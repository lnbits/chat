from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from chat.crud import (  # type: ignore[import]
    create_categories,
    create_chat,
    get_categories_by_id,
    get_chat,
)
from chat.models import ChatMessage, ChatSession, CreateCategories  # type: ignore[import]
from chat.services import _append_message  # type: ignore[import]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "enabled,elapsed,replied,sender,message_type,resolved,expected",
    [
        (True, 899, False, "guest", "message", False, 0),
        (True, 900, False, "guest", "message", False, 1),
        (True, 1800, False, "guest", "message", False, 1),
        (False, 1800, False, "guest", "message", False, 0),
        (True, 1800, True, "guest", "message", False, 0),
        (True, 1800, False, "other", "message", False, 0),
        (True, 1800, False, "guest", "tip", False, 0),
        (True, 1800, False, "guest", "message", True, 0),
    ],
)
async def test_persistent_notification(
    monkeypatch, enabled, elapsed, replied, sender, message_type, resolved, expected
):
    notify = AsyncMock()
    monkeypatch.setattr("chat.services.send_notification", notify)
    monkeypatch.setattr("chat.services._broadcast_chat", AsyncMock())
    category = await create_categories(
        uuid4().hex,
        CreateCategories(name="Support", persistent_notifications=enabled, notify_email="support@example.com"),
    )
    saved_category = await get_categories_by_id(category.id)
    assert saved_category.persistent_notifications == enabled
    now = datetime.now(timezone.utc)
    initial = now - timedelta(seconds=elapsed)
    messages = [
        {
            "id": "first",
            "sender_id": "guest",
            "sender_role": "public",
            "message": "Hello",
            "created_at": initial.isoformat(),
        }
    ]
    if replied:
        messages.append({"id": "reply", "sender_id": "support", "sender_role": "admin", "message": "Hi"})
    chat = ChatSession(
        id=uuid4().hex,
        categories_id=category.id,
        messages=messages,
        last_admin_notification_at=initial,
        resolved=resolved,
    )
    await create_chat(category.id, chat)
    message = ChatMessage(
        id=uuid4().hex,
        sender_id=sender,
        sender_name=sender,
        sender_role="public",
        message="Anyone there?",
        message_type=message_type,
        created_at=now,
    )
    await _append_message(chat, message, unread=True)
    assert notify.await_count == expected
    saved = await get_chat(chat.id)
    assert saved is not None
    if expected:
        assert abs((saved.last_admin_notification_at.replace(tzinfo=timezone.utc) - now).total_seconds()) < 1
        assert notify.call_args.args[2] == ["support@example.com"]
        assert "Anyone there?" in notify.call_args.args[3]
        # A further message inside the cooldown must not send another reminder,
        # including after loading the chat back from the database.
        message.id = uuid4().hex
        message.created_at = now + timedelta(minutes=1)
        await _append_message(saved, message, unread=True)
        assert notify.await_count == 1
        message.id = uuid4().hex
        message.created_at = now + timedelta(minutes=15)
        await _append_message(saved, message, unread=True)
        assert notify.await_count == 2
