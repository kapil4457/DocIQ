from contextlib import asynccontextmanager
from fastapi import  FastAPI
from controllers.base_controller import router as health_router
from utils.logger import setup_logging  
from database.db_engine import init_db
import logging



setup_logging()
logger = logging.getLogger("app.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting DocIQ backend...")
    init_db()
    logger.info("Database initialized successfully")
    yield
    logger.info("Shutting down DocIQ backend...")

app = FastAPI(lifespan=lifespan)
app.include_router(health_router)