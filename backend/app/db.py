# backend/app/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings
from urllib.parse import urlparse

DATABASE_URL = settings.DATABASE_URL

# detect whether the URL requires SSL (supabase / ?sslmode=require)
_use_ssl = False
try:
    parsed = urlparse(DATABASE_URL)
    # either explicit sslmode in query or remote host like supabase
    if "sslmode=require" in (parsed.query or ""):
        _use_ssl = True
    elif parsed.hostname and "supabase.co" in parsed.hostname:
        _use_ssl = True
except Exception:
    _use_ssl = False

if _use_ssl:
    engine = create_engine(
        DATABASE_URL,
        echo=settings.DEBUG,
        future=True,
        connect_args={"sslmode": "require"}
    )
else:
    engine = create_engine(
        DATABASE_URL,
        echo=settings.DEBUG,
        future=True
    )

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True
)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
