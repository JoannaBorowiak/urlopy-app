from sqlalchemy.orm import Session
from models import Leave
from models import User as Userm
from schemas import LeaveCreate, UserCreate

def create_leave(db: Session, leave: LeaveCreate, user_id: int):
    db_leave = Leave(
        user_id=user_id,
        date_from=leave.date_from,
        date_to=leave.date_to,
        comment=leave.comment
    )
    db.add(db_leave)
    db.commit()
    db.refresh(db_leave)
    return db_leave

def get_leaves(db: Session):
    return db.query(Leave).all()

def create_user(db: Session, user: UserCreate):
    db_user = Userm(
        email=user.email,
        name=user.name,
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_users(db: Session):
    return db.query(Userm).all()

