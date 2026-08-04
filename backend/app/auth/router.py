import logging
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from .database import get_db
from .models import LoginRequest, TokenResponse, UserPublic, ChangePasswordRequest
from .security import (
    verify_password, create_access_token, create_refresh_token,
    hash_refresh_token, refresh_token_expires_at, hash_password
)
from .dependencies import get_current_user
from .audit import log_action

logger = logging.getLogger(__name__)
router = APIRouter()

REFRESH_COOKIE = "hb_refresh_token"


def _set_refresh_cookie(response: Response, raw_token: str):
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=raw_token,
        httponly=True,
        secure=True,    # HTTPS only (nginx terminates SSL)
        samesite="lax",
        max_age=60 * 60 * 24 * 7,  # 7 days
        path="/auth",
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, response: Response, db=Depends(get_db)):
    ip = request.client.host if request.client else None

    user = await db.fetchrow(
        "SELECT * FROM users WHERE username = $1", body.username
    )

    # ===== DEBUG LOGS =====
    logger.info(f"Username received: '{body.username}'")
    logger.info(f"Password received: '{body.password}'")
    logger.info(f"User found: {user is not None}")

    if user:
        result = verify_password(body.password, user["hashed_password"])
        logger.info(f"Password verification result: {result}")
    else:
        result = False
    # ======================

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide"
        )

    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabilitato. Contattare l'amministratore."
        )

    if user["is_locked"]:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account bloccato dopo troppi tentativi. Contattare l'amministratore."
        )

    if not result:
        new_count = user["failed_login_count"] + 1

        if new_count >= 3:
            await db.execute(
                """
                UPDATE users
                SET failed_login_count=$1,
                    is_locked=TRUE,
                    updated_at=NOW()
                WHERE id=$2
                """,
                new_count,
                user["id"]
            )

            await log_action(
                db,
                user["id"],
                user["username"],
                "account_locked",
                ip=ip
            )

            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account bloccato dopo troppi tentativi. Contattare l'amministratore."
            )

        await db.execute(
            """
            UPDATE users
            SET failed_login_count=$1,
                updated_at=NOW()
            WHERE id=$2
            """,
            new_count,
            user["id"]
        )

        remaining = 3 - new_count

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Credenziali non valide. Tentativi rimasti: {remaining}"
        )

    # Success
    await db.execute(
        "UPDATE users SET failed_login_count=0, updated_at=NOW() WHERE id=$1",
        user["id"]
    )

    access_token = create_access_token(
        user["id"],
        user["username"],
        user["role"]
    )

    raw_refresh, hashed_refresh = create_refresh_token()
    expires_at = refresh_token_expires_at()

    await db.execute(
        """
        INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
        VALUES ($1, $2, $3)
        """,
        user["id"],
        hashed_refresh,
        expires_at
    )

    _set_refresh_cookie(response, raw_refresh)

    await log_action(
        db,
        user["id"],
        user["username"],
        "login",
        ip=ip
    )

    return TokenResponse(
        access_token=access_token,
        must_change_password=user["must_change_password"],
        user=UserPublic(
            id=user["id"],
            username=user["username"],
            full_name=user["full_name"],
            designation=user["designation"],
            role=user["role"],
        )
    )