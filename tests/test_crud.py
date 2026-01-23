from uuid import uuid4

import pytest

from chat.crud import (  # type: ignore[import]
    create_categories,
    delete_categories,
    get_categories,
    get_categories_by_id,
    get_categories_ids_by_user,
    get_categories_paginated,
    update_categories,
)
from chat.models import (  # type: ignore[import]
    Categories,
    CreateCategories,
)


@pytest.mark.asyncio
async def test_create_and_get_categories():
    user_id = uuid4().hex

    data = CreateCategories(
        name="name_AwqF6ginw2mCnHfLCbEk7D",
        paid=False,
        tips=False,
        chars=39,
        price_chars=78.00288769676463,
        denomination="sat",
    )
    categories_one = await create_categories(user_id, data)
    assert categories_one.id is not None
    assert categories_one.user_id == user_id

    categories_one = await get_categories(user_id, categories_one.id)
    assert categories_one.id is not None
    assert categories_one.user_id == user_id
    assert categories_one.name == data.name
    assert categories_one.paid == data.paid
    assert categories_one.tips == data.tips
    assert categories_one.chars == data.chars
    assert categories_one.price_chars == data.price_chars
    assert categories_one.denomination == data.denomination

    data = CreateCategories(
        name="name_AwqF6ginw2mCnHfLCbEk7D",
        paid=False,
        tips=False,
        chars=39,
        price_chars=78.00288769676463,
        denomination="sat",
    )
    categories_two = await create_categories(user_id, data)
    assert categories_two.id is not None
    assert categories_two.user_id == user_id

    categories_list = await get_categories_ids_by_user(user_id=user_id)
    assert len(categories_list) == 2

    categories_page = await get_categories_paginated(user_id=user_id)
    assert categories_page.total == 2
    assert len(categories_page.data) == 2

    await delete_categories(user_id, categories_one.id)
    categories_list = await get_categories_ids_by_user(user_id=user_id)
    assert len(categories_list) == 1

    categories_page = await get_categories_paginated(user_id=user_id)
    assert categories_page.total == 1
    assert len(categories_page.data) == 1


@pytest.mark.asyncio
async def test_update_categories():
    user_id = uuid4().hex

    data = CreateCategories(
        name="name_AwqF6ginw2mCnHfLCbEk7D",
        paid=False,
        tips=False,
        chars=39,
        price_chars=78.00288769676463,
        denomination="sat",
    )
    categories_one = await create_categories(user_id, data)
    assert categories_one.id is not None
    assert categories_one.user_id == user_id

    categories_one = await get_categories(user_id, categories_one.id)
    assert categories_one.id is not None
    assert categories_one.user_id == user_id
    assert categories_one.name == data.name
    assert categories_one.paid == data.paid
    assert categories_one.tips == data.tips
    assert categories_one.chars == data.chars
    assert categories_one.price_chars == data.price_chars
    assert categories_one.denomination == data.denomination

    data_updated = CreateCategories(
        name="name_AwqF6ginw2mCnHfLCbEk7D",
        paid=False,
        tips=False,
        chars=39,
        price_chars=78.00288769676463,
        denomination="sat",
    )
    categories_updated = Categories(**{**categories_one.dict(), **data_updated.dict()})

    await update_categories(categories_updated)
    categories_one = await get_categories_by_id(categories_one.id)
    assert categories_one.name == categories_updated.name
    assert categories_one.paid == categories_updated.paid
    assert categories_one.tips == categories_updated.tips
    assert categories_one.chars == categories_updated.chars
    assert categories_one.price_chars == categories_updated.price_chars
    assert categories_one.denomination == categories_updated.denomination
