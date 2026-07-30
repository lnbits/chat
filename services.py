import json
import math
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from lnbits.core.crud.users import get_user
from lnbits.core.crud.wallets import get_wallets
from lnbits.core.models import Payment
from lnbits.core.services import create_invoice, pay_invoice, websocket_manager
from lnbits.core.services.notifications import (
    send_email_notification,
    send_notification,
    send_telegram_notification,
)
from lnbits.helpers import urlsafe_short_hash
from lnbits.settings import settings
from lnbits.utils.exchange_rates import fiat_amount_as_satoshis
from loguru import logger

from .crud import (
    create_chat,
    create_chat_payment,
    create_notification_job,
    get_categories_by_id,
    get_chat,
    get_chat_for_category,
    get_chat_payment,
    get_due_notification_jobs,
    update_chat,
    update_chat_payment,
    update_notification_job,
)
from .helpers import is_valid_email_address
from .models import (
    Categories,
    ChatMessage,
    ChatNotificationJob,
    ChatParticipant,
    ChatPayment,
    ChatPaymentRequest,
    ChatSession,
    CreateChat,
    CreateChatMessage,
)

MAX_PARTICIPANTS = 10
USER_EMAIL_DELAY_MINUTES = 5
TELEGRAM_REMINDER_DELAY_MINUTES = 2

CHAT_TEMPLATE_DEFAULTS = {
    "admin_after_hours_subject": "New chat message",
    "admin_after_hours_body": (
        "New chat message from {sender_name} ({guest_email})\n\n" "{message}\n\nOpen chat: {chat_url}"
    ),
    "user_new_message_subject": "You have a new chat message",
    "user_new_message_body": ("You have a new reply from {category_name}.\n\n" "{message}\n\nOpen chat: {chat_url}"),
}


