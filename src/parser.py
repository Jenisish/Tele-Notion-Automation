"""Parse Telegram job posts into structured fields."""
import re
from typing import Optional
from src.logger import get_logger

log = get_logger("parser")

# ── Regex patterns ─────────────────────────────────────

# URLs
URL_PATTERN = re.compile(
    r'https?://[^\s<>"\'\)\]]+',
    re.IGNORECASE,
)

# Salary patterns
SALARY_PATTERNS = [
    re.compile(r'(?:salary|package|ctc|pay|stipend|compensation)\s*[:\-]?\s*([^\n\r]+)', re.IGNORECASE),
    re.compile(r'(?:₹|rs\.?|inr|lpa|per annum|/year|/month)\s*[:\-]?\s*([^\n\r]+)', re.IGNORECASE),
    re.compile(r'(\d[\d,\.]+\s*(?:lpa|lakhs?|k|₹|rs|inr|per\s*(?:annum|year|month)))', re.IGNORECASE),
    re.compile(r'(?:₹|rs\.?)\s*([\d,\.]+(?:\s*[-–to]\s*[\d,\.]+)?)', re.IGNORECASE),
]

# Location patterns
LOCATION_PATTERNS = re.compile(
    r'(?:location|work\s*from|based\s*in|city|place|office)\s*[:\-]?\s*([^\n\r,]+)',
    re.IGNORECASE,
)

# Employment type
EMPLOYMENT_KEYWORDS = {
    "internship": "Internship",
    "intern": "Internship",
    "full-time": "Full-time",
    "full time": "Full-time",
    "part-time": "Part-time",
    "part time": "Part-time",
    "contract": "Contract",
    "freelance": "Contract",
    "hackathon": "Hackathon",
    "fellowship": "Internship",
}

# Work type
WORK_TYPE_KEYWORDS = {
    "remote": "Remote",
    "work from home": "Remote",
    "wfh": "Remote",
    "hybrid": "Hybrid",
    "on-site": "On-site",
    "onsite": "On-site",
    "on site": "On-site",
    "in-office": "On-site",
    "in office": "On-site",
}

# Company patterns
COMPANY_PATTERNS = [
    re.compile(r'(?:company|organization|firm)\s*[:\-]?\s*([^\n\r,|]+)', re.IGNORECASE),
    re.compile(r'(?:at|for)\s+([A-Z][\w\s&\.\-]+?)(?:\s*[,\|\n\r]|$)'),
    re.compile(r'hir(?:ing|er)\s*[:\-]?\s*([^\n\r,|]+)', re.IGNORECASE),
]

# Position / title patterns
POSITION_PATTERNS = [
    re.compile(r'(?:position|role|designation|title)\s*[:\-]?\s*([^\n\r,|#]+)', re.IGNORECASE),
    re.compile(r'(?:job|opening|vacancy)\s*[:\-]?\s*([^\n\r,|#]+)', re.IGNORECASE),
    re.compile(r'(?:hiring|recruit(?:ing)?|looking for|need)\s*[:\-]?\s*([^\n\r,|#]+)', re.IGNORECASE),
]


def clean_text(text: str) -> str:
    """Remove excessive whitespace, normalize."""
    # Remove zero-width chars
    text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)
    # Collapse whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    # Collapse newlines (max 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def extract_urls(text: str) -> list[str]:
    """Extract all URLs from text."""
    urls = URL_PATTERN.findall(text)
    # Clean trailing punctuation
    cleaned = []
    for u in urls:
        u = u.rstrip('.,;:!?)\'\"')
        if u not in cleaned:
            cleaned.append(u)
    return cleaned


def extract_salary(text: str) -> Optional[str]:
    for pat in SALARY_PATTERNS:
        m = pat.search(text)
        if m:
            val = m.group(1).strip()
            if len(val) > 60:
                val = val[:60]
            return val
    return None


def extract_location(text: str) -> Optional[str]:
    m = LOCATION_PATTERNS.search(text)
    if m:
        val = m.group(1).strip()
        if len(val) > 80:
            val = val[:80]
        return val
    return None


