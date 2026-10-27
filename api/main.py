"""PlaceGuard FastAPI application.

Main API entry point with all routes configured.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import drives, eligibility, ingestion, students
from config import settings
from database.connection import init_db

# Create FastAPI app
app = FastAPI(
    title="PlaceGuard API",
    description="Placement eligibility management system with LLM-powered extraction and deterministic rule engine",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()


# Health check
@app.get("/health", tags=["system"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "PlaceGuard API",
        "version": "1.0.0",
    }


# Include routers
app.include_router(students.router)
app.include_router(drives.router)
app.include_router(eligibility.router)
app.include_router(ingestion.router)


# Root endpoint
@app.get("/", tags=["system"])
async def root():
    """Root endpoint with API information."""
    return {
        "message": "PlaceGuard API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "students": "/students",
            "drives": "/drives",
            "eligibility": "/eligibility",
            "ingestion": "/ingest",
        },
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
