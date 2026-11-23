import hashlib
import hmac
import secrets
import base64


ITERATIONS = 100_000
ALGORITHM = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"{ALGORITHM}${ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = stored.split("$")
        if algorithm != ALGORITHM:
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
        return hmac.compare_digest(candidate, expected)
    except (ValueError, TypeError):
        return False


def issue_session_token(user_id) -> str:
    payload = f"{user_id}:{secrets.token_hex(16)}"
    return base64.urlsafe_b64encode(payload.encode()).decode()
