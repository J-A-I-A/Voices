"""Phrase bank endpoints: list active phrases (used by portal debugging) and a
protected create endpoint for seeding. Not central to acceptance criteria but
keeps the phrase bank configurable per spec.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..models.phrase import Phrase
from ..models.user import User
from ..security.deps import get_current_user

router = APIRouter(prefix="/phrases", tags=["phrases"])


class PhraseOut(BaseModel):
    id: str
    text: str
    locale: str
    active: bool


class PhraseCreate(BaseModel):
    text: str
    locale: str = "en-JM"
    active: bool = True


@router.get("", response_model=list[PhraseOut])
async def list_active(db: Session = Depends(get_db)):
    rows = db.query(Phrase).filter(Phrase.active.is_(True)).all()
    return [PhraseOut(id=p.id, text=p.text, locale=p.locale, active=p.active) for p in rows]


@router.post("", response_model=PhraseOut)
async def create_phrase(
    body: PhraseCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not user.is_reviewer:
        raise HTTPException(status_code=403, detail="Reviewer access required to add phrases.")
    p = Phrase(text=body.text, locale=body.locale, active=body.active)
    db.add(p)
    db.commit()
    db.refresh(p)
    return PhraseOut(id=p.id, text=p.text, locale=p.locale, active=p.active)

