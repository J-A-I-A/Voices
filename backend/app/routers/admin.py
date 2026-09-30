"""Admin router: overview stats, user roles, phrase bank, consent records, export.

Every route is behind `get_admin`. Endpoints that expose contributor identity
(users, consent records) are deliberately separate from the dataset export,
which is de-identified — the Privacy Notice promises published data "will not
include any data that could reasonably identify you".
"""
from __future__ import annotations

import csv
import datetime as _dt
import io
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models.consent import ConsentChannel, ConsentRecord
from ..models.phrase import PHRASE_TEXT_MAX_CHARS, Phrase
from ..models.user import User
from ..models.voice_note import VoiceNote, VoiceNoteStatus
from ..schemas.voice_note import VoiceNoteListResponse, VoiceNoteOut
from ..security.deps import get_admin
from ..services import consent as consent_svc
from ..services.phrase_import import PhraseImportError, parse_phrase_file
from ..services.phrase_length import (
    PhraseLength, band_for_words, count_words, estimated_seconds,
    exceeds_maximum, thresholds, word_range_for,
)
from ..services.s3 import delete_key
from .reviewer import voice_note_out

# Generous for a phrase list, small enough to reject a stray upload.
MAX_IMPORT_BYTES = 5 * 1024 * 1024

logger = logging.getLogger("carib.admin")
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_admin)])


# ─── Schemas ────────────────────────────────────────────────────────────
class StatusCount(BaseModel):
    status: str
    count: int


class StatsOut(BaseModel):
    users_total: int
    users_verified: int
    users_consented: int
    reviewers: int
    admins: int
    notes_total: int
    notes_by_status: list[StatusCount]
    phrases_total: int
    phrases_active: int
    total_audio_seconds: int
    contributors_with_notes: int
    acceptance_rate: Optional[float] = Field(
        None, description="accepted / (accepted + rejected), null when nothing is resolved yet"
    )
    needs_review: int


