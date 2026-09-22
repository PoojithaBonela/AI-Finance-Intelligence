import re
from datetime import date
from typing import Optional
import logging

logger = logging.getLogger(__name__)

MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def is_valid_calendar_date(year: int, month: int, day: int) -> bool:
    """
    Validates that (year, month, day) represents a real calendar date.
    Enforces leap-year rules (e.g. 2024-02-29 is valid, 2023-02-29 is invalid).
    Accepts all historical/past years without artificial current-year restrictions.
    """
    if year < 1900 or year > 2100:
        return False
    try:
        date(year, month, day)
        return True
    except (ValueError, TypeError, OverflowError):
        return False


def normalize_and_validate_date(date_str: Optional[str]) -> Optional[str]:
    """
    Normalizes any recognized receipt date into canonical 'YYYY-MM-DD'.
    Preserves historical dates (2024, 2023, 2022, etc.).
    Returns 'YYYY-MM-DD' if valid, or None if unparseable / invalid calendar date.
    """
    if not date_str:
        return None

    s = str(date_str).strip()
    if not s or s.lower() in ("null", "none", "n/a", "undefined"):
        return None

    # Strip prefixes like "Date:", "Dated:", "On:"
    s = re.sub(r'^(date|dated|on)[\s:]+', '', s, flags=re.IGNORECASE).strip()

    # Strip trailing time/timezone (e.g. " 16:48", " 14:22:05", " 04:30 PM", "T14:22:00...", " Time: ...")
    s = re.sub(r'[\s,]+(time|at)[\s:]+.*$', '', s, flags=re.IGNORECASE)
    s = re.sub(r'T\d{1,2}:\d{2}(:\d{2})?.*$', '', s)
    s = re.sub(r'[\s,]+\d{1,2}:\d{2}(:\d{2})?(\s*(am|pm))?.*$', '', s, flags=re.IGNORECASE)
    s = s.strip()

    # 1. ISO YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD
    m = re.match(r'^(\d{4})[\/\-\.](\d{1,2})[\/\-\.](\d{1,2})$', s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if is_valid_calendar_date(y, mo, d):
            return f"{y:04d}-{mo:02d}-{d:02d}"
        return None

    # 2. Textual month: DD Mon YYYY or DD-Mon-YYYY (e.g. "15 Aug 2024", "15-August-2024", "10-Jul-2024")
    m = re.match(r'^(\d{1,2})[\s\-\/\.]+([a-zA-Z]+)[\s\-\/\.,]+(\d{2,4})$', s)
    if m:
        d = int(m.group(1))
        mon_str = m.group(2).lower()
        y = int(m.group(3))
        if y < 100:
            y += 2000 if y < 70 else 1900
        if mon_str in MONTH_MAP:
            mo = MONTH_MAP[mon_str]
            if is_valid_calendar_date(y, mo, d):
                return f"{y:04d}-{mo:02d}-{d:02d}"
        return None

    # 3. Textual month: Mon DD, YYYY (e.g. "Aug 15, 2024", "August 15 2024")
    m = re.match(r'^([a-zA-Z]+)[\s\-\/\.]+?(\d{1,2})[\s\-\/\.,]+(\d{2,4})$', s)
    if m:
        mon_str = m.group(1).lower()
        d = int(m.group(2))
        y = int(m.group(3))
        if y < 100:
            y += 2000 if y < 70 else 1900
        if mon_str in MONTH_MAP:
            mo = MONTH_MAP[mon_str]
            if is_valid_calendar_date(y, mo, d):
                return f"{y:04d}-{mo:02d}-{d:02d}"
        return None

    # 4. DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, MM/DD/YYYY
    m = re.match(r'^(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})$', s)
    if m:
        p1, p2, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if p1 > 12 and p2 <= 12:
            d, mo = p1, p2
        elif p2 > 12 and p1 <= 12:
            mo, d = p1, p2
        else:
            # Default to DD/MM/YYYY
            d, mo = p1, p2
        if is_valid_calendar_date(y, mo, d):
            return f"{y:04d}-{mo:02d}-{d:02d}"
        return None

    # 5. Two-digit year: DD/MM/YY or DD-MM-YY
    m = re.match(r'^(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{2})$', s)
    if m:
        p1, p2, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y = 2000 + yy if yy < 70 else 1900 + yy
        if p1 > 12 and p2 <= 12:
            d, mo = p1, p2
        elif p2 > 12 and p1 <= 12:
            mo, d = p1, p2
        else:
            d, mo = p1, p2
        if is_valid_calendar_date(y, mo, d):
            return f"{y:04d}-{mo:02d}-{d:02d}"
        return None

    return None