def _clean_name(value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    cleaned = value.strip()
    return cleaned if cleaned else fallback


def _serialize_participant(participant: ChatParticipant) -> dict:
    data = participant.dict()
    if participant.joined_at:
        data["joined_at"] = participant.joined_at.isoformat()
    return data


def _serialize_message(message: ChatMessage) -> dict:
    data = message.dict()
    if message.created_at:
        data["created_at"] = message.created_at.isoformat()
    return data


def _message_payload(message: dict) -> dict:
    return {"type": "message", "message": message}


async def _broadcast_chat(chat_id: str, payload: dict) -> None:
    try:
        await websocket_manager.send(f"chat:{chat_id}", json.dumps(payload))
    except Exception as exc:
        logger.warning(f"chat: websocket send failed: {exc}")


async def _broadcast_balance(chat_id: str, balance: int) -> None:
    payload = {"type": "balance", "balance": balance}
    await _broadcast_chat(chat_id, payload)
    await websocket_manager.send(f"chatbalance:{chat_id}", json.dumps(payload))


async def _broadcast_claim(chat_id: str, claimed_by_id: str | None, claimed_by_name: str | None) -> None:
    payload = {
        "type": "claim",
        "claimed_by_name": claimed_by_name,
    }
    await _broadcast_chat(chat_id, payload)


async def _maybe_pay_claim_split(category: Categories, chat: ChatSession, amount: int) -> None:
    if not chat.claimed_by_id:
        return
    split = float(category.claim_split or 0)
    if split <= 0:
        return
    split = max(0.0, min(split, 100.0))
    split_amount = math.floor(amount * (split / 100))
    if split_amount <= 0:
        return
    claimer_wallets = await get_wallets(chat.claimed_by_id)
    if not claimer_wallets:
        return
    category_wallet_id = await _resolve_category_wallet(category)
    if not category_wallet_id:
        return
    try:
        claim_invoice = await create_invoice(
            wallet_id=claimer_wallets[0].id,
            amount=split_amount,
            memo=f"Chat claim split for {category.name}",
            extra={
                "tag": "chat",
                "payment_type": "claim_split",
                "chat_id": chat.id,
                "categories_id": chat.categories_id,
                "claimed_by_id": chat.claimed_by_id,
            },
        )
        await pay_invoice(
            wallet_id=category_wallet_id,
            payment_request=claim_invoice.bolt11,
            max_sat=split_amount,
            description="Chat claim split",
            tag="chat",
        )
    except Exception as exc:
        logger.warning(f"Chat claim split payment failed: {exc}")


def _parse_notify_emails(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [email.strip() for email in raw.split(",") if email.strip()]


def _is_true(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _parse_schedule_days(value: str | list[int] | None) -> list[int]:
    if not value:
        return []
    if isinstance(value, list):
        days = [int(day) for day in value]
        if any(day < 0 or day > 6 for day in days):
            raise ValueError("Schedule days must be between 0 and 6.")
        return sorted(set(days))
    days = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        day = int(item)
        if day < 0 or day > 6:
            raise ValueError("Schedule days must be between 0 and 6.")
        days.append(day)
    return sorted(set(days))


def _schedule_days_to_string(value: str | list[int] | None) -> str:
    if isinstance(value, list):
        return ",".join(str(day) for day in sorted(set(value)))
    return value or "0,1,2,3,4"


def _parse_schedule_time(value: str | None) -> time:
    if not value:
        raise ValueError("Schedule time is required.")
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Schedule time must use HH:MM format.") from exc


def _validate_timezone(value: str | None) -> str:
    timezone_name = (value or "Europe/London").strip() or "Europe/London"
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Unknown schedule timezone.") from exc
    return timezone_name


def normalize_category_schedule_payload(data: dict) -> dict:
    payload = dict(data)
    payload["schedule_enabled"] = _is_true(payload.get("schedule_enabled"))
    payload["schedule_timezone"] = _validate_timezone(payload.get("schedule_timezone"))
    days = _parse_schedule_days(_schedule_days_to_string(payload.get("schedule_days")))
    payload["schedule_days"] = ",".join(str(day) for day in days)
    start = _parse_schedule_time(payload.get("schedule_start") or "09:00")
    end = _parse_schedule_time(payload.get("schedule_end") or "17:00")
    if start >= end:
        raise ValueError("Schedule start must be before schedule end.")
    payload["schedule_start"] = start.strftime("%H:%M")
    payload["schedule_end"] = end.strftime("%H:%M")
    return payload


def _category_template(category: Categories, key: str) -> str:
    value = getattr(category, key, None)
    if value:
        return value
    return CHAT_TEMPLATE_DEFAULTS[key]


def is_chat_available_from_config(
    config: dict[str, str],
    now: datetime | None = None,
) -> bool:
    if not _is_true(config.get("schedule_enabled")):
        return True
    timezone_name = _validate_timezone(config.get("schedule_timezone"))
    tz = ZoneInfo(timezone_name)
    local_now = now.astimezone(tz) if now else datetime.now(tz)
    days = _parse_schedule_days(config.get("schedule_days"))
    if local_now.weekday() not in days:
        return False
    start = _parse_schedule_time(config.get("schedule_start"))
    end = _parse_schedule_time(config.get("schedule_end"))
    return start <= local_now.time() <= end


def get_category_schedule_metadata(category: Categories) -> dict:
    config = {
        "schedule_enabled": "true" if category.schedule_enabled else "false",
        "schedule_timezone": category.schedule_timezone or "Europe/London",
        "schedule_days": category.schedule_days or "0,1,2,3,4",
        "schedule_start": category.schedule_start or "09:00",
        "schedule_end": category.schedule_end or "17:00",
    }
    return {
        "schedule_enabled": _is_true(config.get("schedule_enabled")),
        "schedule_available": is_chat_available_from_config(config),
        "schedule_timezone": config.get("schedule_timezone"),
        "schedule_start": config.get("schedule_start"),
        "schedule_end": config.get("schedule_end"),
        "schedule_days": _parse_schedule_days(config.get("schedule_days")),
    }


async def _resolve_category_wallet(category: Categories) -> str | None:
    if category.wallet:
        return category.wallet
    wallets = await get_wallets(category.user_id)
    return wallets[0].id if wallets else None


def _build_chat_link(base_url: str | None, chat: ChatSession) -> str:
    if base_url:
        return f"{base_url.rstrip('/')}/chat/{chat.categories_id}/{chat.id}"
    if chat.public_url:
        return chat.public_url
    return f"/chat/{chat.categories_id}/{chat.id}"


async def _notify_new_chat(
    category: Categories,
    chat: ChatSession,
    base_url: str | None = None,
    first_message: str | None = None,
) -> None:
    chat_link = _build_chat_link(base_url, chat)
    if first_message:
        message = f'You have a new chat: "{first_message}" {chat_link}'
    else:
        message = f"You have a new chat {chat_link}"
    await send_notification(
        category.notify_telegram,
        [category.notify_nostr] if category.notify_nostr else [],
        _parse_notify_emails(category.notify_email),
        message,
        "chat.new",
    )


async def _notify_chat_reply(
    category: Categories,
    chat: ChatSession,
    message_text: str,
    base_url: str | None = None,
) -> None:
    if not category.guest_notifications:
        return
    nostr = (chat.notify_nostr or "").strip()
    if not nostr:
        return
    chat_link = _build_chat_link(base_url, chat)
    message = f'New reply: "{message_text}" {chat_link}'
    await send_notification(
        None,
        [nostr] if nostr else [],
        [],
        message,
        "chat.reply",
    )


async def _notify_chat_resolved_public(category: Categories, chat: ChatSession) -> None:
    message_text = "This chat has been marked as resolved."
    message = {
        "sender_name": category.name,
        "message": message_text,
    }
    values = _template_values(category, chat, message)
    email = (chat.notify_email or "").strip()
    nostr = (chat.notify_nostr or "").strip()
    if email and settings.lnbits_email_notifications_enabled:
        subject = _render_template(_category_template(category, "user_new_message_subject"), values)
        body = _render_template(_category_template(category, "user_new_message_body"), values)
        await send_email_notification([email], body, subject)
    if nostr and settings.is_nostr_notifications_configured():
        await send_notification(
            None,
            [nostr],
            [],
            f"{message_text} {_build_chat_link(None, chat)}",
            "chat.resolved",
        )


def _render_template(template: str, values: dict[str, str]) -> str:
    class SafeValues(dict):
        def __missing__(self, key):
            return "{" + key + "}"

    return template.format_map(SafeValues(values))


def _message_seen_by_public(chat: ChatSession, message_id: str) -> bool:
    if not chat.public_last_seen_message_id:
        return False
    seen_index = -1
    message_index = -1
    for index, message in enumerate(chat.messages):
        if message.get("id") == chat.public_last_seen_message_id:
            seen_index = index
        if message.get("id") == message_id:
            message_index = index
    return seen_index >= 0 and message_index >= 0 and seen_index >= message_index


def _latest_unanswered_public_message(chat: ChatSession) -> dict | None:
    last_public = None
    last_admin_index = -1
    for index, message in enumerate(chat.messages):
        if message.get("sender_role") == "admin":
            last_admin_index = index
        if message.get("sender_role") == "public":
            last_public = (index, message)
    if not last_public:
        return None
    public_index, public_message = last_public
    if last_admin_index > public_index:
        return None
    return public_message


def _template_values(
    category: Categories,
    chat: ChatSession,
    message: dict,
    base_url: str | None = None,
    guest_email: str | None = None,
) -> dict[str, str]:
    return {
        "category_name": category.name,
        "chat_id": chat.id,
        "chat_url": _build_chat_link(base_url, chat),
        "sender_name": str(message.get("sender_name") or "anon"),
        "guest_email": guest_email or chat.notify_email or "",
        "message": str(message.get("message") or ""),
    }


async def _notify_after_hours_admin(
    category: Categories,
    chat: ChatSession,
    message: ChatMessage,
    base_url: str | None,
) -> None:
    message_dict = _serialize_message(message)
    values = _template_values(category, chat, message_dict, base_url, chat.notify_email)
    subject = _render_template(_category_template(category, "admin_after_hours_subject"), values)
    body = _render_template(_category_template(category, "admin_after_hours_body"), values)
    emails = _parse_notify_emails(category.notify_email)
    if emails:
        await send_email_notification(emails, body, subject)
    if category.notify_telegram and settings.is_telegram_notifications_configured():
        await send_telegram_notification(category.notify_telegram, body)


async def _schedule_user_reply_email(
    category: Categories,
    chat: ChatSession,
    message: ChatMessage,
) -> None:
    if not (chat.notify_email or "").strip():
        return
    await create_notification_job(
        ChatNotificationJob(
            id=urlsafe_short_hash(),
            chat_id=chat.id,
            categories_id=chat.categories_id,
            job_type="user_email",
            message_id=message.id,
            due_at=datetime.now(timezone.utc) + timedelta(minutes=USER_EMAIL_DELAY_MINUTES),
        )
    )


async def _schedule_public_telegram_reminder(
    category: Categories,
    chat: ChatSession,
    message: ChatMessage,
) -> None:
    if not category.notify_telegram:
        return
    config = get_category_schedule_metadata(category)
    if not is_chat_available_from_config(config):
        return
    await create_notification_job(
        ChatNotificationJob(
            id=urlsafe_short_hash(),
            chat_id=chat.id,
            categories_id=chat.categories_id,
            job_type="telegram_reminder",
            message_id=message.id,
            due_at=datetime.now(timezone.utc) + timedelta(minutes=TELEGRAM_REMINDER_DELAY_MINUTES),
        )
    )


async def _prepare_after_hours_email(
    category: Categories,
    chat: ChatSession,
    data: CreateChatMessage,
    user_id: str | None = None,
) -> bool:
    config = get_category_schedule_metadata(category)
    after_hours = data.sender_role == "public" and not user_id and not is_chat_available_from_config(config)
    if not after_hours:
        return False
    email_value = (data.notify_email or "").strip()
    if not email_value:
        raise ValueError("Email address is required outside working hours.")
    if not settings.lnbits_email_notifications_enabled:
        raise ValueError("Email notifications are disabled.")
    if not is_valid_email_address(email_value):
        raise ValueError("Invalid email address.")
    chat.notify_email = email_value
    chat.updated_at = datetime.now(timezone.utc)
    await update_chat(chat)
    return True


async def _prepare_guest_notify_email(chat: ChatSession, data: CreateChatMessage, user_id: str | None = None) -> None:
    if user_id or data.sender_role != "public":
        return
    email_value = (data.notify_email or "").strip()
    if not email_value:
        return
    if not settings.lnbits_email_notifications_enabled:
        raise ValueError("Email notifications are disabled.")
    if not is_valid_email_address(email_value):
        raise ValueError("Invalid email address.")
    if chat.notify_email == email_value:
        return
    chat.notify_email = email_value
    chat.updated_at = datetime.now(timezone.utc)
    await update_chat(chat)


async def _notify_first_paid_message(
    category: Categories,
    chat: ChatSession,
    message: ChatMessage,
) -> None:
    config = get_category_schedule_metadata(category)
    if is_chat_available_from_config(config):
        await _notify_new_chat(category, chat, None, message.message)
    else:
        await _notify_after_hours_admin(category, chat, message, None)


async def create_public_chat(
    categories_id: str,
    data: CreateChat,
    base_url: str,
) -> ChatSession:
    category = await get_categories_by_id(categories_id)
    if not category:
        raise ValueError("Invalid categories ID.")

    participant_id = _clean_name(data.participant_id, urlsafe_short_hash())
    participant_name = _clean_name(data.participant_name, "anon")
    participant = ChatParticipant(
        id=participant_id,
        name=participant_name,
        role="public",
    )

    chat = ChatSession(
        id=urlsafe_short_hash(),
        categories_id=categories_id,
        participants=[_serialize_participant(participant)],
        unread=True,
        last_message_at=None,
        updated_at=datetime.now(timezone.utc),
    )
    chat.public_url = _build_chat_link(base_url, chat)
    await create_chat(categories_id, chat)
    return chat


async def get_public_chat(categories_id: str, chat_id: str) -> ChatSession:
    chat = await get_chat_for_category(categories_id, chat_id)
    if not chat:
        raise ValueError("Chat not found.")
    return _sanitize_public_chat(chat)


def _ensure_participant(chat: ChatSession, sender_id: str, sender_name: str, sender_role: str) -> None:
    normalized_name = (sender_name or "").strip().lower()
    for participant in chat.participants:
        if participant.get("id") == sender_id:
            return
        existing_name = (participant.get("name") or "").strip().lower()
        if normalized_name and existing_name == normalized_name:
            return
    if len(chat.participants) >= MAX_PARTICIPANTS:
        raise ValueError("Chat is full.")
    chat.participants.append(_serialize_participant(ChatParticipant(id=sender_id, name=sender_name, role=sender_role)))


def _sanitize_public_chat(chat: ChatSession) -> ChatSession:
    sanitized = chat.copy(deep=True)
    sanitized.claimed_by_id = None
    sanitized.notify_email = None
    sanitized.notify_nostr = None
    for participant in sanitized.participants:
        if participant.get("role") == "admin":
            name = participant.get("name") or "admin"
            participant["id"] = f"admin-{name}"
    for message in sanitized.messages:
        if message.get("sender_role") == "admin":
            name = message.get("sender_name") or "admin"
            message["sender_id"] = f"admin-{name}"
    return sanitized


async def _append_message(chat: ChatSession, message: ChatMessage, unread: bool) -> ChatSession:
    payload = _serialize_message(message)
    chat.messages.append(payload)
    chat.last_message_at = message.created_at
    chat.unread = unread
    chat.updated_at = datetime.now(timezone.utc)
    await update_chat(chat)
    await _broadcast_chat(chat.id, _message_payload(payload))
    return chat


async def _calculate_amount(category: Categories, message: str) -> int:
    if not category.price_chars:
        return 0
    raw_amount = len(message) * float(category.price_chars)
    if raw_amount <= 0:
        return 0
    if category.denomination and category.denomination != "sat":
        sats = await fiat_amount_as_satoshis(raw_amount, category.denomination)
        return math.ceil(sats)
    return math.ceil(raw_amount)


async def _handle_lnurlp_drawdown(
    category: Categories,
    chat: ChatSession,
    amount: int,
    data: CreateChatMessage,
    sender_name: str,
    base_url: str | None,
    after_hours: bool = False,
) -> ChatPaymentRequest:
    if chat.balance < amount:
        raise ValueError("Insufficient balance. Fund the chat to continue.")
    chat.balance = max(0, chat.balance - amount)
    await _maybe_pay_claim_split(category, chat, amount)
    message = ChatMessage(
        id=urlsafe_short_hash(),
        sender_id=data.sender_id,
        sender_name=sender_name,
        sender_role=data.sender_role,
        message=data.message,
        created_at=datetime.now(timezone.utc),
        amount=amount,
        message_type="message",
    )
    if not chat.messages and not after_hours:
        await _notify_new_chat(category, chat, base_url, data.message)
    await _append_message(chat, message, unread=True)
    if after_hours:
        await _notify_after_hours_admin(category, chat, message, base_url)
    else:
        await _schedule_public_telegram_reminder(category, chat, message)
    await _broadcast_balance(chat.id, chat.balance)
    return ChatPaymentRequest(chat_id=chat.id, pending=False, message_id=message.id)


async def _create_payg_payment_request(
    category: Categories,
    chat: ChatSession,
    amount: int,
    data: CreateChatMessage,
    sender_name: str,
) -> ChatPaymentRequest:
    wallet_id = await _resolve_category_wallet(category)
    if not wallet_id:
        raise ValueError("Category wallet not configured.")
    payment = await create_invoice(
        wallet_id=wallet_id,
        amount=amount,
        memo=f"Chat message for {category.name}",
        extra={
            "tag": "chat",
            "chat_id": chat.id,
            "categories_id": chat.categories_id,
            "sender_id": data.sender_id,
            "sender_name": sender_name,
            "sender_role": data.sender_role,
            "message": data.message,
            "payment_type": "message",
        },
    )
    await create_chat_payment(
        ChatPayment(
            payment_hash=payment.payment_hash,
            chat_id=chat.id,
            categories_id=chat.categories_id,
            sender_id=data.sender_id,
            sender_name=sender_name,
            sender_role=data.sender_role,
            message=data.message,
            amount=amount,
            payment_type="message",
        )
    )
    return ChatPaymentRequest(
        chat_id=chat.id,
        payment_hash=payment.payment_hash,
        payment_request=payment.bolt11,
        amount=amount,
        pending=True,
    )


async def _send_free_message(
    category: Categories,
    chat: ChatSession,
    data: CreateChatMessage,
    sender_name: str,
    base_url: str | None,
    user_id: str | None = None,
    after_hours: bool = False,
) -> ChatPaymentRequest:
    message = ChatMessage(
        id=urlsafe_short_hash(),
        sender_id=data.sender_id,
        sender_name=sender_name,
        sender_role=data.sender_role,
        message=data.message,
        created_at=datetime.now(timezone.utc),
    )
    if not chat.messages and not after_hours:
        await _notify_new_chat(category, chat, base_url, data.message)
    await _append_message(chat, message, unread=True)
    if after_hours:
        await _notify_after_hours_admin(category, chat, message, base_url)
    elif data.sender_role == "public" and not user_id:
        await _schedule_public_telegram_reminder(category, chat, message)
    if user_id:
        await _notify_chat_reply(category, chat, data.message, base_url)
    return ChatPaymentRequest(chat_id=chat.id, pending=False, message_id=message.id)


async def send_public_message(
    categories_id: str,
    chat_id: str,
    data: CreateChatMessage,
    user_id: str | None = None,
    base_url: str | None = None,
) -> ChatPaymentRequest:
    category = await get_categories_by_id(categories_id)
    if not category:
        raise ValueError("Invalid categories ID.")
    chat = await get_chat_for_category(categories_id, chat_id)
    if not chat:
        raise ValueError("Chat not found.")
    if category.chars and len(data.message) > category.chars:
        raise ValueError("Message too long.")

    sender_name = _clean_name(data.sender_name, "anon")
    _ensure_participant(chat, data.sender_id, sender_name, data.sender_role)
    after_hours = await _prepare_after_hours_email(category, chat, data, user_id=user_id)
    if not after_hours:
        await _prepare_guest_notify_email(chat, data, user_id=user_id)

    if user_id and chat.claimed_by_id and chat.claimed_by_id != user_id:
        claimed_name = chat.claimed_by_name or "another user"
        raise ValueError(f"this chat has been claimed by {claimed_name}")

    amount = 0
    if category.paid and not user_id:
        amount = await _calculate_amount(category, data.message)

    if category.paid and category.lnurlp and amount > 0 and not user_id:
        return await _handle_lnurlp_drawdown(
            category,
            chat,
            amount,
            data,
            sender_name,
            base_url,
            after_hours=after_hours,
        )

    if category.paid and amount > 0 and not user_id:
        return await _create_payg_payment_request(category, chat, amount, data, sender_name)

    return await _send_free_message(
        category,
        chat,
        data,
        sender_name,
        base_url,
        user_id=user_id,
        after_hours=after_hours,
    )


async def send_admin_message(
    chat_id: str,
    data: CreateChatMessage,
) -> ChatMessage:
    chat = await get_chat(chat_id)
    if not chat:
        raise ValueError("Chat not found.")
    sender_name = _clean_name(data.sender_name, "support")
    _ensure_participant(chat, data.sender_id, sender_name, "admin")
    message = ChatMessage(
        id=urlsafe_short_hash(),
        sender_id=data.sender_id,
        sender_name=sender_name,
        sender_role="admin",
        message=data.message,
        created_at=datetime.now(timezone.utc),
    )
    await _append_message(chat, message, unread=False)
    category = await get_categories_by_id(chat.categories_id)
    if category:
        await _schedule_user_reply_email(category, chat, message)
        await _notify_chat_reply(category, chat, data.message)
    return message


async def update_chat_notifications(
    categories_id: str,
    chat_id: str,
    email: str | None,
    nostr: str | None,
) -> ChatSession:
    category = await get_categories_by_id(categories_id)
    if not category:
        raise ValueError("Invalid categories ID.")
    if not category.guest_notifications:
        raise ValueError("Guest notifications are disabled for this chat.")

    chat = await get_chat_for_category(categories_id, chat_id)
    if not chat:
        raise ValueError("Chat not found.")

    email_value = (email or "").strip()
    nostr_value = (nostr or "").strip()

    if email_value:
        if not settings.lnbits_email_notifications_enabled:
            raise ValueError("Email notifications are disabled.")
        if not is_valid_email_address(email_value):
            raise ValueError("Invalid email address.")
    if nostr_value:
        if not settings.is_nostr_notifications_configured():
            raise ValueError("Nostr notifications are disabled.")

    chat.notify_email = email_value or None
    chat.notify_nostr = nostr_value or None
    chat.updated_at = datetime.now(timezone.utc)
    await update_chat(chat)
    return chat


async def mark_chat_resolved(chat_id: str, resolved: bool) -> ChatSession:
    chat = await get_chat(chat_id)
    if not chat:
        raise ValueError("Chat not found.")
    chat.resolved = resolved
    chat.updated_at = datetime.now(timezone.utc)
    await update_chat(chat)
    if resolved:
        category = await get_categories_by_id(chat.categories_id)
        if category:
            await _notify_chat_resolved_public(category, chat)
    await _broadcast_chat(chat.id, {"type": "resolved", "resolved": resolved})
    return chat


async def mark_chat_seen(chat_id: str) -> ChatSession:
    chat = await get_chat(chat_id)
    if not chat:
        raise ValueError("Chat not found.")
    if chat.unread:
        chat.unread = False
        chat.updated_at = datetime.now(timezone.utc)
        await update_chat(chat)
        await _broadcast_chat(chat.id, {"type": "seen"})
    return chat


async def mark_public_chat_seen(categories_id: str, chat_id: str) -> ChatSession:
    chat = await get_chat_for_category(categories_id, chat_id)
    if not chat:
        raise ValueError("Chat not found.")
    if chat.messages:
        chat.public_last_seen_message_id = chat.messages[-1].get("id")
        chat.public_last_seen_at = datetime.now(timezone.utc)
        chat.updated_at = datetime.now(timezone.utc)
        await update_chat(chat)
        await _broadcast_chat(
            chat.id,
            {
                "type": "public_seen",
                "message_id": chat.public_last_seen_message_id,
                "seen_at": chat.public_last_seen_at.isoformat(),
            },
        )
    return _sanitize_public_chat(chat)


async def request_tip(
    categories_id: str,
    chat_id: str,
    amount: int,
    sender_id: str,
    sender_name: str,
) -> ChatPaymentRequest:
    if amount <= 0:
        raise ValueError("Tip amount must be positive.")
    category = await get_categories_by_id(categories_id)
    if not category:
        raise ValueError("Invalid categories ID.")
    wallet_id = await _resolve_category_wallet(category)
    if not wallet_id:
        raise ValueError("Category wallet not configured.")

    sender_name = _clean_name(sender_name, "anon")
    payment = await create_invoice(
        wallet_id=wallet_id,
        amount=amount,
        memo=f"Tip for {category.name}",
        extra={
            "tag": "chat",
            "chat_id": chat_id,
            "categories_id": categories_id,
            "sender_id": sender_id,
            "sender_name": sender_name,
            "sender_role": "public",
            "message": f"Tip: {amount} sats",
            "payment_type": "tip",
        },
    )
    await create_chat_payment(
        ChatPayment(
            payment_hash=payment.payment_hash,
            chat_id=chat_id,
            categories_id=categories_id,
            sender_id=sender_id,
            sender_name=sender_name,
            sender_role="public",
            message=f"Tip: {amount} sats",
            amount=amount,
            payment_type="tip",
        )
    )
    return ChatPaymentRequest(
        chat_id=chat_id,
        payment_hash=payment.payment_hash,
        payment_request=payment.bolt11,
        amount=amount,
        pending=True,
    )


async def _apply_balance_payment(chat_id: str | None, amount_sat: int) -> bool:
    if not chat_id:
        logger.warning("Chat balance payment missing chat_id.")
        return False
    chat = await get_chat(chat_id)
    if not chat:
        logger.warning("Chat not found for balance payment.")
        return False
    chat.balance = max(0, chat.balance + amount_sat)
    chat.updated_at = datetime.now(timezone.utc)
    await update_chat(chat)
    await _broadcast_balance(chat.id, chat.balance)
    return True


async def _finalize_chat_payment(chat_payment: ChatPayment) -> bool:
    if chat_payment.paid:
        return True

    chat_payment.paid = True
    await update_chat_payment(chat_payment)

    chat = await get_chat(chat_payment.chat_id)
    if not chat:
        logger.warning("Chat not found for payment.")
        return False

    if chat_payment.payment_type == "balance":
        chat.balance = max(0, chat.balance + chat_payment.amount)
        chat.updated_at = datetime.now(timezone.utc)
        await update_chat(chat)
        await _broadcast_balance(chat.id, chat.balance)
        return True

    message_type = "tip" if chat_payment.payment_type == "tip" else "message"
    if chat_payment.payment_type == "message":
        category = await get_categories_by_id(chat.categories_id)
        if category:
            await _maybe_pay_claim_split(category, chat, chat_payment.amount)
    message = ChatMessage(
        id=urlsafe_short_hash(),
        sender_id=chat_payment.sender_id,
        sender_name=chat_payment.sender_name,
        sender_role=chat_payment.sender_role,
        message=chat_payment.message,
        created_at=datetime.now(timezone.utc),
        amount=chat_payment.amount,
        message_type=message_type,
    )
    if not chat.messages:
        category = await get_categories_by_id(chat.categories_id)
        if category:
            await _notify_first_paid_message(category, chat, message)
    await _append_message(chat, message, unread=True)
    if message.sender_role == "public":
        category = await get_categories_by_id(chat.categories_id)
        if category:
            await _schedule_public_telegram_reminder(category, chat, message)
    return True


async def payment_received_for_client_data(payment: Payment) -> bool:
    if payment.extra.get("tag") != "chat":
        return False

    if payment.extra.get("payment_type") == "balance":
        return await _apply_balance_payment(payment.extra.get("chat_id"), payment.sat)

    chat_payment = await get_chat_payment(payment.payment_hash)
    if not chat_payment:
        logger.warning("Chat payment not found.")
        return False

    return await _finalize_chat_payment(chat_payment)


async def _mark_job(job: ChatNotificationJob, status: str) -> None:
    job.status = status
    job.updated_at = datetime.now(timezone.utc)
    await update_notification_job(job)


async def _process_user_email_job(job: ChatNotificationJob) -> None:
    chat = await get_chat(job.chat_id)
    email = (chat.notify_email or "").strip() if chat else ""
    if not chat or not email:
        await _mark_job(job, "skipped")
        return
    if _message_seen_by_public(chat, job.message_id):
        await _mark_job(job, "skipped")
        return
    category = await get_categories_by_id(job.categories_id)
    if not category:
        await _mark_job(job, "skipped")
        return
    message = next((m for m in chat.messages if m.get("id") == job.message_id), None)
    if not message:
        await _mark_job(job, "skipped")
        return
    values = _template_values(category, chat, message)
    subject = _render_template(_category_template(category, "user_new_message_subject"), values)
    body = _render_template(_category_template(category, "user_new_message_body"), values)
    await send_email_notification([email], body, subject)
    await _mark_job(job, "sent")


async def _process_telegram_reminder_job(job: ChatNotificationJob) -> None:
    chat = await get_chat(job.chat_id)
    category = await get_categories_by_id(job.categories_id)
    if not chat or not category or not category.notify_telegram:
        await _mark_job(job, "skipped")
        return
    config = get_category_schedule_metadata(category)
    if not is_chat_available_from_config(config):
        await _mark_job(job, "skipped")
        return
    latest_public = _latest_unanswered_public_message(chat)
    if not latest_public or latest_public.get("id") != job.message_id:
        await _mark_job(job, "skipped")
        return
    message = (
        f"No response after {TELEGRAM_REMINDER_DELAY_MINUTES} minutes: "
        f'"{latest_public.get("message", "")}" {_build_chat_link(None, chat)}'
    )
    await send_telegram_notification(category.notify_telegram, message)
    await _mark_job(job, "sent")


async def process_due_notification_jobs() -> None:
    jobs = await get_due_notification_jobs(datetime.now(timezone.utc))
    for job in jobs:
        try:
            if job.job_type == "user_email":
                await _process_user_email_job(job)
            elif job.job_type == "telegram_reminder":
                await _process_telegram_reminder_job(job)
            else:
                await _mark_job(job, "skipped")
        except Exception as exc:
            logger.warning(f"chat: notification job failed: {exc}")


async def toggle_chat_claim(chat_id: str, user_id: str) -> ChatSession:
    chat = await get_chat(chat_id)
    if not chat:
        raise ValueError("Chat not found.")

    user = await get_user(user_id)
    if not user:
        raise ValueError("User not found.")

    if chat.claimed_by_id == user_id:
        chat.claimed_by_id = None
        chat.claimed_by_name = None
    else:
        chat.claimed_by_id = user_id
        chat.claimed_by_name = user.username or "user"

    chat.updated_at = datetime.now(timezone.utc)
    await update_chat(chat)
    await _broadcast_claim(chat.id, chat.claimed_by_id, chat.claimed_by_name)
    return chat
