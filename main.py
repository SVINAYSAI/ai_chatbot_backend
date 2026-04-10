from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import settings
from db.connection import connect_db, close_db
from db.indexes import create_indexes
from ai.router import get_provider
from jobs.scheduler import start_scheduler, stop_scheduler

from routers import chat, bookings, tables, auth, admin, restaurant


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("[App] Starting up...")
    await connect_db()
    await create_indexes()
    app.state.ai_provider = get_provider()
    start_scheduler()
    print("[App] Startup complete")
    yield
    # Shutdown
    print("[App] Shutting down...")
    await close_db()
    stop_scheduler()
    print("[App] Shutdown complete")


app = FastAPI(
    title="Restaurant Table Management API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router,       prefix="/api/auth",       tags=["Auth"])
app.include_router(chat.router,       prefix="/api/chat",       tags=["Chat"])
app.include_router(bookings.router,   prefix="/api/bookings",   tags=["Bookings"])
app.include_router(tables.router,     prefix="/api/tables",     tags=["Tables"])
app.include_router(admin.router,      prefix="/api/admin",      tags=["Admin"])
app.include_router(restaurant.router, prefix="/api/restaurant", tags=["Restaurant"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/")
async def root():
    return {
        "message": "Restaurant Table Management API",
        "version": "1.0.0",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
