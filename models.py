from sqlalchemy import Column, Integer, String, Date, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, unique=True, index=True, nullable=False)
    role = Column(String, default = "employee")

    leaves = relationship("Leave", back_populates="owner")

class Leave(Base):
    __tablename__ = "leaves"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    date_from = Column(Date)
    date_to = Column(Date)
    comment = Column(String)

    owner = relationship("User", back_populates="leaves")