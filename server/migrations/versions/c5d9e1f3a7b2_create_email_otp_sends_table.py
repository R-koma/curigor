"""create email_otp_sends table

Revision ID: c5d9e1f3a7b2
Revises: b3f7d1e9a2c4
Create Date: 2026-10-27 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "c5d9e1f3a7b2"
down_revision: str | Sequence[str] | None = "b3f7d1e9a2c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""--sql
        CREATE TABLE email_otp_sends (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email_hash TEXT NOT NULL,
            ip_hash    TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX idx_email_otp_sends_email_created ON email_otp_sends(email_hash, created_at)")
    op.execute("CREATE INDEX idx_email_otp_sends_ip_created ON email_otp_sends(ip_hash, created_at)")
    op.execute("CREATE INDEX idx_email_otp_sends_created ON email_otp_sends(created_at)")
    op.execute("""--sql
        CREATE FUNCTION reserve_email_otp_send(
            p_email_hash TEXT,
            p_ip_hash TEXT,
            p_ip_hourly INT,
            p_email_hourly INT,
            p_email_daily INT
        ) RETURNS TABLE (send_id UUID, retry_after_seconds INT)
        LANGUAGE plpgsql AS $$
        DECLARE
            v_free_at TIMESTAMPTZ;
            v_retry_at TIMESTAMPTZ;
        BEGIN
            PERFORM pg_advisory_xact_lock(hashtext('email_otp_sends:email:' || p_email_hash));
            IF p_ip_hash IS NOT NULL THEN
                PERFORM pg_advisory_xact_lock(hashtext('email_otp_sends:ip:' || p_ip_hash));
            END IF;

            DELETE FROM email_otp_sends WHERE created_at < NOW() - INTERVAL '1 day';

            SELECT s.created_at + INTERVAL '1 hour' INTO v_free_at
            FROM email_otp_sends s
            WHERE s.email_hash = p_email_hash AND s.created_at >= NOW() - INTERVAL '1 hour'
            ORDER BY s.created_at DESC OFFSET p_email_hourly - 1 LIMIT 1;
            v_retry_at := v_free_at;

            SELECT s.created_at + INTERVAL '1 day' INTO v_free_at
            FROM email_otp_sends s
            WHERE s.email_hash = p_email_hash AND s.created_at >= NOW() - INTERVAL '1 day'
            ORDER BY s.created_at DESC OFFSET p_email_daily - 1 LIMIT 1;
            v_retry_at := GREATEST(v_retry_at, v_free_at);

            IF p_ip_hash IS NOT NULL THEN
                SELECT s.created_at + INTERVAL '1 hour' INTO v_free_at
                FROM email_otp_sends s
                WHERE s.ip_hash = p_ip_hash AND s.created_at >= NOW() - INTERVAL '1 hour'
                ORDER BY s.created_at DESC OFFSET p_ip_hourly - 1 LIMIT 1;
                v_retry_at := GREATEST(v_retry_at, v_free_at);
            END IF;

            IF v_retry_at IS NOT NULL THEN
                RETURN QUERY SELECT NULL::UUID, GREATEST(1, CEIL(EXTRACT(EPOCH FROM v_retry_at - NOW())))::INT;
                RETURN;
            END IF;

            RETURN QUERY
                INSERT INTO email_otp_sends (email_hash, ip_hash) VALUES (p_email_hash, p_ip_hash)
                RETURNING id, NULL::INT;
        END;
        $$
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS reserve_email_otp_send(TEXT, TEXT, INT, INT, INT)")
    op.execute("DROP TABLE IF EXISTS email_otp_sends")
