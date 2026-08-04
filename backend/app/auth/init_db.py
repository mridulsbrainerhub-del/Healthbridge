import logging
from ..config import ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_FULL_NAME
from .security import hash_password
from .roles import Role

logger = logging.getLogger(__name__)

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id                   SERIAL PRIMARY KEY,
    username             VARCHAR(100) UNIQUE NOT NULL,
    hashed_password      VARCHAR(255) NOT NULL,
    full_name            VARCHAR(255) NOT NULL,
    designation          VARCHAR(255),
    role                 VARCHAR(20) NOT NULL,
    is_active            BOOLEAN NOT NULL DEFAULT TRUE,
    is_locked            BOOLEAN NOT NULL DEFAULT FALSE,
    failed_login_count   INTEGER NOT NULL DEFAULT 0,
    must_change_password BOOLEAN NOT NULL DEFAULT TRUE,
    created_by           INTEGER REFERENCES users(id),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) UNIQUE NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    revoked     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    username    VARCHAR(100) NOT NULL,
    action      VARCHAR(50) NOT NULL,
    fiscal_code VARCHAR(16),
    ip_address  VARCHAR(45),
    details     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id    ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_fiscal_code ON audit_logs(fiscal_code);
"""


async def initialize_database(pool):
    async with pool.acquire() as conn:
        await conn.execute(CREATE_TABLES_SQL)
        logger.info("Auth tables verified/created")

        # Migrate legacy 'operator' role to 'nurse', then enforce the current role set
        await conn.execute("UPDATE users SET role = 'nurse' WHERE role = 'operator'")
        await conn.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check")
        await conn.execute(
            f"ALTER TABLE users ADD CONSTRAINT users_role_check CHECK (role IN "
            f"({', '.join(repr(r) for r in (Role.ADMIN.value, Role.NURSE.value, Role.DOCTOR.value))}))"
        )
        logger.info("Role constraint verified (admin, nurse, doctor)")

        # Seed admin if no users exist
        count = await conn.fetchval("SELECT COUNT(*) FROM users")
        if count == 0:
            if not ADMIN_PASSWORD:
                logger.warning("ADMIN_PASSWORD not set — skipping admin seed")
                return
            # temporary basis
            logger.info(f"ADMIN_USERNAME={ADMIN_USERNAME}")
            logger.info(f"ADMIN_PASSWORD={ADMIN_PASSWORD}")
            hashed = hash_password(ADMIN_PASSWORD)
            await conn.execute(
                """
                INSERT INTO users (username, hashed_password, full_name, role, must_change_password)
                VALUES ($1, $2, $3, 'admin', FALSE)
                """,
                ADMIN_USERNAME,
                hashed,
                ADMIN_FULL_NAME,
            )
            logger.info(f"Admin account seeded: username='{ADMIN_USERNAME}'")

            demo_users = [
                ("nurse.demo", "NurseDemo2026!", "Giulia Bianchi", Role.NURSE.value),
                ("doctor.demo", "DoctorDemo2026!", "Marco Rossi", Role.DOCTOR.value),
            ]
            for username, password, full_name, role in demo_users:
                await conn.execute(
                    """
                    INSERT INTO users (username, hashed_password, full_name, role, must_change_password)
                    VALUES ($1, $2, $3, $4, FALSE)
                    """,
                    username,
                    hash_password(password),
                    full_name,
                    role,
                )
                logger.info(f"Demo {role} account seeded: username='{username}'")
