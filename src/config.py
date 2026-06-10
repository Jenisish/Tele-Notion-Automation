"""Configuration loader — reads .env, validates required keys."""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ──────────────────────────────────────────
TELEGRAM_API_ID: int = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH: str = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_SESSION_PATH: str = os.getenv(
    "TELEGRAM_SESSION_PATH",
    str(Path(__file__).resolve().parent.parent / "state" / "telegram_session"),
)

# ── Notion ────────────────────────────────────────────
NOTION_API_KEY: str = os.getenv("NOTION_API_KEY", "")
NOTION_DATABASE_ID: str = os.getenv(
    "NOTION_DATABASE_ID", "566e019f-d3cf-838a-8f9c-81939785f919"
)
NOTION_API_VERSION: str = os.getenv("NOTION_API_VERSION", "2022-06-28")

# ── Channels to monitor ───────────────────────────────
TELEGRAM_CHANNELS_RAW: str = os.getenv("TELEGRAM_CHANNELS", "")
TELEGRAM_CHANNELS: list[str] = [
    c.strip()
    for c in TELEGRAM_CHANNELS_RAW.split(",")
    if c.strip()
] if TELEGRAM_CHANNELS_RAW else [
    "merademy",
    "freshershunt",
    "ytsmart1437",
    "goyalarsh",
    "gocareers",
    "edubard_internship",
    "jobwithmayra",
    "Fresherjobsadda",
    "jobs_and_internships_updates",
    "offcampus_phodenge",
    "PLACEMENTLELO",
    "vishalkumar_linkedin",
]

# ── Sync settings ─────────────────────────────────────
SYNC_INTERVAL_SECONDS: int = int(os.getenv("SYNC_INTERVAL_SECONDS", "300"))
STATE_FILE: str = os.getenv(
    "STATE_FILE",
    str(Path(__file__).resolve().parent.parent / "state" / "sync_state.json"),
)
LOG_DIR: str = os.getenv(
    "LOG_DIR",
    str(Path(__file__).resolve().parent.parent / "logs"),
)
STATUS_FILE: str = os.getenv(
    "STATUS_FILE",
    str(Path(__file__).resolve().parent.parent / "state" / "status.json"),
)
IMPORTED_FILE: str = os.getenv(
    "IMPORTED_FILE",
    str(Path(__file__).resolve().parent.parent / "state" / "imported.json"),
)
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "5"))
RETRY_BASE_DELAY: float = float(os.getenv("RETRY_BASE_DELAY", "2.0"))
REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
LOG_MAX_BYTES: int = int(os.getenv("LOG_MAX_BYTES", "5242880"))  # 5 MB
LOG_BACKUP_COUNT: int = int(os.getenv("LOG_BACKUP_COUNT", "5"))


def validate() -> None:
    """Exit with error if required config is missing."""
    errors: list[str] = []
    if not TELEGRAM_API_ID or TELEGRAM_API_ID == 0:
        errors.append("TELEGRAM_API_ID is missing or 0")
    if not TELEGRAM_API_HASH:
        errors.append("TELEGRAM_API_HASH is missing")
    if not NOTION_API_KEY:
        errors.append("NOTION_API_KEY is missing")
    if not NOTION_DATABASE_ID:
        errors.append("NOTION_DATABASE_ID is missing")
    if errors:
        for e in errors:
            print(f"[CONFIG ERROR] {e}", file=sys.stderr)
        sys.exit(1)
