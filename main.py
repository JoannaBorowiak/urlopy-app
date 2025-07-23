from fastapi import FastAPI, Depends, HTTPException, Header, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session 
from database import engine, SessionLocal
from models import Base, User as Userm, Leave
from schemas import LeaveCreate, Leave as LeaveSchema, UserCreate, User
from starlette.middleware.sessions import SessionMiddleware
from datetime import date, timedelta
from typing import Optional
from fastapi import Request, Query
import crud
from crud import get_polish_holidays
import bcrypt
import smtplib

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.add_middleware(SessionMiddleware, secret_key="klucz")

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(x_user_id: int = Header(...), db: Session = Depends(get_db)):
    user = db.query(Userm).filter_by(id=x_user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Użytkownik nie istnieje")
    return user

@app.post("/leaves/", response_model=LeaveSchema)
def create_leave(leave: LeaveCreate, 
                db: Session = Depends(get_db),
                current_user: Userm = Depends(get_current_user)):
    return crud.create_leave(db=db, leave=leave, user_id=current_user.id)

@app.get("/leaves/", response_model=list[LeaveSchema])
def read_leaves(db: Session = Depends(get_db)):
    return crud.get_leaves(db)

@app.post("/users/", response_model=User)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    return crud.create_user(db=db, user=user)

@app.get("/users/", response_model=list[User])
def read_users(db: Session = Depends(get_db)):
    return crud.get_users(db)

@app.get("/me")
def read_current_user(current_user: Userm = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email, "role": current_user.role}

@app.put("/leaves/{leave_id}", response_model=LeaveSchema)
def update_leave(
    leave_id: int,
    leave: LeaveCreate,
    db: Session = Depends(get_db),
    current_user: Userm = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Tylko administrator może edytować urlopy")
    db_leave = db.query(Leave).filter_by(id=leave_id).first()
    if not db_leave:
        raise HTTPException(status_code=404, detail="Urlop nie istnieje")
    db_leave.date_from = leave.date_from
    db_leave.date_to = leave.date_to
    db_leave.comment = leave.comment

    db.commit()
    db.refresh(db_leave)
    return db_leave

@app.delete("/leaves/{leave_id}")
def delete_leave(leave_id: int,
                 db: Session = Depends(get_db),
                 current_user: Userm = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Tylko administrator może usuwać urlopy")

    db_leave = db.query(Leave).filter_by(id=leave_id).first()
    if not db_leave:
        raise HTTPException(status_code=404, detail="Urlop nie istnieje")

    db.delete(db_leave)
    db.commit()
    return {"detail": "Urlop został usunięty"}

@app.get("/leaves/html", response_class=HTMLResponse)
def get_leaves_html(request: Request, db: Session = Depends(get_db)):
    # user_id jako string
    user_id_param = request.query_params.get("user_id")

    # próba konwersji user_id do int jeśli podano wartość
    try:
        user_id = int(user_id_param) if user_id_param else None
    except ValueError:
        # Jeśli user_id nie da się skonwertować — przekieruj bez filtra
        return RedirectResponse("/leaves/html", status_code=303)

    query = db.query(Leave)

    if user_id:
        query = query.filter(Leave.user_id == user_id)

    all_leaves = query.all()
    today = date.today()

    upcoming = [l for l in all_leaves if l.date_to >= today]
    past = [l for l in all_leaves if l.date_to < today]
    upcoming.sort(key=lambda l: l.date_from)
    past.sort(key=lambda l: l.date_from)

    sorted_leaves = upcoming + past
    users = db.query(Userm).all()

    return templates.TemplateResponse("leaves.html", {
        "request": request,
        "leaves": sorted_leaves,
        "users": users,
        "selected_user_id": user_id
    })


@app.get("/leaves/form", response_class=HTMLResponse)
def show_leave_form(request: Request):
    return templates.TemplateResponse("leave_form.html", {"request": request})

@app.post("/leaves/form")
def submit_leave_form(
    request: Request,
    date_from: str = Form(...),
    date_to: str = Form(...),
    comment: str = Form(None),
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=303)

    new_leave = Leave(
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        comment=comment
    )
    db.add(new_leave)
    db.commit()

    from utils import send_leave_notification

    admins = db.query(Userm).filter_by(role="admin").all()
    admin_emails = [a.email for a in admins]

    user = db.query(Userm).filter_by(id=user_id).first()

    send_leave_notification(
        admin_emails=admin_emails,
        employee_name=user.name,
        date_from=new_leave.date_from,
        date_to=new_leave.date_to,
        comment=new_leave.comment
    )

    return RedirectResponse(url="/leaves/html", status_code=303)

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, db: Session = Depends(get_db)):
    if request.session.get("user_id"):
        return RedirectResponse(url="leaves/calendar", status_code=303)

    users = db.query(Userm).all()
    return templates.TemplateResponse("login.html", {
        "request": request,
        "users": users
    })

@app.post("/login")
def login(request: Request, db: Session = Depends(get_db), name: str = Form(...), password: str = Form(...)):
    user = db.query(Userm).filter_by(name=name).first()

    if not user or not verify_password(password, user.password):
        users = db.query(Userm).all()
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Nieprawidłowa nazwa użytkownika lub hasło",
            "users": users
        }, status_code=401)

    request.session["user_id"] = user.id
    request.session["user_name"] = user.name
    request.session["role"] = user.role
    return RedirectResponse(url="leaves/calendar", status_code=303)


