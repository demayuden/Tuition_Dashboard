from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import settings

# SQLAlchemy engine (connects to Postgres via DATABASE_URL)
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,   # prints SQL queries when DEBUG=True
    future=True,
    connect_args={"sslmode": "require"}
)

# SessionLocal is used in routes to interact with DB
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True
)

# Base class for all ORM models
Base = declarative_base()

# Dependency for FastAPI routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
