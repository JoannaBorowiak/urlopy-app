from fastapi import FastAPI, Depends, HTTPException, Header
from sqlalchemy.orm import Session 
from database import engine, SessionLocal
from models import Base, User as Userm, Leave
from schemas import LeaveCreate, Leave as LeaveSchema, UserCreate, User
import crud

app = FastAPI()

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
