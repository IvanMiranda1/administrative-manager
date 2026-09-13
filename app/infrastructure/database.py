import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./administrative_system.db")

# check_same_thread=False es específico de SQLite: permite usar la misma
# conexión desde distintos threads, que es como FastAPI maneja requests.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session():
    """Dependency de FastAPI: una sesión por request, que se cierra sola."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
