from datetime import datetime, timezone

from lnbits.db import FilterModel
from pydantic import BaseModel, Field


class CreateCategories(BaseModel):
    name: str
    wallet: str | None = None
    paid: bool | None = False
    lnurlp: bool | None = False
    tips: bool | None = False
    chars: int | None = None
    price_chars: float | None = None
    denomination: str | None = "sat"
    claim_split: float | None = 0
    notify_telegram: str | None = None
    notify_nostr: str | None = None
    notify_email: str | None = None


class Categories(BaseModel):
    id: str
    user_id: str
    name: str
    wallet: str | None = None
    paid: bool | None = False
    lnurlp: bool | None = False
    tips: bool | None = False
    chars: int | None = None
    price_chars: float | None = None
    denomination: str | None = "sat"
    claim_split: float | None = 0
    notify_telegram: str | None = None
    notify_nostr: str | None = None
    notify_email: str | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PublicCategories(BaseModel):
    id: str
    name: str
    paid: bool | None = False
    lnurlp: bool | None = False
    tips: bool | None = False
    chars: int | None = None
    price_chars: float | None = None
    denomination: str | None = "sat"
    claim_split: float | None = 0


class CategoriesFilters(FilterModel):
    __search_fields__ = [
        "name",
        "paid",
        "lnurlp",
        "tips",
        "chars",
        "price_chars",
        "denomination",
        "claim_split",
    ]

    __sort_fields__ = [
        "name",
        "paid",
        "lnurlp",
        "tips",
        "chars",
        "price_chars",
        "denomination",
        "claim_split",
        "created_at",
        "updated_at",
    ]

    created_at: datetime | None
    updated_at: datetime | None


################################# Chats ###########################


class ChatParticipant(BaseModel):
    id: str
    name: str
    role: str
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ChatMessage(BaseModel):
    id: str
    sender_id: str
    sender_name: str
    sender_role: str
    message: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    amount: int | None = None
    message_type: str = "message"


class ChatSession(BaseModel):
    id: str
    categories_id: str
    title: str | None = None
    resolved: bool = False
    unread: bool = True
    public_url: str | None = None
    balance: int = 0
    claimed_by_id: str | None = None
    claimed_by_name: str | None = None
    participants: list[dict] = Field(default_factory=list)
    messages: list[dict] = Field(default_factory=list)
    last_message_at: datetime | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CreateChat(BaseModel):
    participant_id: str | None = None
    participant_name: str | None = None


class CreateChatMessage(BaseModel):
    sender_id: str
    sender_name: str
    sender_role: str
    message: str


class ChatPaymentRequest(BaseModel):
    chat_id: str
    payment_hash: str | None = None
    payment_request: str | None = None
    amount: int | None = None
    pending: bool = False
    message_id: str | None = None


class ChatPayment(BaseModel):
    payment_hash: str
    chat_id: str
    categories_id: str
    sender_id: str
    sender_name: str
    sender_role: str
    message: str
    amount: int
    payment_type: str = "message"
    paid: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TipRequest(BaseModel):
    amount: int
    sender_id: str
    sender_name: str


class ChatsFilters(FilterModel):
    __search_fields__ = [
        "title",
    ]

    __sort_fields__ = [
        "last_message_at",
        "created_at",
        "updated_at",
    ]

    created_at: datetime | None
    updated_at: datetime | None
