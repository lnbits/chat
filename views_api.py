from http import HTTPStatus

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import HTTPException
from lnbits.core.models import SimpleStatus
from lnbits.core.models.users import AccountId
from lnbits.db import Filters, Page
from lnbits.decorators import check_account_id_exists, optional_user_id, parse_filters
from lnbits.helpers import generate_filter_params_openapi

from .crud import (
    create_categories,
    delete_categories,
    get_categories,
    get_categories_by_id,
    get_categories_ids_by_user,
    get_categories_paginated,
    get_chat,
    get_chat_for_category,
    get_chats_paginated,
    update_categories,
)
from .helpers import chat_lnurl_url, lnurl_encode_chat
from .models import (
    Categories,
    CategoriesFilters,
    ChatMessage,
    ChatPaymentRequest,
    ChatSession,
    ChatsFilters,
    CreateCategories,
    CreateChat,
    CreateChatMessage,
    PublicCategories,
    TipRequest,
)
from .services import (
    create_public_chat,
    get_public_chat,
    mark_chat_resolved,
    mark_chat_seen,
    request_tip,
    send_admin_message,
    send_public_message,
    toggle_chat_claim,
)

categories_filters = parse_filters(CategoriesFilters)
chats_filters = parse_filters(ChatsFilters)

chat_api_router = APIRouter()


############################# Categories #############################
@chat_api_router.post("/api/v1/categories", status_code=HTTPStatus.CREATED)
async def api_create_categories(
    data: CreateCategories,
    account_id: AccountId = Depends(check_account_id_exists),
) -> Categories:
    payload = data.dict()
    if not payload.get("paid"):
        payload["lnurlp"] = False
        payload["claim_split"] = 0
    if payload.get("claim_split") is not None:
        payload["claim_split"] = max(0, min(float(payload["claim_split"]), 90))
    categories = await create_categories(account_id.id, CreateCategories(**payload))
    return categories


@chat_api_router.put("/api/v1/categories/{categories_id}", status_code=HTTPStatus.CREATED)
async def api_update_categories(
    categories_id: str,
    data: CreateCategories,
    account_id: AccountId = Depends(check_account_id_exists),
) -> Categories:
    categories = await get_categories(account_id.id, categories_id)
    if not categories:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Categories not found.")
    if categories.user_id != account_id.id:
        raise HTTPException(HTTPStatus.FORBIDDEN, "You do not own this categories.")
    payload = data.dict()
    if not payload.get("paid"):
        payload["lnurlp"] = False
        payload["claim_split"] = 0
    if payload.get("claim_split") is not None:
        payload["claim_split"] = max(0, min(float(payload["claim_split"]), 90))
    categories = await update_categories(
        Categories(**{**categories.dict(), **payload})
    )
    return categories


@chat_api_router.get(
    "/api/v1/categories/paginated",
    name="Categories List",
    summary="get paginated list of categories",
    response_description="list of categories",
    openapi_extra=generate_filter_params_openapi(CategoriesFilters),
    response_model=Page[Categories],
)
async def api_get_categories_paginated(
    account_id: AccountId = Depends(check_account_id_exists),
    filters: Filters = Depends(categories_filters),
) -> Page[Categories]:

    return await get_categories_paginated(
        user_id=account_id.id,
        filters=filters,
    )


@chat_api_router.get(
    "/api/v1/categories/{categories_id}",
    name="Get Categories",
    summary="Get the categories with this id.",
    response_description="An categories or 404 if not found",
    response_model=Categories,
)
async def api_get_categories(
    categories_id: str,
    account_id: AccountId = Depends(check_account_id_exists),
) -> Categories:

    categories = await get_categories(account_id.id, categories_id)
    if not categories:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Categories not found.")

    return categories