def extract_employment_type(text: str) -> Optional[str]:
    lower = text.lower()
    for keyword, etype in EMPLOYMENT_KEYWORDS.items():
        if keyword in lower:
            return etype
    return None


def extract_work_type(text: str) -> Optional[str]:
    lower = text.lower()
    for keyword, wtype in WORK_TYPE_KEYWORDS.items():
        if keyword in lower:
            return wtype
    return None


def extract_company(text: str) -> Optional[str]:
    for pat in COMPANY_PATTERNS:
        m = pat.search(text)
        if m:
            val = m.group(1).strip()
            # Skip if it looks like a URL or too long
            if val.startswith("http") or val.startswith("/") or len(val) > 60:
                continue
            # Clean trailing noise
            val = re.sub(r'\s+(?:is|are|was|were|for|and|with|the|a|an)\s*$', '', val, flags=re.IGNORECASE)
            if len(val) >= 2:
                return val
    return None


def extract_position(text: str) -> Optional[str]:
    for pat in POSITION_PATTERNS:
        m = pat.search(text)
        if m:
            val = m.group(1).strip()
            # Remove trailing hashtags/emojis noise
            val = re.sub(r'\s+#.*$', '', val)
            val = re.sub(r'\s{2,}', ' ', val).strip()
            if len(val) > 120:
                val = val[:120]
            if len(val) >= 3:
                return val
    return None


def is_job_post(text: str) -> bool:
    """Heuristic: does this message look like a job posting?"""
    lower = text.lower()
    job_keywords = [
        "hiring", "job", "opening", "vacancy", "position", "role",
        "apply", "recruitment", "recruiting", "opportunity", "career",
        "internship", "intern", "fresher", "experience", "walk-in",
        "walkin", "placement", "off-campus", "offcampus", "job alert",
        "jobalert", "job opening", "we are hiring", "we're hiring",
        "required", "looking for", "join us", "join our team",
    ]
    score = sum(1 for kw in job_keywords if kw in lower)
    return score >= 2


def parse_message(msg: dict) -> Optional[dict]:
    """
    Parse a Telegram message into structured job fields.
    Returns None if the message doesn't look like a job post.
    """
    text = clean_text(msg.get("text", ""))
    if not text or len(text) < 30:
        return None

    if not is_job_post(text):
        return None

    urls = extract_urls(text)

    # First URL that looks like an application link
    apply_link = None
    for u in urls:
        if any(kw in u.lower() for kw in [
            "apply", "forms", "google", "typeform", "jotform",
            "linktr", "bit.ly", "tinyurl", "career", "jobs",
            "unstop", "devpost", "mlh", "internshala", "naukri",
            "linkedin", "indeed", "glassdoor", "wellfound", "angel",
        ]):
            apply_link = u
            break
    # If no specific apply link, use first URL
    if not apply_link and urls:
        apply_link = urls[0]

    # Salary as number for Notion
    salary_raw = extract_salary(text)
    salary_num = None
    if salary_raw:
        # Try to extract a numeric value
        nums = re.findall(r'[\d,\.]+', salary_raw)
        if nums:
            try:
                val = float(nums[0].replace(",", ""))
                if "lpa" in salary_raw.lower() or "lakh" in salary_raw.lower():
                    val *= 100000
                elif "k" in salary_raw.lower() and val < 1000:
                    val *= 1000
                salary_num = val
            except ValueError:
                pass

    return {
        "company": extract_company(text) or "",
        "position": extract_position(text) or "",
        "status": "New",
        "location": extract_location(text) or "",
        "salary": salary_num,
        "apply_link": apply_link or "",
        "employment_type": extract_employment_type(text) or "",
        "work_type": extract_work_type(text) or "",
        "reference_link": msg.get("link", ""),
        "description": text[:2000],  # Notion rich_text limit
        "channel": msg.get("channel", ""),
        "message_id": msg.get("id", 0),
        "date": msg.get("date", ""),
    }
