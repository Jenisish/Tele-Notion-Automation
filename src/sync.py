"""
Main sync engine: Telegram -> Parse -> Notion.
Designed to be run as a one-shot (cron) or continuous loop.
"""
import asyncio
import sys
import time
import traceback
from datetime import datetime, timezone

from src.config import validate, SYNC_INTERVAL_SECONDS
from src.logger import get_logger
from src.state import write_status
from src.telegram_fetcher import TelegramFetcher
from src.parser import parse_message
from src.notion_writer import create_page

log = get_logger("sync")


def run_once() -> dict:
    """
    Execute one sync cycle.
    Returns a summary dict.
    """
    summary = {
        "started": datetime.now(timezone.utc).isoformat(),
        "fetched": 0,
        "parsed": 0,
        "imported": 0,
        "skipped": 0,
        "errors": 0,
    }

    try:
        # 1. Fetch from Telegram
        fetcher = TelegramFetcher()
        messages = asyncio.run(fetcher.fetch_all_channels())
        summary["fetched"] = len(messages)
        log.info(f"Fetched {len(messages)} messages total")

        if not messages:
            log.info("No new messages. Nothing to do.")
            write_status(
                last_sync=summary["started"],
                last_result="no_new_messages",
                **summary,
            )
            return summary

        # 2. Parse each message
        jobs = []
        for msg in messages:
            try:
                job = parse_message(msg)
                if job:
                    jobs.append(job)
                else:
                    summary["skipped"] += 1
            except Exception as e:
                log.error(f"Parse error for msg {msg.get('id')}: {e}")
                summary["errors"] += 1

        summary["parsed"] = len(jobs)
        log.info(f"Parsed {len(jobs)} job posts from {len(messages)} messages")

        # 3. Write to Notion
        for job in jobs:
            try:
                url = create_page(job)
                if url:
                    summary["imported"] += 1
                else:
                    summary["skipped"] += 1
            except Exception as e:
                log.error(f"Notion write error: {e}")
                summary["errors"] += 1

        log.info(
            f"Sync complete: {summary['imported']} imported, "
            f"{summary['skipped']} skipped, {summary['errors']} errors"
        )

    except Exception as e:
        log.error(f"Sync cycle failed: {e}\n{traceback.format_exc()}")
        summary["errors"] += 1

    summary["finished"] = datetime.now(timezone.utc).isoformat()
    write_status(last_sync=summary["finished"], last_result="ok", **summary)
    return summary


def run_loop() -> None:
    """Run continuously with SYNC_INTERVAL_SECONDS between cycles."""
    log.info(f"Starting continuous sync (interval={SYNC_INTERVAL_SECONDS}s)")
    write_status(running=True, mode="continuous")

    while True:
        try:
            run_once()
        except KeyboardInterrupt:
            log.info("Interrupted by user")
            write_status(running=False, mode="stopped")
            sys.exit(0)
        except Exception as e:
            log.error(f"Unhandled error in sync loop: {e}\n{traceback.format_exc()}")
            write_status(last_error=str(e), running=True)

        log.info(f"Sleeping {SYNC_INTERVAL_SECONDS}s until next sync")
        time.sleep(SYNC_INTERVAL_SECONDS)


if __name__ == "__main__":
    validate()
    if "--once" in sys.argv:
        run_once()
    elif "--loop" in sys.argv:
        run_loop()
    else:
        # Default: run once (for cron)
        run_once()