@chat_api_router.get(
    "/api/v1/categories/{categories_id}/public",
    name="Get Public Categories",
    summary="Get the public categories with this id." "This is a public endpoint.",
    response_description="An categories or 404 if not found",
    response_model=PublicCategories,
)
async def api_get_public_categories(categories_id: str) -> PublicCategories:

    categories = await get_categories_by_id(categories_id)
    if not categories:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Categories not found.")

    return PublicCategories(**categories.dict())


@chat_api_router.delete(
    "/api/v1/categories/{categories_id}",
    name="Delete Categories",
    summary="Delete the categories " "and optionally all its associated chats.",
    response_description="The status of the deletion.",
    response_model=SimpleStatus,
)
async def api_delete_categories(
    categories_id: str,
    clear_chats: bool | None = False,
    account_id: AccountId = Depends(check_account_id_exists),
) -> SimpleStatus:

    await delete_categories(account_id.id, categories_id)
    if clear_chats is True:
        # await delete all chats associated with this categories
        pass
    return SimpleStatus(success=True, message="Categories Deleted")


############################# Chats #############################
@chat_api_router.post(
    "/api/v1/chats/{categories_id}/public",
    name="Create Chat",
    summary="Create a new chat for this category (public endpoint).",
    response_description="The created chat.",
    response_model=ChatSession,
    status_code=HTTPStatus.CREATED,
)
async def api_create_public_chat(
    categories_id: str,
    data: CreateChat,
    request: Request,
) -> ChatSession:
    base_url = str(request.base_url)
    try:
        return await create_public_chat(categories_id, data, base_url)
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(exc)) from exc


@chat_api_router.get(
    "/api/v1/chats/{categories_id}/{chat_id}/public",
    name="Get Chat (Public)",
    summary="Get chat history for the public page.",
    response_model=ChatSession,
)
async def api_get_public_chat(categories_id: str, chat_id: str) -> ChatSession:
    try:
        return await get_public_chat(categories_id, chat_id)
    except ValueError as exc:
        raise HTTPException(HTTPStatus.NOT_FOUND, str(exc)) from exc


@chat_api_router.get(
    "/api/v1/chats/{categories_id}/{chat_id}/lnurl",
    name="Get Chat LNURL",
    summary="Get LNURL for chat balance funding.",
)
async def api_get_chat_lnurl(
    categories_id: str, chat_id: str, request: Request
) -> dict:
    chat = await get_chat_for_category(categories_id, chat_id)
    if not chat:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Chat not found.")
    categories = await get_categories_by_id(categories_id)
    if not categories or not categories.paid or not categories.lnurlp:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Chat does not accept balance.")
    return {
        "lnurl": lnurl_encode_chat(request, chat.id),
        "url": chat_lnurl_url(request, chat.id),
    }


@chat_api_router.post(
    "/api/v1/chats/{categories_id}/{chat_id}/public/messages",
    name="Send Message (Public)",
    summary="Send a message to a chat (public endpoint).",
    response_model=ChatPaymentRequest,
)
async def api_send_public_message(
    categories_id: str,
    chat_id: str,
    data: CreateChatMessage,
    request: Request,
    user_id: str | None = Depends(optional_user_id),
) -> ChatPaymentRequest:
    try:
        base_url = str(request.base_url)
        return await send_public_message(categories_id, chat_id, data, user_id=user_id, base_url=base_url)
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(exc)) from exc


@chat_api_router.post(
    "/api/v1/chats/{categories_id}/{chat_id}/public/claim",
    name="Toggle Chat Claim",
    summary="Claim or release a chat (public endpoint, logged-in users only).",
    response_model=ChatSession,
)
async def api_toggle_chat_claim(
    categories_id: str,
    chat_id: str,
    user_id: str | None = Depends(optional_user_id),
) -> ChatSession:
    if not user_id:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, "Login required.")
    chat = await get_chat_for_category(categories_id, chat_id)
    if not chat:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Chat not found.")
    try:
        return await toggle_chat_claim(chat_id, user_id)
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(exc)) from exc


