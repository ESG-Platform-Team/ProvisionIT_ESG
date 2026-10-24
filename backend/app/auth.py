"""
Accounts and JWT sign-in for the people who use the platform.

A successful sign-in returns a signed JSON Web Token (HS256). The token carries
the user's id, name and email, when it was issued, when it expires, and a
unique id (jti). Every API request sends it as `Authorization: Bearer <token>`
and the server checks the signature, the expiry, the issuer and the audience
on every call; no session table is consulted for a valid token.

Signing out records the token's jti in the revoked_tokens table until the
token would have expired anyway, so a signed-out token stops working at once.

Passwords are stored as salted PBKDF2-SHA256 hashes (200,000 iterations).
In the deployment design, Amazon Cognito issues the JWTs instead and this
module only verifies them.

Companies answering a disclosure request never sign in. Their link carries its
own single-purpose token (see disclosure.py).

Environment:
    JWT_SECRET          signing key, at least 32 characters. If unset, a random
                        key is generated once and kept in data/.jwt_secret so
                        local sign-ins survive a restart. Always set it in a
                        deployment.
    JWT_EXPIRE_MINUTES  token lifetime (default 480, a working day)
    SIGNUP_DOMAINS      comma-separated email domains allowed to create an
                        account, for example "provisionit.com.au". Empty means
                        anyone can sign up, which is the local default.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import os
import re
import secrets
import time
import uuid
from pathlib import Path

import jwt

from . import store

ITERATIONS = 200_000
MIN_PASSWORD = 10
ALGORITHM = "HS256"
ISSUER = "provisionit-esg"
AUDIENCE = "provisionit-esg-api"
_EMAIL = re.compile(r"^[^@\s<>\"',;]+@[^@\s<>\"',;]+\.[A-Za-z]{2,}$")

# Failed sign-ins per email, so a password cannot be guessed at speed.
_failures: dict[str, list[float]] = {}
MAX_FAILURES, WINDOW_SECONDS = 8, 300


class AuthError(ValueError):
    pass


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


def _iso(dt: datetime.datetime) -> str:
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def expire_minutes() -> int:
    return int(os.getenv("JWT_EXPIRE_MINUTES", "480"))


def _secret() -> str:
    key = os.getenv("JWT_SECRET")
    if key:
        if len(key) < 32:
            raise RuntimeError("JWT_SECRET must be at least 32 characters")
        return key
    path = Path(os.getenv("JWT_SECRET_FILE", "data/.jwt_secret"))
    if path.exists():
        return path.read_text().strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_urlsafe(48)
    path.write_text(key)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return key


# --- passwords -------------------------------------------------------------------


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split("$")
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt),
                                    int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(check.hex(), digest)


# --- tokens ----------------------------------------------------------------------


def issue_token(user: dict) -> str:
    now = _now()
    claims = {
        "sub": user["userId"], "name": user["name"], "email": user["email"],
        "role": user.get("role", "analyst"),
        "iss": ISSUER, "aud": AUDIENCE,
        "iat": now, "nbf": now,
        "exp": now + datetime.timedelta(minutes=expire_minutes()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, _secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Signature, expiry, issuer and audience are all checked. Raises
    jwt.InvalidTokenError on any failure."""
    return jwt.decode(token, _secret(), algorithms=[ALGORITHM], issuer=ISSUER,
                      audience=AUDIENCE, options={"require": ["exp", "iat", "sub", "jti"]})


def user_for_token(token: str | None) -> dict | None:
    if not token:
        return None
    try:
        claims = decode_token(token)
    except jwt.InvalidTokenError:
        return None
    if store.is_revoked(claims["jti"]):
        return None
    # The account must still exist; a deleted user's token stops working.
    return store.get_user(claims["sub"])


def logout(token: str | None) -> None:
    if not token:
        return
    try:
        claims = decode_token(token)
    except jwt.InvalidTokenError:
        return
    store.revoke_token(claims["jti"], claims["sub"],
                       datetime.datetime.fromtimestamp(claims["exp"], datetime.timezone.utc))


# --- accounts --------------------------------------------------------------------


def public(user: dict) -> dict:
    return {"userId": user["userId"], "name": user["name"], "email": user["email"],
            "role": user.get("role", "analyst"), "createdAt": user.get("createdAt")}


def signup(name: str, email: str, password: str) -> dict:
    name, email = (name or "").strip(), (email or "").strip().lower()
    if not name:
        raise AuthError("Enter your name")
    if not _EMAIL.match(email):
        raise AuthError("Enter a valid email address")
    domains = [d.strip().lower() for d in os.getenv("SIGNUP_DOMAINS", "").split(",") if d.strip()]
    if domains and email.split("@")[1] not in domains:
        raise AuthError("Accounts are limited to " + ", ".join(domains) + " addresses")
    if len(password or "") < MIN_PASSWORD:
        raise AuthError(f"Use a password of at least {MIN_PASSWORD} characters")
    if store.get_user_by_email(email):
        raise AuthError("An account with that email already exists. Sign in instead")
    user = {"userId": f"usr_{uuid.uuid4().hex[:16]}", "name": name[:80], "email": email,
            "role": "analyst", "passwordHash": hash_password(password),
            "createdAt": _iso(_now())}
    store.save_user(user)
    return user


def login(email: str, password: str) -> tuple[str, dict]:
    email = (email or "").strip().lower()
    recent = [t for t in _failures.get(email, []) if time.time() - t < WINDOW_SECONDS]
    _failures[email] = recent
    if len(recent) >= MAX_FAILURES:
        raise AuthError("Too many attempts. Wait five minutes and try again")
    user = store.get_user_by_email(email)
    if not user or not verify_password(password or "", user["passwordHash"]):
        recent.append(time.time())
        raise AuthError("Email or password is incorrect")
    _failures.pop(email, None)
    store.touch_login(user["userId"])
    return issue_token(user), user
