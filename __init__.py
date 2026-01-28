import asyncio

from fastapi import APIRouter
from lnbits.tasks import create_permanent_unique_task
from loguru import logger

from .crud import db
from .tasks import cleanup_empty_chats, wait_for_paid_invoices
from .views import chat_generic_router
from .views_api import chat_api_router
from .views_lnurl import chat_lnurl_router

chat_ext: APIRouter = APIRouter(prefix="/chat", tags=["Chat"])
chat_ext.include_router(chat_lnurl_router)
chat_ext.include_router(chat_api_router)
chat_ext.include_router(chat_generic_router)


chat_static_files = [
    {
        "path": "/chat/static",
        "name": "chat_static",
    }
]

scheduled_tasks: list[asyncio.Task] = []


def chat_stop():
    for task in scheduled_tasks:
        try:
            task.cancel()
        except Exception as ex:
            logger.warning(ex)


def chat_start():
    task = create_permanent_unique_task("ext_chat", wait_for_paid_invoices)
    scheduled_tasks.append(task)
    cleanup_task = create_permanent_unique_task("ext_chat_cleanup", cleanup_empty_chats)
    scheduled_tasks.append(cleanup_task)


__all__ = [
    "chat_ext",
    "chat_start",
    "chat_static_files",
    "chat_stop",
    "db",
]
