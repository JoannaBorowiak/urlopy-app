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
def get_leaves(db: Session = Depends(get_db)):
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
    return RedirectResponse(url="/leaves/html", status_code=303)

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, db: Session = Depends(get_db)):
    if request.session.get("user_id"):
        return RedirectResponse(url="/dashboard", status_code=303)

    users = db.query(Userm).all()
    return templates.TemplateResponse("login.html", {
        "request": request,
        "users": users
    })

@app.post("/login")
def login(request: Request, db: Session = Depends(get_db), name: str = Form(...), password: str = Form(...)):
    user = db.query(Userm).filter_by(name=name).first()

    if not user or user.password != password:
        users = db.query(Userm).all()
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Nieprawidłowa nazwa użytkownika lub hasło",
            "users": users
        }, status_code=401)

    request.session["user_id"] = user.id
    request.session["user_name"] = user.name
    request.session["role"] = user.role
    return RedirectResponse(url="/dashboard", status_code=303)


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

@app.get("/leaves/calendar", response_class=HTMLResponse)
def show_calendar(request: Request, db: Session = Depends(get_db)):
    leaves = crud.get_leaves(db)
    return templates.TemplateResponse("calendar.html", {
        "request": request,
        "leaves": leaves
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


def get_polish_holidays(year: int):
    # Statyczna lista świąt ustawowych (bez Wielkanocy i Bożego Ciała na razie)
    return {
        date(year, 1, 1),   # Nowy Rok
        date(year, 1, 6),   # Trzech Króli
        date(year, 5, 1),   # Święto Pracy
        date(year, 5, 3),   # Święto Konstytucji 3 Maja
        date(year, 8, 15),  # Wniebowzięcie NMP
        date(year, 11, 1),  # Wszystkich Świętych
        date(year, 11, 11), # Święto Niepodległości
        date(year, 12, 25), # Boże Narodzenie
        date(year, 12, 26), # Drugi dzień świąt
    }

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    users = db.query(Userm).all()
    leaves = db.query(Leave).all()
    current_year = date.today().year

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
        "year": current_year
    })


