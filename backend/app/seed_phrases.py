"""Seed the Phrase bank with a starter set of Jamaican-English prompts.

Run:  python -m app.seed_phrases
"""
from __future__ import annotations

from .db import SessionLocal
from .models.phrase import Phrase
from .services.phrase_length import count_words

SEED_PHRASES = [
    "Good morning, how are you today?",
    "I grew up in Kingston and I love the music here.",
    "One love, one heart, let's get together and feel alright.",
    "Mi deh yah, everyting irie. How yuh stay?",
    "The sun is shining bright over the harbour today.",
    "Please pass the salt and pepper when you are ready.",
    "She sell sea shells by the sea shore down at Hellshire.",
    "Tonight we are having rice and peas with fricasseed chicken.",
    "The bus will be late again, that is just how it goes.",
    "Blessings and growth to you and your family this year.",
    "Walk good, my yute, and remember where you come from.",
    "Three mangoes, four bananas, and a dozen oranges please.",
    "The rain falling hard today, but the farmers need it.",
    "Can you please repeat what you just said one more time?",
    "Everything is going to be alright in the end, just have patience.",
]


def main() -> None:
    db = SessionLocal()
    try:
        existing = db.query(Phrase).count()
        if existing:
            print(f"Phrases already seeded ({existing}). Skipping.")
            return
        for text in SEED_PHRASES:
            db.add(Phrase(text=text, locale="en-JM", active=True,
                          word_count=count_words(text)))
        db.commit()
        print(f"Seeded {len(SEED_PHRASES)} phrases.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

