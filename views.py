from fastapi import APIRouter, Depends
from lnbits.core.views.generic import index, index_public
from lnbits.decorators import check_account_exists
from lnbits.helpers import template_renderer

chat_generic_router = APIRouter()


def chat_renderer():
    return template_renderer(["chat/templates"])


chat_generic_router.add_api_route("/", methods=["GET"], endpoint=index, dependencies=[Depends(check_account_exists)])


chat_generic_router.add_api_route("/{categories_id}", methods=["GET"], endpoint=index_public)
chat_generic_router.add_api_route("/{categories_id}/{chat_id}", methods=["GET"], endpoint=index_public)
chat_generic_router.add_api_route("/embed/{categories_id}", methods=["GET"], endpoint=index_public)
chat_generic_router.add_api_route("/embed/{categories_id}/{chat_id}", methods=["GET"], endpoint=index_public)
