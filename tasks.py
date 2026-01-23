import asyncio
from datetime import datetime, timedelta, timezone

from lnbits.core.models import Payment
from lnbits.settings import settings
from lnbits.tasks import register_invoice_listener
from loguru import logger

from .crud import delete_empty_chats_before
from .services import payment_received_for_client_data


async def wait_for_paid_invoices():
    invoice_queue = asyncio.Queue()
    register_invoice_listener(invoice_queue, "ext_chat")
    while True:
        payment = await invoice_queue.get()
        await on_invoice_paid(payment)


async def on_invoice_paid(payment: Payment) -> None:
    if payment.extra.get("tag") != "chat":
        return

    logger.info(f"Invoice paid for chat: {payment.payment_hash}")

    try:
        await payment_received_for_client_data(payment)
    except Exception as e:
        logger.error(f"Error processing payment for chat: {e}")


async def cleanup_empty_chats() -> None:
    while settings.lnbits_running:
        cutoff = int((datetime.now(timezone.utc) - timedelta(minutes=20)).timestamp())
        try:
            await delete_empty_chats_before(cutoff)
        except Exception as e:
            logger.warning(f"Error cleaning empty chats: {e}")
        await asyncio.sleep(60)
