from fastapi import FastAPI, Depends, HTTPException, Header, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.requests import Request
from sqlalchemy.orm import Session 
from database import engine, SessionLocal
from models import Base, User as Userm, Leave
from schemas import LeaveCreate, Leave as LeaveSchema, UserCreate, User
from starlette.middleware.sessions import SessionMiddleware
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
def read_leaves(db: Session = Depends(get_db)):
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
    leaves = crud.get_leaves(db)
    return templates.TemplateResponse("leaves.html", {"request": request, "leaves": leaves})

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
    user_id = request.session.get("user_id")  # <- to musi być W CIELE FUNKCJI
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
    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/leaves/my", response_class=HTMLResponse)
def get_my_leaves(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=303)

    leaves = db.query(Leave).filter_by(user_id=user_id).all()
    return templates.TemplateResponse("my_leaves.html", {"request": request, "leaves": leaves})

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse("/login", status_code=303)

    return RedirectResponse("/leaves/html", status_code=303)

@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)