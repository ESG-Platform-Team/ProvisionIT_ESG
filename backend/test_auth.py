#!/usr/bin/env python3
"""Accounts, JWT sign-in and the sign-in gate on the API. Uses a throwaway database."""

import datetime
import os
import tempfile
from pathlib import Path

from testkit import check, done, raises, section

TMP = Path(tempfile.mkdtemp())
os.environ["DATABASE_URL"] = f"sqlite:///{TMP / 'platform.db'}"
os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-for-hs256-signing"
for k in ("AUTH_REQUIRED", "SIGNUP_DOMAINS"):
    os.environ.pop(k, None)

import jwt  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import auth  # noqa: E402
from app.main import app  # noqa: E402

section("PASSWORDS")
h = auth.hash_password("correct horse battery")
check("a password is stored as a salted hash, never as text", "correct horse" not in h)
check("the right password verifies", auth.verify_password("correct horse battery", h))
check("a wrong password does not", not auth.verify_password("wrong", h))
check("the same password hashes differently each time",
      h != auth.hash_password("correct horse battery"))

section("ACCOUNTS")
check("a short password is refused",
      raises(lambda: auth.signup("Ann", "ann@example.com", "short"), auth.AuthError))
check("a bad email is refused",
      raises(lambda: auth.signup("Ann", "not-an-email", "long enough pw"), auth.AuthError))
user = auth.signup("Ann Analyst", "Ann@Example.com", "long enough pw")
check("email is stored in lower case", user["email"] == "ann@example.com")
check("the same email cannot sign up twice",
      raises(lambda: auth.signup("Ann", "ann@example.com", "long enough pw"), auth.AuthError))
os.environ["SIGNUP_DOMAINS"] = "provisionit.com.au"
check("sign-up can be limited to the client's domain",
      raises(lambda: auth.signup("Bob", "bob@gmail.com", "long enough pw"), auth.AuthError))
os.environ.pop("SIGNUP_DOMAINS")

section("JWT")
token, u = auth.login("ann@example.com", "long enough pw")
claims = auth.decode_token(token)
check("signing in returns a JWT for that user", claims["sub"] == u["userId"])
check("the token carries name, email, expiry and a unique id",
      {"name", "email", "exp", "iat", "jti", "iss", "aud"} <= set(claims))
check("the token expires after the configured lifetime",
      claims["exp"] - claims["iat"] == auth.expire_minutes() * 60)
check("a valid token resolves to the user", auth.user_for_token(token)["userId"] == u["userId"])
forged = jwt.encode(dict(claims, name="Mallory"), "a-different-secret-that-is-also-long-x",
                    algorithm="HS256")
check("a token signed with another key is rejected", auth.user_for_token(forged) is None)
expired = jwt.encode(dict(claims, exp=datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)),
                     os.environ["JWT_SECRET"], algorithm="HS256")
check("an expired token is rejected", auth.user_for_token(expired) is None)
wrong_aud = jwt.encode(dict(claims, aud="someone-else"), os.environ["JWT_SECRET"], algorithm="HS256")
check("a token for another audience is rejected", auth.user_for_token(wrong_aud) is None)
none_alg = jwt.encode(claims, None, algorithm="none") if hasattr(jwt, "encode") else ""
check("an unsigned token is rejected", auth.user_for_token(none_alg) is None)
check("rubbish is not a token", auth.user_for_token("not.a.jwt") is None)
auth.logout(token)
check("signing out revokes the token straight away", auth.user_for_token(token) is None)
for _ in range(auth.MAX_FAILURES):
    raises(lambda: auth.login("ann@example.com", "wrong password"), auth.AuthError)
check("repeated wrong passwords lock the account for a while",
      raises(lambda: auth.login("ann@example.com", "long enough pw"), auth.AuthError))
auth._failures.clear()

section("THE API GATE")
client = TestClient(app)
check("health is public", client.get("/api/health").status_code == 200)
check("company search needs a signed-in user", client.get("/api/companies?q=TST").status_code == 401)
r = client.post("/api/auth/signup", json={"name": "Cara", "email": "cara@example.com",
                                           "password": "long enough pw"})
body = r.json()
check("signing up through the API returns a bearer JWT",
      r.status_code == 201 and body.get("tokenType") == "Bearer" and body["token"].count(".") == 2)
hdr = {"Authorization": f"Bearer {body['token']}"}
check("with the token the API answers", client.get("/api/companies?q=TST", headers=hdr).status_code == 200)
check("me returns the signed-in user",
      client.get("/api/auth/me", headers=hdr).json()["user"]["email"] == "cara@example.com")
bad = client.post("/api/auth/login", json={"email": "cara@example.com", "password": "nope"})
check("a wrong password is a 401 with a plain message",
      bad.status_code == 401 and "incorrect" in bad.text)
client.post("/api/auth/logout", headers=hdr)
check("after signing out the token stops working",
      client.get("/api/companies?q=TST", headers=hdr).status_code == 401)
check("the company response page stays public (it has its own token)",
      client.get("/respond/not-a-real-token-123456").status_code == 404)

done()
