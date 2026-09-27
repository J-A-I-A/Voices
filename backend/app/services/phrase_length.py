"""Classify phrases by how long they take to read aloud.

Bands are defined in seconds, which is what actually matters for a recording:

    short   under 10s
    medium  10s to 20s
    long    20s to 35s

Word counts are derived from those bounds and a speaking rate, rather than
hard-coded, so changing PHRASE_WORDS_PER_MINUTE moves every threshold together
and the bands keep meaning what they say. A phrase estimated beyond the long
bound is rejected — 35 seconds is the maximum a contributor is asked to read
in one take.
"""
from __future__ import annotations

import enum
import re
from dataclasses import dataclass

from ..config import settings

# A "word" for counting purposes: runs of letters/digits/apostrophes. Keeps
# "don't" and "mi'd" as one word, and ignores stray punctuation.
_WORD_RE = re.compile(r"[\w'’]+", re.UNICODE)


class PhraseLength(str, enum.Enum):
    short = "short"
    medium = "medium"
    long = "long"


@dataclass(frozen=True)
class Thresholds:
    words_per_minute: int
    short_max_seconds: int
    medium_max_seconds: int
    long_max_seconds: int
    short_max_words: int
    medium_max_words: int
    long_max_words: int


def count_words(text: str) -> int:
    return len(_WORD_RE.findall(text or ""))


def _words_for(seconds: float) -> int:
    """Most words that fit in `seconds` at the configured rate."""
    return max(1, int(settings.phrase_words_per_minute / 60.0 * seconds))


def thresholds() -> Thresholds:
    return Thresholds(
        words_per_minute=settings.phrase_words_per_minute,
        short_max_seconds=settings.phrase_short_max_seconds,
        medium_max_seconds=settings.phrase_medium_max_seconds,
        long_max_seconds=settings.phrase_long_max_seconds,
        short_max_words=_words_for(settings.phrase_short_max_seconds),
        medium_max_words=_words_for(settings.phrase_medium_max_seconds),
        long_max_words=_words_for(settings.phrase_long_max_seconds),
    )


def estimated_seconds(word_count: int) -> float:
    """Expected spoken duration, rounded to one decimal."""
    if word_count <= 0:
        return 0.0
    return round(word_count / (settings.phrase_words_per_minute / 60.0), 1)


def band_for_words(word_count: int) -> PhraseLength:
    """Band for a word count. Anything beyond the long bound still reports
    `long`; use `exceeds_maximum` to reject it."""
    t = thresholds()
    if word_count <= t.short_max_words:
        return PhraseLength.short
    if word_count <= t.medium_max_words:
        return PhraseLength.medium
    return PhraseLength.long


def band_for_text(text: str) -> PhraseLength:
    return band_for_words(count_words(text))


def exceeds_maximum(word_count: int) -> bool:
    return word_count > thresholds().long_max_words


def word_range_for(band: PhraseLength) -> tuple[int, int]:
    """Inclusive (min, max) word count for a band — used to filter in SQL."""
    t = thresholds()
    if band is PhraseLength.short:
        return 1, t.short_max_words
    if band is PhraseLength.medium:
        return t.short_max_words + 1, t.medium_max_words
    return t.medium_max_words + 1, t.long_max_words


def describe(word_count: int) -> str:
    """Human summary, e.g. '12 words · about 5s · short'."""
    return f"{word_count} words · about {estimated_seconds(word_count):g}s · {band_for_words(word_count).value}"
