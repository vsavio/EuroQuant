import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from pydantic import BaseModel
from sqlalchemy import text, create_engine
import hashlib
import secrets

# ─── Configuration ──────────────────────────────────────────────────────────────
_jwt_secret = os.environ.get("JWT_SECRET_KEY")
if not _jwt_secret:
    raise RuntimeError(
        "FATAL: JWT_SECRET_KEY environment variable is not set. "
        "Generate one with: python3 -c \"import secrets; print(secrets.token_hex(32))\""
    )
SECRET_KEY = _jwt_secret
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 hours

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://euroquant_user:euroquant_password@db:5432/euroquant_db")
engine = create_engine(DATABASE_URL)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)
router = APIRouter(prefix="/api/auth", tags=["auth"])


# ─── Password Hashing ─────────────────────────────────────────────────────────
def get_password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return f"{salt}:{dk.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        salt, hash_hex = hashed_password.split(":")
        dk = hashlib.pbkdf2_hmac('sha256', plain_password.encode('utf-8'), salt.encode('utf-8'), 100000)
        return secrets.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


# ─── JWT Token ────────────────────────────────────────────────────────────────
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# ─── Audit Log Helper ─────────────────────────────────────────────────────────
def write_audit_log(username: str, action: str, details: dict, ip_address: str = "unknown"):
    """Records a security-relevant action to the audit_log table."""
    import json as _json
    try:
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO audit_log (username, action, details, ip_address)
                    VALUES (:username, :action, CAST(:details AS jsonb), :ip)
                """),
                {
                    "username": username,
                    "action": action,
                    "details": _json.dumps(details),
                    "ip": ip_address
                }
            )
            conn.commit()
    except Exception as e:
        print(f"Audit log write failed: {e}")


# ─── Auth Dependencies ────────────────────────────────────────────────────────
def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """FastAPI dependency: requires a valid JWT token (any role)."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        role: str = payload.get("role", "Trader")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    return {"username": username, "role": role}


def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """FastAPI dependency: requires Admin role. Raises 403 for Traders."""
    if current_user.get("role") != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required for this action.",
        )
    return current_user


# ─── Pydantic Models ─────────────────────────────────────────────────────────
class UserRegister(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str

class ChangePasswordPayload(BaseModel):
    current_password: str
    new_password: str


# ─── Auth Routes ──────────────────────────────────────────────────────────────
@router.post("/register", response_model=Token)
def register(user: UserRegister, request: Request):
    hashed = get_password_hash(user.password)
    with engine.connect() as conn:
        exists = conn.execute(
            text("SELECT id FROM users WHERE username = :username"),
            {"username": user.username}
        ).fetchone()
        if exists:
            raise HTTPException(status_code=400, detail="Username already registered")
        conn.execute(
            text("INSERT INTO users (username, hashed_password, role) VALUES (:username, :hashed_password, 'Trader')"),
            {"username": user.username, "hashed_password": hashed}
        )
        conn.commit()

    ip = request.client.host if request.client else "unknown"
    write_audit_log(user.username, "user_register", {"role": "Trader"}, ip)
    access_token = create_access_token(
        data={"sub": user.username, "role": "Trader"},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer", "role": "Trader"}


@router.post("/login", response_model=Token)
def login(user: UserLogin, request: Request):
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT hashed_password, role FROM users WHERE username = :username"),
            {"username": user.username}
        ).fetchone()

    ip = request.client.host if request.client else "unknown"
    if not row or not verify_password(user.password, row[0]):
        write_audit_log(user.username, "login_failed", {"reason": "wrong credentials"}, ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    write_audit_log(user.username, "login_success", {"role": row[1]}, ip)
    access_token = create_access_token(
        data={"sub": user.username, "role": row[1]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer", "role": row[1]}


@router.post("/change-password")
def change_password(payload: ChangePasswordPayload, request: Request, current_user: dict = Depends(get_current_user)):
    """Allows any authenticated user to change their own password."""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT hashed_password FROM users WHERE username = :username"),
            {"username": current_user["username"]}
        ).fetchone()

    if not row or not verify_password(payload.current_password, row[0]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if len(payload.new_password) < 8:
        raise HTTPException(status_code=422, detail="New password must be at least 8 characters")

    new_hash = get_password_hash(payload.new_password)
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE users SET hashed_password = :hash WHERE username = :username"),
            {"hash": new_hash, "username": current_user["username"]}
        )
        conn.commit()

    ip = request.client.host if request.client else "unknown"
    write_audit_log(current_user["username"], "password_changed", {}, ip)
    return {"status": "success", "message": "Password updated successfully"}


@router.get("/users")
def list_users(current_user: dict = Depends(require_admin)):
    """Admin only: returns all registered users."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, username, role, created_at FROM users ORDER BY created_at DESC")
        ).fetchall()
    return [
        {"id": r[0], "username": r[1], "role": r[2], "created_at": r[3].isoformat() if r[3] else None}
        for r in rows
    ]


@router.delete("/users/{user_id}")
def delete_user(user_id: int, request: Request, current_user: dict = Depends(require_admin)):
    """Admin only: deletes a user by ID. Cannot delete yourself."""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT username FROM users WHERE id = :id"),
            {"id": user_id}
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        if row[0] == current_user["username"]:
            raise HTTPException(status_code=400, detail="Cannot delete your own account")
        conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        conn.commit()

    ip = request.client.host if request.client else "unknown"
    write_audit_log(current_user["username"], "user_deleted", {"deleted_user_id": user_id, "deleted_username": row[0]}, ip)
    return {"status": "success", "deleted_user_id": user_id}
