import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db, seed_demo_data, BASE_DIR, UPLOAD_DIR
from app.routers import auth, student, tutor, admin, public

app = FastAPI(title="TOLK Language Practice Platform", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup event: Initialize database and seed accounts
@app.on_event("startup")
def on_startup():
    init_db()
    seed_demo_data()

# Include routers
app.include_router(auth.router)
app.include_router(student.router)
app.include_router(tutor.router)
app.include_router(admin.router)
app.include_router(public.router)

# Mount static files and uploaded receipts
STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/uploads/receipts", StaticFiles(directory=UPLOAD_DIR), name="receipts")

@app.get("/")
def serve_index():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/health")
def health_check():
    return {"status": "ok", "app": "TOLK MVP", "version": "1.0.0"}
