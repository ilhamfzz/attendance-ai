from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from os import getenv
from app.core.env import ensure_env_loaded

ensure_env_loaded()

DATABASE_URL = getenv("DATABASE_URL")
if not DATABASE_URL:
	raise RuntimeError("DATABASE_URL tidak ditemukan. Pastikan sudah di-set di .env")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()