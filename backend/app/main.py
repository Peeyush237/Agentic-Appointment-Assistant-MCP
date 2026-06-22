from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import router as api_router
from app.core.config import settings
from app.db.database import Base, engine, SessionLocal
from app.db.seed import seed_data  # importing seed also registers all models with Base
from app.mcp.server import router as mcp_router


def _apply_column_migrations() -> None:
    """Add new columns to existing tables (idempotent — uses IF NOT EXISTS)."""
    stmts = [
        "ALTER TABLE doctors      ADD COLUMN IF NOT EXISTS clinic_id         INTEGER",
        "ALTER TABLE doctors      ADD COLUMN IF NOT EXISTS is_active         BOOLEAN DEFAULT TRUE",
        "ALTER TABLE users         ADD COLUMN IF NOT EXISTS doctor_profile_id INTEGER",
        "ALTER TABLE users         ADD COLUMN IF NOT EXISTS clinic_id         INTEGER",
        "ALTER TABLE appointments  ADD COLUMN IF NOT EXISTS clinic_id         INTEGER",
        "ALTER TABLE appointments  ADD COLUMN IF NOT EXISTS user_id           INTEGER",
    ]
    with engine.connect() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))
        conn.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)  # creates new tables (cities, clinics, doctor_availability)
    _apply_column_migrations()             # adds new columns to existing tables
    with SessionLocal() as db:
        seed_data(db)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_origin,
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(mcp_router, prefix="/mcp", tags=["mcp"])
