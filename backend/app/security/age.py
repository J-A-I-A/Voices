"""Age computation from date of birth (never persist a static age)."""
from __future__ import annotations

import datetime as _dt
from typing import Optional


def age_from_dob(dob: _dt.date, today: Optional[_dt.date] = None) -> int:
    """Return whole years between dob and today (UTC date)."""
    today = today or _dt.datetime.now(_dt.timezone.utc).date()
    years = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        years -= 1
    return years


def is_at_least_18(dob: _dt.date, today: Optional[_dt.date] = None) -> bool:
    """True if the person is 18 or older on the reference date."""
    return age_from_dob(dob, today) >= 18

