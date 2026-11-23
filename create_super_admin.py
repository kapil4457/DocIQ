"""Standalone utility to create the first DocIQ super admin.

Zero dependency on the backend application: reads its own .env file next to
this script (or plain environment variables) and talks to Postgres directly.

Usage:
    python create_super_admin.py
"""

import os
import sys
import base64
import hashlib
import hmac
import secrets
import uuid
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):
        return False

from sqlalchemy import create_engine, text, URL

SCRIPT_DIR = Path(__file__).resolve().parent
ENV_PATH = SCRIPT_DIR / ".env"

PBKDF2_ITERATIONS = 100_000
ALGORITHM = "pbkdf2_sha256"


def load_config() -> dict:
    for candidate in [ENV_PATH, SCRIPT_DIR / "backend" / ".env"]:
        if candidate.exists():
            load_dotenv(candidate, override=False)
            break

    config = {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": os.getenv("POSTGRES_PORT", "5432"),
        "database": os.getenv("POSTGRES_DB", "dociq"),
        "username": os.getenv("POSTGRES_USERNAME", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", "password"),
    }

    missing = [k for k, v in config.items() if not v]
    if missing:
        print(f"Missing database configuration: {', '.join(missing)}")
        print(f"Set them in {ENV_PATH} or as environment variables.")
        sys.exit(1)
    return config


def connect(config: dict):
    url = URL.create(
        drivername="postgresql+psycopg",
        username=config["username"],
        password=config["password"],
        host=config["host"],
        port=int(config["port"]),
        database=config["database"],
    )
    try:
        return create_engine(url, pool_pre_ping=True).connect()
    except Exception as exc:
        print(f"Could not connect to the database: {exc}")
        sys.exit(1)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return (
        f"{ALGORITHM}${PBKDF2_ITERATIONS}$"
        f"{base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"
    )


def count_super_admins(conn) -> int:
    result = conn.execute(
        text("SELECT count(*) FROM users WHERE role = 'super_admin'")
    ).scalar()
    return result or 0


def user_exists(conn, email: str) -> bool:
    return (
        conn.execute(text("SELECT 1 FROM users WHERE email = :email"), {"email": email}).scalar()
        is not None
    )


def tables_ready(conn) -> bool:
    return conn.execute(
        text("SELECT to_regclass('public.users') IS NOT NULL")
    ).scalar()


def prompt_input(label: str, validator=None) -> str:
    while True:
        value = input(f"{label}: ").strip()
        if validator:
            error = validator(value)
            if error:
                print(f"  {error}")
                continue
        return value


def prompt_password() -> str:
    import getpass

    while True:
        password = getpass.getpass("Password (min 8 chars): ")
        if len(password) < 8:
            print("  Password must be at least 8 characters.")
            continue
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("  Passwords do not match. Try again.")
            continue
        return password


def valid_email(value: str) -> str | None:
    if "@" not in value or value.startswith("@") or value.endswith("@"):
        return "Enter a valid email address."
    return None


def main() -> None:
    print("=" * 50)
    print("DocIQ Super Admin Setup")
    print("=" * 50)

    config = load_config()
    conn = connect(config)

    if not tables_ready(conn):
        print("The 'users' table does not exist yet.")
        print("Start the backend once so it creates the schema, then rerun this script.")
        sys.exit(1)

    existing = count_super_admins(conn)
    if existing > 0:
        print(f"\nA super admin already exists ({existing} found).")
        answer = input("Create another super admin anyway? [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted. No changes made.")
            sys.exit(0)

    print("\nEnter the details for the new super admin.\n")
    name = prompt_input("Full name", validator=lambda v: None if v else "Name cannot be empty.")
    email = prompt_input("Email", validator=valid_email)

    if user_exists(conn, email):
        print(f"\nA user with email {email} already exists.")
        sys.exit(1)

    password = prompt_password()

    user_id = uuid.uuid4()
    conn.execute(
        text(
            """
            INSERT INTO users (id, name, email, password, "organizationId", role, "createdAt", "createdBy", "modifiedAt", "modifiedBy")
            VALUES (:id, :name, :email, :password, NULL, 'super_admin', NOW(), :id, NOW(), :id)
            """
        ),
        {"id": user_id, "name": name, "email": email, "password": hash_password(password)},
    )
    conn.commit()
    conn.close()

    print("\nSuper admin created successfully.")
    print(f"  ID:    {user_id}")
    print(f"  Name:  {name}")
    print(f"  Email: {email}")
    print("\nYou can now log in through the application.")


if __name__ == "__main__":
    main()