@app.get("/leaves/my", response_class=HTMLResponse)
def get_my_leaves(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=303)

    leaves = db.query(Leave).filter_by(user_id=user_id).all()
    return templates.TemplateResponse("my_leaves.html", {"request": request, "leaves": leaves})

@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)

from datetime import timedelta

@app.get("/leaves/calendar", response_class=HTMLResponse)
def show_calendar(request: Request, db: Session = Depends(get_db)):
    leaves = crud.get_leaves(db)

    adjusted_leaves = []
    for leave in leaves:
        adjusted_leave = leave.__dict__.copy()
        adjusted_leave["owner"] = leave.owner  # bo jest używane w HTML
        adjusted_leave["date_to"] = leave.date_to + timedelta(days=1)
        adjusted_leaves.append(adjusted_leave)

    return templates.TemplateResponse("calendar.html", {
        "request": request,
        "leaves": adjusted_leaves
    })

@app.get("/leaves/edit/{leave_id}", response_class=HTMLResponse)
def edit_leave_form(
    request: Request,
    leave_id: int,
    db: Session = Depends(get_db)
):
    leave = db.query(Leave).filter_by(id=leave_id).first()
    if not leave:
        return HTMLResponse(content="Urlop nie istnieje", status_code=404)

    return templates.TemplateResponse("leave_form.html", {
        "request": request,
        "leave": leave,
        "edit": True
    })

@app.post("/leaves/edit/{leave_id}")
def edit_leave_submit(
    request: Request,
    leave_id: int,
    date_from: str = Form(...),
    date_to: str = Form(...),
    comment: str = Form(None),
    db: Session = Depends(get_db)
):
    leave = db.query(Leave).filter_by(id=leave_id).first()
    if not leave:
        return HTMLResponse(content="Urlop nie istnieje", status_code=404)

    leave.date_from = date_from
    leave.date_to = date_to
    leave.comment = comment
    db.commit()
    return RedirectResponse(url="/leaves/html", status_code=303)

@app.post("/leaves/delete/{leave_id}")
def delete_leave_post(
    request: Request,
    leave_id: int,
    db: Session = Depends(get_db)
):
    if request.session.get("role") != "admin":
        return HTMLResponse("Brak uprawnień", status_code=403)

    leave = db.query(Leave).filter_by(id=leave_id).first()
    if not leave:
        return HTMLResponse("Urlop nie istnieje", status_code=404)

    db.delete(leave)
    db.commit()

    return RedirectResponse(url="/leaves/html", status_code=303)

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    users = db.query(Userm).order_by(Userm.name).all()
    leaves = db.query(Leave).all()

    years_in_db = sorted({l.date_from.year for l in leaves} | {l.date_to.year for l in leaves})
    
    selected_year = request.query_params.get("year")
    try:
        current_year = int(selected_year)
        if current_year not in years_in_db:
            current_year = max(years_in_db) if years_in_db else date.today().year
    except (TypeError, ValueError):
        current_year = max(years_in_db) if years_in_db else date.today().year

    user_summary = []

    holidays = get_polish_holidays(current_year)

    for user in users:
        user_leaves = [l for l in leaves if l.user_id == user.id]

        days_past = 0
        days_future = 0
        today = date.today()

        for leave in user_leaves:
            start = max(leave.date_from, date(current_year, 1, 1))
            end = min(leave.date_to, date(current_year, 12, 31))
            if start <= end:
                current = start
                while current <= end:
                    if current.weekday() < 5 and current not in holidays:
                        if current <= today:
                            days_past += 1
                        else:
                            days_future += 1
                    current += timedelta(days=1)

        user_summary.append({
            "name": user.name,
            "email": user.email,
            "days_past": days_past,
            "days_future": days_future,
            "days_total": days_past + days_future
        })

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user_summary": user_summary,
        "year": current_year,
        "selected_year": current_year,
        "years": years_in_db
    })

@app.get("/my-account", response_class=HTMLResponse)
def my_account(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=303)
    
    user = db.query(Userm).filter_by(id=user_id).first()
    if not user:
        return HTMLResponse("Użytkownik nie znaleziony", status_code=404)

    return templates.TemplateResponse("my-account.html", {"request": request, "user": user})

@app.get("/change-password", response_class=HTMLResponse)
def change_password_form(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse("change_password.html", {"request": request})

@app.post("/change-password", response_class=HTMLResponse)
def change_password_submit(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=303)

    user = db.query(Userm).filter_by(id=user_id).first()
    if not user or not verify_password(old_password, user.password):
        return templates.TemplateResponse("change_password.html", {
            "request": request,
            "error": "Stare hasło jest nieprawidłowe"
        }, status_code=400)

    user.password = hash_password(new_password)
    db.commit()

    return RedirectResponse("/my-account", status_code=303)

def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