class AdminUserOut(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: str
    auth_provider: str
    whatsapp_number: Optional[str]
    whatsapp_verified: bool
    is_reviewer: bool
    is_admin: bool
    has_consent: bool
    note_count: int
    created_at: _dt.datetime


class UserListOut(BaseModel):
    items: list[AdminUserOut]
    total: int


class RoleUpdate(BaseModel):
    is_reviewer: Optional[bool] = None
    is_admin: Optional[bool] = None


class PhraseOut(BaseModel):
    id: str
    text: str
    locale: str
    active: bool
    note_count: int
    word_count: int
    estimated_seconds: float
    length: str


class LengthBandOut(BaseModel):
    band: str
    min_words: int
    max_words: int
    max_seconds: int
    count: int


class PhraseLengthInfo(BaseModel):
    words_per_minute: int
    bands: list[LengthBandOut]


class PhraseCreate(BaseModel):
    text: str = Field(min_length=3, max_length=PHRASE_TEXT_MAX_CHARS)
    locale: str = "en-JM"
    active: bool = True


class PhraseUpdate(BaseModel):
    text: Optional[str] = Field(None, min_length=3, max_length=PHRASE_TEXT_MAX_CHARS)
    locale: Optional[str] = None
    active: Optional[bool] = None


class ConsentOut(BaseModel):
    id: str
    user_id: str
    user_name: str
    user_email: str
    policy_version: str
    channel: str
    evidence: Optional[str]
    phone: Optional[str]
    consented_at: _dt.datetime
    withdrawn_at: Optional[_dt.datetime]
    is_active: bool


class ConsentListOut(BaseModel):
    items: list[ConsentOut]
    total: int


# ─── Overview ───────────────────────────────────────────────────────────
@router.get("/stats", response_model=StatsOut)
async def stats(db: Session = Depends(get_db)):
    by_status = dict(
        db.query(VoiceNote.status, func.count(VoiceNote.id)).group_by(VoiceNote.status).all()
    )
    counts = {s.value: int(by_status.get(s, 0)) for s in VoiceNoteStatus}
    accepted, rejected = counts.get("accepted", 0), counts.get("rejected", 0)
    resolved = accepted + rejected

    consented = (
        db.query(func.count(func.distinct(ConsentRecord.user_id)))
        .filter(
            ConsentRecord.withdrawn_at.is_(None),
            ConsentRecord.policy_version == settings.privacy_policy_version,
        )
        .scalar()
    ) or 0

    return StatsOut(
        users_total=db.query(func.count(User.id)).filter(User.deleted_at.is_(None)).scalar() or 0,
        users_verified=db.query(func.count(User.id)).filter(
            User.whatsapp_verified.is_(True), User.deleted_at.is_(None)).scalar() or 0,
        users_consented=int(consented),
        reviewers=db.query(func.count(User.id)).filter(User.is_reviewer.is_(True)).scalar() or 0,
        admins=db.query(func.count(User.id)).filter(User.is_admin.is_(True)).scalar() or 0,
        notes_total=sum(counts.values()),
        notes_by_status=[StatusCount(status=k, count=v) for k, v in counts.items()],
        phrases_total=db.query(func.count(Phrase.id)).scalar() or 0,
        phrases_active=db.query(func.count(Phrase.id)).filter(Phrase.active.is_(True)).scalar() or 0,
        total_audio_seconds=int(db.query(func.coalesce(func.sum(VoiceNote.duration_seconds), 0)).scalar() or 0),
        contributors_with_notes=int(db.query(func.count(func.distinct(VoiceNote.user_id))).scalar() or 0),
        acceptance_rate=(accepted / resolved) if resolved else None,
        needs_review=counts.get("needs_review", 0),
    )


# ─── Users ──────────────────────────────────────────────────────────────
def _user_out(u: User, note_count: int, consented: bool) -> AdminUserOut:
    return AdminUserOut(
        id=u.id, first_name=u.first_name, last_name=u.last_name, email=u.email,
        auth_provider=u.auth_provider.value if hasattr(u.auth_provider, "value") else str(u.auth_provider),
        whatsapp_number=u.whatsapp_number, whatsapp_verified=u.whatsapp_verified,
        is_reviewer=u.is_reviewer, is_admin=u.is_admin, has_consent=consented,
        note_count=note_count, created_at=u.created_at,
    )


@router.get("/users", response_model=UserListOut)
async def list_users(
    q: Optional[str] = Query(None, description="match on name or email"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(User).filter(User.deleted_at.is_(None))
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(
            User.email.ilike(like), User.first_name.ilike(like), User.last_name.ilike(like)
        ))
    total = query.count()
    users = query.order_by(User.created_at.desc()).limit(limit).offset(offset).all()

    ids = [u.id for u in users]
    note_counts = dict(
        db.query(VoiceNote.user_id, func.count(VoiceNote.id))
        .filter(VoiceNote.user_id.in_(ids)).group_by(VoiceNote.user_id).all()
    ) if ids else {}
    consented = {
        r[0] for r in db.query(ConsentRecord.user_id).filter(
            ConsentRecord.user_id.in_(ids),
            ConsentRecord.withdrawn_at.is_(None),
            ConsentRecord.policy_version == settings.privacy_policy_version,
        ).all()
    } if ids else set()

    return UserListOut(
        items=[_user_out(u, int(note_counts.get(u.id, 0)), u.id in consented) for u in users],
        total=total,
    )


@router.patch("/users/{user_id}/roles", response_model=AdminUserOut)
async def update_roles(
    user_id: str,
    body: RoleUpdate,
    admin: User = Depends(get_admin),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    if body.is_admin is False and target.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot remove your own admin access.")
    if body.is_admin is False:
        remaining = db.query(func.count(User.id)).filter(
            User.is_admin.is_(True), User.id != target.id
        ).scalar() or 0
        if remaining == 0:
            raise HTTPException(status_code=400, detail="Refusing to remove the last admin.")

    if body.is_reviewer is not None:
        target.is_reviewer = body.is_reviewer
    if body.is_admin is not None:
        target.is_admin = body.is_admin
    db.commit()
    db.refresh(target)
    logger.info("admin %s updated roles for %s: reviewer=%s admin=%s",
                admin.email, target.email, target.is_reviewer, target.is_admin)

    count = db.query(func.count(VoiceNote.id)).filter(VoiceNote.user_id == target.id).scalar() or 0
    return _user_out(target, int(count), consent_svc.has_consent(db, target))


# ─── Phrase bank ────────────────────────────────────────────────────────

def _phrase_out(p: Phrase, note_count: int = 0) -> PhraseOut:
    return PhraseOut(
        id=p.id, text=p.text, locale=p.locale, active=p.active, note_count=note_count,
        word_count=p.word_count,
        estimated_seconds=estimated_seconds(p.word_count),
        length=band_for_words(p.word_count).value,
    )


def _apply_text(p: Phrase, text: str) -> None:
    """Set the text and keep the cached word count in step."""
    p.text = text.strip()
    p.word_count = count_words(p.text)
    if exceeds_maximum(p.word_count):
        t = thresholds()
        raise HTTPException(
            status_code=422,
            detail=(f"Phrase is too long to read in one take: {p.word_count} words is about "
                    f"{estimated_seconds(p.word_count):g}s, over the {t.long_max_seconds}s maximum "
                    f"({t.long_max_words} words)."),
        )


@router.get("/phrases", response_model=list[PhraseOut])
async def list_phrases(
    q: Optional[str] = Query(None, description="case-insensitive match on phrase text or locale"),
    length: Optional[str] = Query(None, pattern="^(short|medium|long)$"),
    include_inactive: bool = Query(True),
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    query = db.query(Phrase)
    if not include_inactive:
        query = query.filter(Phrase.active.is_(True))
    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(or_(Phrase.text.ilike(like), Phrase.locale.ilike(like)))
    if length:
        lo, hi = word_range_for(PhraseLength(length))
        query = query.filter(Phrase.word_count >= lo, Phrase.word_count <= hi)
    rows = query.order_by(Phrase.text).limit(limit).all()
    counts = dict(
        db.query(VoiceNote.phrase_id, func.count(VoiceNote.id)).group_by(VoiceNote.phrase_id).all()
    )
    return [_phrase_out(p, int(counts.get(p.id, 0))) for p in rows]


@router.post("/phrases", response_model=PhraseOut, status_code=201)
async def create_phrase(body: PhraseCreate, db: Session = Depends(get_db)):
    p = Phrase(locale=body.locale, active=body.active)
    _apply_text(p, body.text)
    db.add(p)
    db.commit()
    db.refresh(p)
    return _phrase_out(p)


@router.patch("/phrases/{phrase_id}", response_model=PhraseOut)
async def update_phrase(phrase_id: str, body: PhraseUpdate, db: Session = Depends(get_db)):
    p = db.get(Phrase, phrase_id)
    if not p:
        raise HTTPException(status_code=404, detail="Phrase not found.")
    if body.text is not None:
        _apply_text(p, body.text)
    if body.locale is not None:
        p.locale = body.locale
    if body.active is not None:
        p.active = body.active
    db.commit()
    db.refresh(p)
    count = db.query(func.count(VoiceNote.id)).filter(VoiceNote.phrase_id == p.id).scalar() or 0
    return _phrase_out(p, int(count))


@router.delete("/phrases/{phrase_id}", status_code=204)
async def delete_phrase(phrase_id: str, db: Session = Depends(get_db)):
    """Delete a phrase that has never been used; otherwise deactivate it.

    Hard-deleting a phrase that voice notes reference would orphan the recording
    from the text it was read against, which the dataset needs.
    """
    p = db.get(Phrase, phrase_id)
    if not p:
        raise HTTPException(status_code=404, detail="Phrase not found.")
    used = db.query(func.count(VoiceNote.id)).filter(VoiceNote.phrase_id == p.id).scalar() or 0
    if used:
        raise HTTPException(
            status_code=409,
            detail=f"{used} voice note(s) reference this phrase. Deactivate it instead of deleting.",
        )
    db.delete(p)
    db.commit()
    return None


class PhraseImportResult(BaseModel):
    added: int
    duplicates: int
    skipped: int
    rows_read: int
    by_length: dict[str, int] = Field(
        default_factory=dict, description="Added phrases per length band."
    )
    details: list[str] = Field(
        default_factory=list,
        description="Per-row reasons for anything not imported (first 50).",
    )


@router.post("/phrases/import", response_model=PhraseImportResult)
async def import_phrases(
    file: UploadFile = File(..., description=".xlsx, .xls or .csv, one phrase per row"),
    db: Session = Depends(get_db),
):
    """Bulk-add phrases from a spreadsheet.

    Column A is the phrase, B an optional locale, C an optional active flag.
    Rows already present in the bank are reported as duplicates rather than
    inserted, so re-uploading a corrected file is safe.
    """
    data = await file.read()
    if len(data) > MAX_IMPORT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File is larger than {MAX_IMPORT_BYTES // (1024 * 1024)}MB.",
        )

    try:
        parsed = parse_phrase_file(file.filename or "", data)
    except PhraseImportError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Compare case-insensitively on collapsed whitespace, the same key the
    # parser uses within a file, so "One  Love" does not slip past "one love".
    existing = {
        " ".join((t or "").lower().split())
        for (t,) in db.query(Phrase.text).all()
    }

    added = duplicates = 0
    details: list[str] = [f"row {row}: {reason}" for row, reason in parsed.skipped]

    by_length: dict[str, int] = {b.value: 0 for b in PhraseLength}
    t = thresholds()

    for item in parsed.phrases:
        key = " ".join(item.text.lower().split())
        if key in existing:
            duplicates += 1
            details.append(f"row {item.row}: already in the phrase bank")
            continue

        words = count_words(item.text)
        if exceeds_maximum(words):
            # Too long to read in one take, so it would only produce rejects.
            details.append(
                f"row {item.row}: too long to read in one take — {words} words is about "
                f"{estimated_seconds(words):g}s, over the {t.long_max_seconds}s maximum"
            )
            continue

        existing.add(key)
        p = Phrase(locale=item.locale, active=item.active, text=item.text, word_count=words)
        db.add(p)
        by_length[band_for_words(words).value] += 1
        added += 1

    if added:
        db.commit()
    logger.info("phrase import from %r: %d added, %d duplicates, %d skipped",
                file.filename, added, duplicates, len(parsed.skipped))

    return PhraseImportResult(
        added=added,
        duplicates=duplicates,
        skipped=len(details) - duplicates,
        rows_read=parsed.rows_read,
        by_length=by_length,
        details=details[:50],
    )


@router.get("/phrases/lengths", response_model=PhraseLengthInfo)
async def phrase_lengths(db: Session = Depends(get_db)):
    """Length bands with their word ranges and how many phrases sit in each.

    Useful for balancing the bank: a dataset of only short prompts trains
    poorly for continuous speech.
    """
    t = thresholds()
    out: list[LengthBandOut] = []
    for band, max_seconds in (
        (PhraseLength.short, t.short_max_seconds),
        (PhraseLength.medium, t.medium_max_seconds),
        (PhraseLength.long, t.long_max_seconds),
    ):
        lo, hi = word_range_for(band)
        count = db.query(func.count(Phrase.id)).filter(
            Phrase.word_count >= lo, Phrase.word_count <= hi
        ).scalar() or 0
        out.append(LengthBandOut(band=band.value, min_words=lo, max_words=hi,
                                 max_seconds=max_seconds, count=int(count)))
    return PhraseLengthInfo(words_per_minute=t.words_per_minute, bands=out)


# ─── Consent records ────────────────────────────────────────────────────
def _consent_out(r: ConsentRecord, u: User) -> ConsentOut:
    return ConsentOut(
        id=r.id, user_id=r.user_id, user_name=u.full_name if u else "—",
        user_email=u.email if u else "—",
        policy_version=r.policy_version,
        channel=r.channel.value if hasattr(r.channel, "value") else str(r.channel),
        evidence=r.evidence, phone=r.phone,
        consented_at=r.consented_at, withdrawn_at=r.withdrawn_at,
        is_active=r.withdrawn_at is None,
    )


@router.get("/consents", response_model=ConsentListOut)
async def list_consents(
    active_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = db.query(ConsentRecord, User).join(User, User.id == ConsentRecord.user_id)
    if active_only:
        query = query.filter(ConsentRecord.withdrawn_at.is_(None))
    total = query.count()
    rows = query.order_by(ConsentRecord.consented_at.desc()).limit(limit).offset(offset).all()
    return ConsentListOut(items=[_consent_out(r, u) for r, u in rows], total=total)


@router.get("/consents/export.csv")
async def export_consents(db: Session = Depends(get_db)):
    """Consent register, in the form it would be handed to the Information Commissioner."""
    rows = (
        db.query(ConsentRecord, User)
        .join(User, User.id == ConsentRecord.user_id)
        .order_by(ConsentRecord.consented_at.desc())
        .all()
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["consent_id", "user_id", "name", "email", "phone", "policy_version",
                "channel", "evidence", "consented_at", "withdrawn_at", "status"])
    for r, u in rows:
        w.writerow([
            r.id, r.user_id, u.full_name, u.email, r.phone or "", r.policy_version,
            r.channel.value if hasattr(r.channel, "value") else r.channel,
            (r.evidence or "").replace("\n", " "),
            r.consented_at.isoformat() if r.consented_at else "",
            r.withdrawn_at.isoformat() if r.withdrawn_at else "",
            "active" if r.withdrawn_at is None else "withdrawn",
        ])
    buf.seek(0)
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="carib-voices-consent-register-{stamp}.csv"'},
    )


# ─── Data subject requests ──────────────────────────────────────────────
class EraseResult(BaseModel):
    user_id: str
    consents_withdrawn: int
    notes_deleted: int
    audio_objects_deleted: int
    note: str


@router.post("/users/{user_id}/erase", response_model=EraseResult)
async def erase_user_data(
    user_id: str,
    admin: User = Depends(get_admin),
    db: Session = Depends(get_db),
):
    """Honour a deletion request: withdraw consent and remove stored recordings.

    Deletes the S3 audio and the voice-note rows, and withdraws consent. The
    user row itself is kept so the consent register stays intact — the Privacy
    Notice commits to producing those records on request. Anything already
    published in a released open dataset cannot be recalled, as the notice says.
    """
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")

    withdrawn = consent_svc.withdraw_consent(db, target, reason=f"erasure requested, actioned by {admin.email}")

    notes = db.query(VoiceNote).filter(VoiceNote.user_id == target.id).all()
    deleted_objects = 0
    for n in notes:
        if n.s3_key:
            try:
                delete_key(n.s3_key)
                deleted_objects += 1
            except Exception as e:  # keep going; the row still goes
                logger.error("could not delete %s for erasure: %s", n.s3_key, e)
        db.delete(n)
    target.pending_phrase_id = None
    db.commit()
    logger.info("admin %s erased data for user %s (%d notes)", admin.email, target.email, len(notes))

    return EraseResult(
        user_id=target.id,
        consents_withdrawn=withdrawn,
        notes_deleted=len(notes),
        audio_objects_deleted=deleted_objects,
        note=("Account retained so the consent register stays auditable. Recordings already "
              "published in a released open dataset cannot be recalled."),
    )


# ─── Rejected voice notes ───────────────────────────────────────────────
# Automatic QC rejects on a word-error-rate threshold, and ASR models trained
# mostly on standard English mis-hear Patois, so correct recordings can be
# rejected. Admins listen to rejected notes here and approve the good ones.
@router.get("/voice-notes/rejected", response_model=VoiceNoteListResponse)
async def list_rejected_notes(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    notes = (
        db.query(VoiceNote)
        .filter(VoiceNote.status == VoiceNoteStatus.rejected)
        .order_by(VoiceNote.created_at.desc())
        .limit(limit)
        .all()
    )
    total = db.query(func.count(VoiceNote.id)).filter(VoiceNote.status == VoiceNoteStatus.rejected).scalar()
    return VoiceNoteListResponse(items=[voice_note_out(n) for n in notes], total=total or 0)


@router.post("/voice-notes/{note_id}/approve", response_model=VoiceNoteOut)
async def approve_rejected_note(
    note_id: str,
    admin: User = Depends(get_admin),
    db: Session = Depends(get_db),
):
    note = db.get(VoiceNote, note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Voice note not found.")
    if note.status != VoiceNoteStatus.rejected:
        raise HTTPException(status_code=409, detail="Only rejected voice notes can be approved here.")

    now = _dt.datetime.now(_dt.timezone.utc)
    qc = dict(note.qc or {})
    # Keep the original verdict so the override is auditable.
    qc["admin_override"] = {
        "from_status": "rejected",
        "from_reason": note.reject_reason,
        "by": admin.id,
        "at": now.isoformat(),
    }
    note.qc = qc
    note.status = VoiceNoteStatus.accepted
    note.reject_reason = None
    note.reviewed_at = now
    note.reviewer_id = admin.id
    db.commit()
    db.refresh(note)
    logger.info("admin %s approved rejected voice note %s", admin.id, note.id)
    return voice_note_out(note)


# ─── Dataset export ─────────────────────────────────────────────────────
def _age_band(dob: Optional[_dt.date]) -> str:
    """Age range, never an exact age — the Privacy Notice only collects a band."""
    if not dob:
        return "unknown"
    today = _dt.date.today()
    years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    for lo, hi in ((18, 24), (25, 34), (35, 44), (45, 54), (55, 64)):
        if lo <= years <= hi:
            return f"{lo}-{hi}"
    return "65+" if years >= 65 else "under-18"


@router.get("/export/dataset")
async def export_dataset(
    fmt: str = Query("jsonl", pattern="^(jsonl|csv)$"),
    status: str = Query("accepted", pattern="^(accepted|all)$"),
    include_internal: bool = Query(
        False,
        description="Include the raw S3 key. Off by default: the key embeds the "
                    "internal user id, which would re-link rows to an account.",
    ),
    db: Session = Depends(get_db),
):
    """De-identified open-dataset export.

    Contains no name, email or phone number. Contributors appear as an opaque
    `speaker_id`, and age is reduced to a band, matching what the Privacy
    Notice says is published.
    """
    query = db.query(VoiceNote, User, Phrase).join(User, User.id == VoiceNote.user_id).outerjoin(
        Phrase, Phrase.id == VoiceNote.phrase_id
    )
    if status == "accepted":
        query = query.filter(VoiceNote.status == VoiceNoteStatus.accepted)
    rows = query.order_by(VoiceNote.created_at).all()

    # Stable pseudonym per contributor, scoped to this dataset.
    speakers: dict[str, str] = {}

    def record(n: VoiceNote, u: User, p: Optional[Phrase]) -> dict:
        if u.id not in speakers:
            speakers[u.id] = f"spk_{len(speakers) + 1:05d}"
        qc = n.qc or {}
        return {
            "id": n.id,
            "speaker_id": speakers[u.id],
            "age_band": _age_band(u.date_of_birth),
            "locale": p.locale if p else "en-JM",
            "phrase": p.text if p else None,
            "transcript": qc.get("transcript"),
            # Publication-safe filename. The real S3 key contains the user id,
            # so it is only included when an admin explicitly asks.
            "audio_filename": f"{speakers[u.id]}/{n.id}.ogg",
            "mime_type": n.mime_type,
            "duration_seconds": n.duration_seconds or qc.get("duration_seconds"),
            "status": n.status.value if hasattr(n.status, "value") else str(n.status),
            "wer": qc.get("wer"),
            "snr_db": qc.get("snr_db"),
            "vad_ratio": qc.get("vad_ratio"),
            "asr_model": qc.get("asr_model"),
            "recorded_at": n.created_at.isoformat() if n.created_at else None,
            **({"audio_key": n.s3_key} if include_internal else {}),
        }

    records = [record(n, u, p) for n, u, p in rows]
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%d")

    if fmt == "csv":
        buf = io.StringIO()
        cols = ["id", "speaker_id", "age_band", "locale", "phrase", "transcript",
                "audio_filename", "mime_type", "duration_seconds", "status", "wer",
                "snr_db", "vad_ratio", "asr_model", "recorded_at"]
        if include_internal:
            cols.append("audio_key")
        w = csv.DictWriter(buf, fieldnames=cols)
        w.writeheader()
        for r in records:
            w.writerow(r)
        body, media, ext = buf.getvalue(), "text/csv", "csv"
    else:
        body = "\n".join(json.dumps(r, ensure_ascii=False) for r in records)
        media, ext = "application/x-ndjson", "jsonl"

    return StreamingResponse(
        iter([body]),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="carib-voices-dataset-{stamp}.{ext}"'},
    )
