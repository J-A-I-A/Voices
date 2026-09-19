"""Text normalization + Word Error Rate against the assigned phrase."""
from __future__ import annotations

import re
import unicodedata

# Common number words for light numeric expansion (jiwer handles some, but we
# expand a few Jamaican-context numerals explicitly before tokenizing).
_NUM_WORD_MAP = {
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
    "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
    "10": "ten", "100": "one hundred", "1000": "one thousand",
}


def _expand_numbers(text: str) -> str:
    def repl(m: re.Match) -> str:
        token = m.group(0)
        return _NUM_WORD_MAP.get(token, token)
    return re.sub(r"\b\d+\b", repl, text)


def normalize(text: str) -> str:
    """Lowercase, strip punctuation, expand numbers, collapse whitespace."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.lower()
    text = re.sub(r"[\u2018\u2019]", "'", text)
    # Replace a modest set of patois contractions to help alignment.
    contractions = {
        "mi nuh": "mi no", "nuh": "no", "cah": "because", "ting": "thing",
        "dem": "them", "unu": "you", "yah": "here", "deh": "there",
        "man dem": "them", "pickney": "child", "bwoy": "boy", "gyal": "girl",
    }
    for k, v in contractions.items():
        text = re.sub(rf"\b{re.escape(k)}\b", v, text)
    text = _expand_numbers(text)
    # Remove punctuation, keep letters/numbers/spaces/apostrophes.
    text = re.sub(r"[^\w\s']", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def compute_wer(reference: str, hypothesis: str) -> float:
    """Word error rate in [0.0, ...]. 0.0 = perfect match."""
    try:
        from jiwer import wer as _wer
        return float(_wer(normalize(reference), normalize(hypothesis)))
    except Exception:
        # Fallback: a simple Levenshtein-on-words WER if jiwer is unavailable.
        ref = normalize(reference).split()
        hyp = normalize(hypothesis).split()
        if not ref:
            return 0.0 if not hyp else 1.0
        d = _levenshtein(ref, hyp)
        return d / len(ref)


def _levenshtein(a: list[str], b: list[str]) -> int:
    m, n = len(a), len(b)
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        cur = [i] + [0] * n
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[n]
