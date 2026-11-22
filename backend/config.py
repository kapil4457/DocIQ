import os
from sqlalchemy.engine import URL
from dotenv import load_dotenv

load_dotenv()


def get_database_url() -> URL:
    return URL.create(
        drivername="postgresql+psycopg",
        username=os.getenv("POSTGRES_USERNAME", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "password"),
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "postgres"),
    )
