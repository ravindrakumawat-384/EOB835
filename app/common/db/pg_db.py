import psycopg2
from ..config import settings
from ...utils.logger import get_logger
logger = get_logger(__name__)


# Example connection (replace with your config)
def get_pg_conn():

   
    return psycopg2.connect(
        dbname="eob_db",
        user="aman0622",
        password="password1234",
        host="127.0.0.1",
        port="5432"
    )

# Ensure organizations table has timezone column (idempotent, run at import)
def _ensure_timezone_column():
    try:
        with get_pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE organizations ADD COLUMN IF NOT EXISTS timezone TEXT;")
                conn.commit()
    except Exception as e:
        logger.warning(f"Could not ensure timezone column: {e}")

_ensure_timezone_column()