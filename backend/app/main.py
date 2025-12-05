from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import Base, engine
from .routers import students, packages

# Create DB tables (DEV ONLY — disable in production, use Alembic instead)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Tuition Lesson Dashboard API")

# --------------------------------------------------------
# CORS SETTINGS
# Allow frontend (React) to access backend
# --------------------------------------------------------
# CORS SETTINGS
from fastapi.middleware.cors import CORSMiddleware

# allow both common dev ports (5173, 5174) and 127.0.0.1 forms
# CORS SETTINGS
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
print("DEBUG: CORS middleware installed with allow_origins=['*']")
# --------------------------------------------------------
# ROUTES
# --------------------------------------------------------
app.include_router(students.router)
app.include_router(packages.router)


# --------------------------------------------------------
# ROOT ENDPOINT (for testing)
# --------------------------------------------------------
@app.get("/")
def root():
    return {"message": "Backend is running!"}
