from lnbits.db import DB_TYPE, POSTGRES, SQLITE, Database, Filters, Page
from lnbits.helpers import urlsafe_short_hash

from .models import (
    Categories,
    CategoriesFilters,
    ChatPayment,
    ChatSession,
    ChatsFilters,
    CreateCategories,
)

db = Database("ext_chat")


########################### Categories ############################
async def create_categories(user_id: str, data: CreateCategories) -> Categories:
    categories = Categories(**data.dict(), id=urlsafe_short_hash(), user_id=user_id)
    await db.insert("chat.categories", categories)
    return categories


async def get_categories(
    user_id: str,
    categories_id: str,
) -> Categories | None:
    return await db.fetchone(
        """
            SELECT * FROM chat.categories
            WHERE id = :id AND user_id = :user_id
        """,
        {"id": categories_id, "user_id": user_id},
        Categories,
    )


async def get_categories_by_id(
    categories_id: str,
) -> Categories | None:
    return await db.fetchone(
        """
            SELECT * FROM chat.categories
            WHERE id = :id
        """,
        {"id": categories_id},
        Categories,
    )


async def get_categories_ids_by_user(
    user_id: str,
) -> list[str]:
    rows: list[dict] = await db.fetchall(
        """
            SELECT DISTINCT id FROM chat.categories
            WHERE user_id = :user_id
        """,
        {"user_id": user_id},
    )

    return [row["id"] for row in rows]


async def get_categories_paginated(
    user_id: str | None = None,
    filters: Filters[CategoriesFilters] | None = None,
) -> Page[Categories]:
    where = []
    values = {}
    if user_id:
        where.append("user_id = :user_id")
        values["user_id"] = user_id

    return await db.fetch_page(
        "SELECT * FROM chat.categories",
        where=where,
        values=values,
        filters=filters,
        model=Categories,
    )


async def update_categories(data: Categories) -> Categories:
    await db.update("chat.categories", data)
    return data


async def delete_categories(user_id: str, categories_id: str) -> None:
    await db.execute(
        """
            DELETE FROM chat.categories
            WHERE id = :id AND user_id = :user_id
        """,
        {"id": categories_id, "user_id": user_id},
    )


################################# Chats ###########################


async def create_chat(categories_id: str, chat: ChatSession) -> ChatSession:
    await db.insert("chat.chats", chat)
    return chat


async def get_chat(chat_id: str) -> ChatSession | None:
    return await db.fetchone(
        """
            SELECT * FROM chat.chats
            WHERE id = :id
        """,
        {"id": chat_id},
        ChatSession,
    )


async def get_chat_for_category(categories_id: str, chat_id: str) -> ChatSession | None:
    return await db.fetchone(
        """
            SELECT * FROM chat.chats
            WHERE id = :id AND categories_id = :categories_id
        """,
        {"id": chat_id, "categories_id": categories_id},
        ChatSession,
    )


async def get_chats_paginated(
    categories_ids: list[str] | None = None,
    filters: Filters[ChatsFilters] | None = None,
) -> Page[ChatSession]:

    if not categories_ids:
        return Page(data=[], total=0)

    where = []
    values = {}
    id_clause = []
    for i, item_id in enumerate(categories_ids):
        categories_id = f"categories_id__{i}"
        id_clause.append(f"categories_id = :{categories_id}")
        values[categories_id] = item_id
    or_clause = " OR ".join(id_clause)
    where.append(f"({or_clause})")

    return await db.fetch_page(
        "SELECT * FROM chat.chats",
        where=where,
        values=values,
        filters=filters,
        model=ChatSession,
    )


async def update_chat(chat: ChatSession) -> ChatSession:
    await db.update("chat.chats", chat)
    return chat


async def delete_chat(categories_id: str, chat_id: str) -> None:
    await db.execute(
        """
            DELETE FROM chat.chats
            WHERE id = :id AND categories_id = :categories_id
        """,
        {"id": chat_id, "categories_id": categories_id},
    )


################################# Chat Payments ###########################


async def create_chat_payment(payment: ChatPayment) -> ChatPayment:
    await db.insert("chat.chat_payments", payment)
    return payment


async def get_chat_payment(payment_hash: str) -> ChatPayment | None:
    return await db.fetchone(
        """
            SELECT * FROM chat.chat_payments
            WHERE payment_hash = :payment_hash
        """,
        {"payment_hash": payment_hash},
        ChatPayment,
    )


async def update_chat_payment(payment: ChatPayment) -> ChatPayment:
    await db.update("chat.chat_payments", payment, where="WHERE payment_hash = :payment_hash")
    return payment


async def delete_empty_chats_before(cutoff: int) -> None:
    if DB_TYPE == SQLITE:
        query = """
            DELETE FROM chat.chats
            WHERE (messages IS NULL OR messages = '[]')
              AND created_at < :cutoff
        """
    elif DB_TYPE == POSTGRES:
        query = """
            DELETE FROM chat.chats
            WHERE (messages IS NULL OR messages = '[]')
              AND created_at < to_timestamp(:cutoff)
        """
    else:
        query = """
            DELETE FROM chat.chats
            WHERE (messages IS NULL OR messages = '[]')
              AND created_at < cast(:cutoff AS timestamp)
        """
    await db.execute(query, {"cutoff": cutoff})
