from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Ganti nama database sesuai keinginan Anda
DATABASE_URL = "sqlite:///gudang_sistem.db"

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False}  # Diperlukan khusus untuk SQLite
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Helper untuk mendapatkan session (berguna untuk Flask/FastAPI)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()