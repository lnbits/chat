import json
from http import HTTPStatus

from fastapi import APIRouter, HTTPException, Query, Request
from lnbits.core.services import create_invoice
from lnbits.settings import settings
from lnurl import (
    CallbackUrl,
    LightningInvoice,
    LnurlErrorResponse,
    LnurlPayActionResponse,
    LnurlPayMetadata,
    LnurlPayResponse,
    MilliSatoshi,
)
from pydantic import parse_obj_as

from .crud import get_categories_by_id, get_chat
from .services import _resolve_category_wallet

chat_lnurl_router = APIRouter()


def _chat_lnurl_limits_msat() -> tuple[int, int]:
    minimum = 1_000
    maximum = settings.lnbits_max_incoming_payment_amount_sats * 1000
    return minimum, maximum


@chat_lnurl_router.get(
    "/api/v1/lnurl/cb/{chat_id}",
    status_code=HTTPStatus.OK,
    name="chat.api_lnurl_callback",
)
async def api_lnurl_callback(
    request: Request,
    chat_id: str,
    amount: int = Query(...),
) -> LnurlErrorResponse | LnurlPayActionResponse:
    chat = await get_chat(chat_id)
    if not chat:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Chat does not exist."
        )
    category = await get_categories_by_id(chat.categories_id)
    if not category or not category.paid or not category.lnurlp:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Chat does not accept balance."
        )

    minimum, maximum = _chat_lnurl_limits_msat()
    if amount < minimum:
        return LnurlErrorResponse(
            reason=f"Amount {amount} is smaller than minimum {minimum}."
        )
    if amount > maximum:
        return LnurlErrorResponse(
            reason=f"Amount {amount} is greater than maximum {maximum}."
        )

    wallet_id = await _resolve_category_wallet(category)
    if not wallet_id:
        return LnurlErrorResponse(reason="Category wallet not configured.")

    amount_sat = int(amount / 1000)
    payment = await create_invoice(
        wallet_id=wallet_id,
        amount=amount_sat,
        memo=f"Chat balance for {category.name}",
        extra={
            "tag": "chat",
            "payment_type": "balance",
            "chat_id": chat.id,
            "categories_id": chat.categories_id,
        },
    )
    invoice = parse_obj_as(LightningInvoice, LightningInvoice(payment.bolt11))
    return LnurlPayActionResponse(pr=invoice, disposable=False)


@chat_lnurl_router.get(
    "/lnurl/{chat_id}",
    name="chat.api_lnurl_response",
)
async def api_lnurl_response(request: Request, chat_id: str) -> LnurlPayResponse:
    chat = await get_chat(chat_id)
    if not chat:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Chat does not exist."
        )
    category = await get_categories_by_id(chat.categories_id)
    if not category or not category.paid or not category.lnurlp:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, detail="Chat does not accept balance."
        )

    url = request.url_for("chat.api_lnurl_callback", chat_id=chat.id)
    callback_url = parse_obj_as(CallbackUrl, str(url))

    metadata = LnurlPayMetadata(
        json.dumps([["text/plain", f"Chat balance for {category.name}"]])
    )
    minimum, maximum = _chat_lnurl_limits_msat()

    return LnurlPayResponse(
        callback=callback_url,
        minSendable=MilliSatoshi(minimum),
        maxSendable=MilliSatoshi(maximum),
        metadata=metadata,
    )
