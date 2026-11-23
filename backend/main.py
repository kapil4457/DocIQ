from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from controllers.base_controller import router as health_router
from controllers.organization_controller import router as organization_router
from controllers.user_controller import router as user_router
from controllers.workspace_controller import router as workspace_router
from controllers.document_controller import router as document_router
from utils.logger import setup_logging
from utils.exception_handler import global_exception_handler, AppError
from utils.object_storage import ensure_bucket
from database.db_engine import init_db
import logging
import os

FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]



setup_logging()
logger = logging.getLogger("app.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting DocIQ backend...")
    init_db()
    logger.info("Database initialized successfully")
    ensure_bucket()
    logger.info("Object storage ready")
    yield
    logger.info("Shutting down DocIQ backend...")

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(AppError, global_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)
app.include_router(health_router)
app.include_router(organization_router)
app.include_router(user_router)
app.include_router(workspace_router)
app.include_router(document_router)
