from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from lnbits.helpers import urlsafe_short_hash

from chat.crud import (  # type: ignore[import]
    create_categories,
    create_chat,
    create_notification_job,
    get_notification_job,
)
from chat.models import (  # type: ignore[import]
    ChatNotificationJob,
    ChatSession,
    CreateCategories,
)
from chat.services import (  # type: ignore[import]
    CHAT_TEMPLATE_DEFAULTS,
    _render_template,
    get_category_schedule_metadata,
    is_chat_available_from_config,
    process_due_notification_jobs,
)


@pytest.mark.asyncio
async def test_template_defaults_are_available():
    assert CHAT_TEMPLATE_DEFAULTS["admin_after_hours_subject"] == "New chat message"
    assert CHAT_TEMPLATE_DEFAULTS["user_new_message_subject"] == "You have a new chat message"


def test_schedule_evaluation_with_timezone_and_days():
    config = {
        "schedule_enabled": "true",
        "schedule_timezone": "Europe/London",
        "schedule_days": "0,1,2,3,4",
        "schedule_start": "09:00",
        "schedule_end": "17:00",
    }

    monday_midday = datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc)
    monday_evening = datetime(2026, 7, 6, 18, 0, tzinfo=timezone.utc)
    saturday_midday = datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc)

    assert is_chat_available_from_config(config, monday_midday)
    assert not is_chat_available_from_config(config, monday_evening)
    assert not is_chat_available_from_config(config, saturday_midday)


@pytest.mark.asyncio
async def test_category_schedule_metadata():
    category = await create_categories(
        uuid4().hex,
        CreateCategories(
            name=f"category-{urlsafe_short_hash()}",
            schedule_enabled=True,
            schedule_timezone="Europe/London",
            schedule_days="0,1,2",
            schedule_start="08:00",
            schedule_end="12:00",
        ),
    )

    metadata = get_category_schedule_metadata(category)

    assert metadata["schedule_enabled"] is True
    assert metadata["schedule_timezone"] == "Europe/London"
    assert metadata["schedule_days"] == [0, 1, 2]


def test_template_rendering_keeps_unknown_placeholders():
    rendered = _render_template(
        "Hello {sender_name}, keep {unknown}",
        {"sender_name": "Alice"},
    )

    assert rendered == "Hello Alice, keep {unknown}"


async def _create_chat_with_admin_message(seen: bool) -> tuple[str, str, str]:
    category = await create_categories(
        uuid4().hex,
        CreateCategories(name=f"category-{urlsafe_short_hash()}"),
    )
    message_id = urlsafe_short_hash()
    chat = ChatSession(
        id=urlsafe_short_hash(),
        categories_id=category.id,
        notify_email="guest@example.com",
        public_last_seen_message_id=message_id if seen else None,
        messages=[
            {
                "id": message_id,
                "sender_id": "admin-support",
                "sender_name": "support",
                "sender_role": "admin",
                "message": "Reply",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
    )
    await create_chat(category.id, chat)
    return category.id, chat.id, message_id


@pytest.mark.asyncio
async def test_user_email_job_skips_seen_message(monkeypatch):
    category_id, chat_id, message_id = await _create_chat_with_admin_message(True)
    sent = []

    async def fake_send_email(to_emails, message, subject):
        sent.append((to_emails, message, subject))

    monkeypatch.setattr("chat.services.send_email_notification", fake_send_email)
    job = await create_notification_job(
        ChatNotificationJob(
            id=urlsafe_short_hash(),
            chat_id=chat_id,
            categories_id=category_id,
            job_type="user_email",
            message_id=message_id,
            due_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
    )

    await process_due_notification_jobs()
    saved = await get_notification_job(job.id)

    assert sent == []
    assert saved
    assert saved.status == "skipped"


@pytest.mark.asyncio
async def test_user_email_job_sends_unseen_message(monkeypatch):
    category_id, chat_id, message_id = await _create_chat_with_admin_message(False)
    sent = []

    async def fake_send_email(to_emails, message, subject):
        sent.append((to_emails, message, subject))

    monkeypatch.setattr("chat.services.send_email_notification", fake_send_email)
    job = await create_notification_job(
        ChatNotificationJob(
            id=urlsafe_short_hash(),
            chat_id=chat_id,
            categories_id=category_id,
            job_type="user_email",
            message_id=message_id,
            due_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        )
    )

    await process_due_notification_jobs()
    saved = await get_notification_job(job.id)

    assert sent
    assert sent[0][0] == ["guest@example.com"]
    assert saved
    assert saved.status == "sent"
