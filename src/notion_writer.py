"""Notion API client — create pages with deduplication."""
import time
from typing import Optional

import httpx

from src.config import (
    NOTION_API_KEY,
    NOTION_DATABASE_ID,
    NOTION_API_VERSION,
    MAX_RETRIES,
    RETRY_BASE_DELAY,
    REQUEST_TIMEOUT,
)
from src.logger import get_logger
from src.state import is_imported, mark_imported

log = get_logger("notion")

_HEADERS = {
    "Authorization": f"Bearer {NOTION_API_KEY}",
    "Notion-Version": NOTION_API_VERSION,
    "Content-Type": "application/json",
}

# Valid select options from the database schema
STATUS_OPTIONS = ["Not Applied", "Applied", "Rejected", "Interviewed", "Accepted"]
EMPLOYMENT_OPTIONS = ["Hackathon", "Job", "Internship"]

# Map parsed employment types to DB options
EMPLOYMENT_TYPE_MAP = {
    "Internship": "Internship",
    "Full-time": "Job",
    "Part-time": "Job",
    "Contract": "Job",
    "Hackathon": "Hackathon",
}


def _build_page_payload(job: dict) -> dict:
    """Convert parsed job dict to Notion page properties."""
    props: dict = {}

    # Company (title)
    if job.get("company"):
        props["Company"] = {
            "title": [{"text": {"content": job["company"][:2000]}}]
        }

    # Position (rich_text)
    if job.get("position"):
        props["Position"] = {
            "rich_text": [{"text": {"content": job["position"][:2000]}}]
        }

    # Status (select) — always "New", map to closest option
    status = job.get("status", "New")
    if status == "New":
        status = "Not Applied"  # closest match in DB
    if status in STATUS_OPTIONS:
        props["Status"] = {"select": {"name": status}}

    # Location (rich_text)
    if job.get("location"):
        props["Location"] = {
            "rich_text": [{"text": {"content": job["location"][:2000]}}]
        }

    # Salary (number)
    if job.get("salary") is not None:
        props["Salary"] = {"number": job["salary"]}

    # Apply link (url)
    if job.get("apply_link"):
        props["Apply link"] = {"url": job["apply_link"][:2000]}

    # Employment Type (select)
    etype = job.get("employment_type", "")
    if etype:
        mapped = EMPLOYMENT_TYPE_MAP.get(etype, etype)
        if mapped in EMPLOYMENT_OPTIONS:
            props["Employment Type"] = {"select": {"name": mapped}}

    # Work Type (rich_text)
    if job.get("work_type"):
        props["Work Type"] = {
            "rich_text": [{"text": {"content": job["work_type"][:2000]}}]
        }

    # Reference Link (url)
    if job.get("reference_link"):
        props["Reference Link"] = {"url": job["reference_link"][:2000]}

    # Build the full payload
    payload: dict = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": props,
    }

    # Add description as page content (markdown blocks)
    description = job.get("description", "")
    if description:
        # Split into chunks for Notion blocks (max 2000 chars per rich_text)
        chunks = [description[i:i+1900] for i in range(0, len(description), 1900)]
        children = []
        for chunk in chunks:
            children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"text": {"content": chunk}}]
                },
            })
        payload["children"] = children[:50]  # Notion limit

    return payload


def create_page(job: dict) -> Optional[str]:
    """
    Create a page in the Notion database.
    Returns the page URL on success, None on failure.
    """
    dedup_key = f"{job.get('channel', '')}:{job.get('message_id', 0)}"

    # Dedup check
    if is_imported(dedup_key):
        log.debug(
            f"Skipping duplicate: {dedup_key}",
            extra={"action": "skip", "channel": job.get("channel", "")},
        )
        return None

    payload = _build_page_payload(job)

    for attempt in range(MAX_RETRIES):
        try:
            resp = httpx.post(
                "https://api.notion.com/v1/pages",
                headers=_HEADERS,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )

            if resp.status_code == 200:
                data = resp.json()
                url = data.get("url", "")
                mark_imported(dedup_key)
                log.info(
                    f"Created Notion page: {url}",
                    extra={
                        "action": "create",
                        "channel": job.get("channel", ""),
                        "message_id": job.get("message_id", 0),
                    },
                )
                return url

            elif resp.status_code == 429:
                # Rate limited
                retry_after = int(resp.headers.get("Retry-After", 5))
                log.warning(f"Notion rate limited. Waiting {retry_after}s")
                time.sleep(retry_after)
                continue

            elif resp.status_code == 400:
                body = resp.text
                log.error(
                    f"Notion 400 error: {body[:500]}",
                    extra={"action": "error"},
                )
                # Don't retry 400s — bad payload
                return None

            elif resp.status_code == 401:
                log.error("Notion 401: Invalid API key")
                return None

            elif resp.status_code == 404:
                log.error("Notion 404: Database not found or not shared with integration")
                return None

            else:
                log.warning(
                    f"Notion {resp.status_code}: {resp.text[:300]}. Attempt {attempt+1}/{MAX_RETRIES}"
                )
                time.sleep(RETRY_BASE_DELAY ** (attempt + 1))

        except httpx.TimeoutException:
            log.warning(f"Notion timeout (attempt {attempt+1}/{MAX_RETRIES})")
            time.sleep(RETRY_BASE_DELAY ** (attempt + 1))

        except httpx.ConnectError as e:
            log.warning(f"Notion connection error: {e}. Attempt {attempt+1}")
            time.sleep(RETRY_BASE_DELAY ** (attempt + 1))

        except Exception as e:
            log.error(f"Unexpected Notion error: {e}", exc_info=True)
            time.sleep(RETRY_BASE_DELAY ** (attempt + 1))

    log.error(
        f"Failed to create Notion page after {MAX_RETRIES} attempts: {dedup_key}",
        extra={"action": "fail"},
    )
    return None
