from datetime import datetime, timezone
from enum import Enum

from lnbits.db import FilterModel
from pydantic import BaseModel, Field

DEFAULT_PUBLIC_NOTE = "we aim to reply as soon as possible but it may take up to 24hrs for a reply"


class NostrDmType(str, Enum):
    nip04 = "nip04"
    nip17 = "nip17"
    nip17b = "nip17b"


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
    guest_notifications: bool | None = False
    public_note: str | None = DEFAULT_PUBLIC_NOTE
    persistent_notifications: bool = False
    notify_telegram: str | None = None
    notify_nostr: str | None = None
    notify_nostr_dm_type: NostrDmType = NostrDmType.nip04
    notify_email: str | None = None
    schedule_enabled: bool | None = False
    schedule_timezone: str | None = "Europe/London"
    schedule_days: str | list[int] | None = "0,1,2,3,4"
    schedule_start: str | None = "09:00"
    schedule_end: str | None = "17:00"
    admin_after_hours_subject: str | None = None
    admin_after_hours_body: str | None = None
    user_new_message_subject: str | None = None
    user_new_message_body: str | None = None


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
    guest_notifications: bool | None = False
    public_note: str | None = DEFAULT_PUBLIC_NOTE
    persistent_notifications: bool = False
    notify_telegram: str | None = None
    notify_nostr: str | None = None
    notify_nostr_dm_type: NostrDmType = NostrDmType.nip04
    notify_email: str | None = None
    schedule_enabled: bool | None = False
    schedule_timezone: str | None = "Europe/London"
    schedule_days: str | None = "0,1,2,3,4"
    schedule_start: str | None = "09:00"
    schedule_end: str | None = "17:00"
    admin_after_hours_subject: str | None = None
    admin_after_hours_body: str | None = None
    user_new_message_subject: str | None = None
    user_new_message_body: str | None = None

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
    guest_notifications: bool | None = False
    public_note: str | None = DEFAULT_PUBLIC_NOTE
    notify_email_available: bool | None = False
    notify_nostr_available: bool | None = False
    schedule_enabled: bool | None = False
    schedule_available: bool | None = True
    schedule_timezone: str | None = None
    schedule_start: str | None = None
    schedule_end: str | None = None
    schedule_days: list[int] = Field(default_factory=list)


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
    notify_email: str | None = None
    notify_nostr: str | None = None
    public_last_seen_message_id: str | None = None
    public_last_seen_at: datetime | None = None
    participants: list[dict] = Field(default_factory=list)
    messages: list[dict] = Field(default_factory=list)
    last_message_at: datetime | None = None
    last_admin_notification_at: datetime | None = None

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
    notify_email: str | None = None


class ChatNotifications(BaseModel):
    email: str | None = None
    nostr: str | None = None


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


class ChatNotificationJob(BaseModel):
    id: str
    chat_id: str
    categories_id: str
    job_type: str
    message_id: str
    due_at: datetime
    status: str = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


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
