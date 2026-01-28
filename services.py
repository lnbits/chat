import json
import math
from datetime import datetime, timezone

from lnbits.core.crud.users import get_user
from lnbits.core.crud.wallets import get_wallets
from lnbits.core.models import Payment
from lnbits.core.services import create_invoice, pay_invoice, websocket_manager
from lnbits.core.services.notifications import send_notification
from lnbits.helpers import urlsafe_short_hash
from lnbits.utils.exchange_rates import fiat_amount_as_satoshis
from loguru import logger

from .crud import (
    create_chat,
    create_chat_payment,
    get_categories_by_id,
    get_chat,
    get_chat_for_category,
    get_chat_payment,
    update_chat,
    update_chat_payment,
)
from .models import (
    Categories,
    ChatMessage,
    ChatParticipant,
    ChatPayment,
    ChatPaymentRequest,
    ChatSession,
    CreateChat,
    CreateChatMessage,
)

MAX_PARTICIPANTS = 10


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
        "claimed_by_id": claimed_by_id,
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
    return chat


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
    if not chat.messages:
        await _notify_new_chat(category, chat, base_url, data.message)
    await _append_message(chat, message, unread=True)
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
) -> ChatPaymentRequest:
    message = ChatMessage(
        id=urlsafe_short_hash(),
        sender_id=data.sender_id,
        sender_name=sender_name,
        sender_role=data.sender_role,
        message=data.message,
        created_at=datetime.now(timezone.utc),
    )
    if not chat.messages:
        await _notify_new_chat(category, chat, base_url, data.message)
    await _append_message(chat, message, unread=True)
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

    if user_id and chat.claimed_by_id and chat.claimed_by_id != user_id:
        claimed_name = chat.claimed_by_name or "another user"
        raise ValueError(f"this chat has been claimed by {claimed_name}")

    amount = 0
    if category.paid and not user_id:
        amount = await _calculate_amount(category, data.message)

    if category.paid and category.lnurlp and amount > 0 and not user_id:
        return await _handle_lnurlp_drawdown(category, chat, amount, data, sender_name, base_url)

    if category.paid and amount > 0 and not user_id:
        return await _create_payg_payment_request(category, chat, amount, data, sender_name)

    return await _send_free_message(category, chat, data, sender_name, base_url)


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
    return message


async def mark_chat_resolved(chat_id: str, resolved: bool) -> ChatSession:
    chat = await get_chat(chat_id)
    if not chat:
        raise ValueError("Chat not found.")
    chat.resolved = resolved
    chat.updated_at = datetime.now(timezone.utc)
    await update_chat(chat)
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
            await _notify_new_chat(category, chat, None, chat_payment.message)
    await _append_message(chat, message, unread=True)
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
