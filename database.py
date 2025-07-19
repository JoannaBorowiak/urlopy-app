#Konfuguracja połączenia z bazą
from sqlalchemy import create_engine # łączenie z bazą
from sqlalchemy.ext.declarative import declarative_base # podstawa pod klasy-tabele
from sqlalchemy.orm import sessionmaker # obsługa sesji z bazą

# Zmienna do połączenia z PostgreSQL
SQLALCHEMY_DATABASE_URL = "postgresql://postgres:postgres@localhost/urlopydb"

engine = create_engine(SQLALCHEMY_DATABASE_URL) # silnik łączący SQLAlchemy z bazą 
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False) # fabryka sesji, dzięki której można robić operacje na bazie
Base = declarative_base() # rodzic dla wszystkich modeli
