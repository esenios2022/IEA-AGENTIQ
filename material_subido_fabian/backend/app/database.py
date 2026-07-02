from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
import os
from dotenv import load_dotenv

load_dotenv()

# Supabase connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres.djyuotgzcwhqvoowvixv:YOUR_PASSWORD@db.djyuotgzcwhqvoowvixv.supabase.co:5432/postgres"
)

# Crear engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Inicializar BD con migrations"""
    from .models import Base
    Base.metadata.create_all(bind=engine)