@chat_api_router.post(
    "/api/v1/chats/{categories_id}/{chat_id}/public/tip",
    name="Send Tip (Public)",
    summary="Create a tip invoice for this chat.",
    response_model=ChatPaymentRequest,
)
async def api_send_tip(
    categories_id: str,
    chat_id: str,
    data: TipRequest,
) -> ChatPaymentRequest:
    try:
        return await request_tip(
            categories_id,
            chat_id,
            data.amount,
            data.sender_id,
            data.sender_name,
        )
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(exc)) from exc


@chat_api_router.get(
    "/api/v1/chats/paginated",
    name="Chats List",
    summary="get paginated list of chats",
    response_description="list of chats",
    openapi_extra=generate_filter_params_openapi(ChatsFilters),
    response_model=Page[ChatSession],
)
async def api_get_chats_paginated(
    account_id: AccountId = Depends(check_account_id_exists),
    categories_id: str | None = None,
    filters: Filters = Depends(chats_filters),
) -> Page[ChatSession]:

    categories_ids = await get_categories_ids_by_user(account_id.id)

    if categories_id:
        if categories_id not in categories_ids:
            raise HTTPException(HTTPStatus.FORBIDDEN, "Not your categories.")
        categories_ids = [categories_id]

    return await get_chats_paginated(
        categories_ids=categories_ids,
        filters=filters,
    )


@chat_api_router.get(
    "/api/v1/chats/{chat_id}",
    name="Get Chat (Admin)",
    summary="Get the chat with this id.",
    response_description="A chat or 404 if not found",
    response_model=ChatSession,
)
async def api_get_chat(
    chat_id: str,
    account_id: AccountId = Depends(check_account_id_exists),
) -> ChatSession:
    chat = await get_chat(chat_id)
    if not chat:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Chat not found.")
    categories = await get_categories(account_id.id, chat.categories_id)
    if not categories:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Categories deleted for this chat.")
    return chat


@chat_api_router.post(
    "/api/v1/chats/{chat_id}/messages",
    name="Send Chat Message (Admin)",
    summary="Send a message as admin to this chat.",
    response_model=ChatMessage,
)
async def api_send_admin_message(
    chat_id: str,
    data: CreateChatMessage,
    account_id: AccountId = Depends(check_account_id_exists),
) -> ChatMessage:
    chat = await get_chat(chat_id)
    if not chat:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Chat not found.")
    categories = await get_categories(account_id.id, chat.categories_id)
    if not categories:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Categories deleted for this chat.")
    try:
        return await send_admin_message(chat_id, data)
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(exc)) from exc


@chat_api_router.post(
    "/api/v1/chats/{chat_id}/resolve",
    name="Resolve Chat",
    summary="Mark chat as resolved or unresolved.",
    response_model=ChatSession,
)
async def api_resolve_chat(
    chat_id: str,
    data: dict,
    account_id: AccountId = Depends(check_account_id_exists),
) -> ChatSession:
    chat = await get_chat(chat_id)
    if not chat:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Chat not found.")
    categories = await get_categories(account_id.id, chat.categories_id)
    if not categories:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Categories deleted for this chat.")
    resolved = bool(data.get("resolved", True))
    try:
        return await mark_chat_resolved(chat_id, resolved)
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(exc)) from exc


@chat_api_router.post(
    "/api/v1/chats/{chat_id}/seen",
    name="Mark Chat Seen",
    summary="Mark chat as seen (no longer unread).",
    response_model=ChatSession,
)
async def api_mark_chat_seen(
    chat_id: str,
    account_id: AccountId = Depends(check_account_id_exists),
) -> ChatSession:
    chat = await get_chat(chat_id)
    if not chat:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Chat not found.")
    categories = await get_categories(account_id.id, chat.categories_id)
    if not categories:
        raise HTTPException(HTTPStatus.NOT_FOUND, "Categories deleted for this chat.")
    try:
        return await mark_chat_seen(chat_id)
    except ValueError as exc:
        raise HTTPException(HTTPStatus.BAD_REQUEST, str(exc)) from exc
