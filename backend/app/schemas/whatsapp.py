"""WhatsApp webhook payloads (subset we care about)."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class WebhookValue(BaseModel):
    messaging_product: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
    contacts: Optional[list[dict[str, Any]]] = None
    messages: Optional[list[dict[str, Any]]] = None
    statuses: Optional[list[dict[str, Any]]] = None


class WebhookEntry(BaseModel):
    id: Optional[str] = None
    changes: list[dict[str, Any]] = []


class WebhookPayload(BaseModel):
    object: Optional[str] = None
    entry: list[WebhookEntry] = []

