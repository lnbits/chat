import re

from fastapi import Request
from lnurl import encode as lnurl_encode


def is_valid_email_address(email: str) -> bool:
    email_regex = r"[A-Za-z0-9\._%+-]+@[A-Za-z0-9\.-]+\.[A-Za-z]{2,63}"
    return re.fullmatch(email_regex, email) is not None


def chat_lnurl_url(req: Request, chat_id: str) -> str:
    url = req.url_for("chat.api_lnurl_response", chat_id=chat_id)
    url = url.replace(path=url.path)
    url_str = str(url)
    if url.netloc.endswith(".onion"):
        url_str = url_str.replace("https://", "http://")
    return url_str


def lnurl_encode_chat(req: Request, chat_id: str) -> str:
    return str(lnurl_encode(chat_lnurl_url(req, chat_id)).bech32)
