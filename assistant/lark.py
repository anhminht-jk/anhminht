"""Lark (Larksuite) Open API: email công ty và nhóm chat có bot.

Cần một "Custom App" trong Lark Developer Console với quyền:
  - mail:user_mailbox.message:readonly   (đọc email)
  - im:chat:readonly, im:message:readonly (đọc nhóm chat mà bot được thêm vào)
Biến môi trường: LARK_APP_ID, LARK_APP_SECRET, LARK_MAILBOX (địa chỉ email công ty).
"""
import base64
import json
import os
import re
from datetime import datetime, timezone

from .http import ApiError, request

DOMAIN = os.environ.get("LARK_DOMAIN", "https://open.larksuite.com")


def _ts(ms):
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat()


def decode_body(b64):
    if not b64:
        return ""
    pad = "=" * (-len(b64) % 4)
    return base64.urlsafe_b64decode(b64 + pad).decode("utf-8", errors="replace")


_QUOTE_START = re.compile(r"^(On .+ wrote:|Vào .+ đã viết:|-{2,}\s*Original Message|From: .+)$", re.M)


def strip_quoted(text, limit=3000):
    """Bỏ phần trích dẫn email cũ để tránh lặp nội dung."""
    m = _QUOTE_START.search(text)
    if m:
        text = text[: m.start()]
    text = "\n".join(l for l in text.splitlines() if not l.startswith(">"))
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:limit] + (" …[cắt bớt]" if len(text) > limit else "")


class Lark:
    def __init__(self, app_id=None, app_secret=None):
        self.app_id = app_id or os.environ["LARK_APP_ID"]
        self.app_secret = app_secret or os.environ["LARK_APP_SECRET"]
        self._token = None

    def token(self):
        if not self._token:
            r = request("POST", f"{DOMAIN}/open-apis/auth/v3/tenant_access_token/internal",
                        json_body={"app_id": self.app_id, "app_secret": self.app_secret})
            if r.get("code") != 0:
                raise ApiError(f"Lark auth: {r.get('msg')}")
            self._token = r["tenant_access_token"]
        return self._token

    def get(self, path, params=None):
        r = request("GET", f"{DOMAIN}/open-apis{path}", params=params,
                    headers={"Authorization": f"Bearer {self.token()}"})
        if r.get("code") != 0:
            raise ApiError(f"Lark {path}: [{r.get('code')}] {r.get('msg')}")
        return r.get("data", {})

    # ---------- Email ----------
    def mail(self, mailbox, since, folders=("INBOX", "SENT")):
        """Email từ thời điểm `since` (datetime UTC), mới nhất trước."""
        since_ms = int(since.timestamp() * 1000)
        box = f"/mail/v1/user_mailboxes/{mailbox}"
        for folder in folders:
            page_token, older_streak = None, 0
            while older_streak < 20:
                d = self.get(f"{box}/messages", {"folder_id": folder, "page_size": 20, "page_token": page_token})
                for mid in d.get("items") or []:
                    msg = self.get(f"{box}/messages/{mid}").get("message", {})
                    if int(msg.get("internal_date") or 0) < since_ms:
                        older_streak += 1
                        continue
                    older_streak = 0
                    yield parse_mail(msg, folder)
                if not d.get("has_more"):
                    break
                page_token = d.get("page_token")

    # ---------- Chat ----------
    def chats(self):
        page_token = None
        while True:
            d = self.get("/im/v1/chats", {"page_size": 100, "page_token": page_token})
            yield from d.get("items") or []
            if not d.get("has_more"):
                return
            page_token = d.get("page_token")

    def chat_messages(self, chat_id, since):
        page_token = None
        while True:
            d = self.get("/im/v1/messages", {
                "container_id_type": "chat", "container_id": chat_id,
                "start_time": int(since.timestamp()), "page_size": 50, "page_token": page_token})
            for m in d.get("items") or []:
                yield parse_chat(m)
            if not d.get("has_more"):
                return
            page_token = d.get("page_token")


def _addr(a):
    if not a:
        return ""
    return f"{a.get('name') or ''} <{a.get('mail_address', '')}>".strip()


def parse_mail(msg, folder):
    return {
        "source": "lark_mail",
        "folder": folder,
        "id": msg.get("message_id") or msg.get("smtp_message_id"),
        "thread": msg.get("thread_id"),
        "time": _ts(msg.get("internal_date") or 0),
        "from": _addr(msg.get("head_from")),
        "to": ", ".join(_addr(a) for a in msg.get("to") or []),
        "cc": ", ".join(_addr(a) for a in msg.get("cc") or []),
        "subject": msg.get("subject", ""),
        "text": strip_quoted(decode_body(msg.get("body_plain_text"))),
    }


def chat_text(msg_type, content):
    try:
        c = json.loads(content or "{}")
    except json.JSONDecodeError:
        return content or ""
    if msg_type == "text":
        return c.get("text", "")
    if msg_type == "post":
        body = c.get("content") or next((v.get("content") for v in c.values() if isinstance(v, dict)), [])
        title = c.get("title") or ""
        lines = [" ".join(seg.get("text", "") for seg in line if isinstance(seg, dict)) for line in body or []]
        return "\n".join([title] + lines).strip()
    if msg_type in ("file", "image", "media", "audio"):
        return f"[{msg_type}: {c.get('file_name', '')}]"
    return f"[{msg_type}]"


def parse_chat(m):
    return {
        "source": "lark_chat",
        "id": m.get("message_id"),
        "chat_id": m.get("chat_id"),
        "time": _ts(m.get("create_time") or 0),
        "from": (m.get("sender") or {}).get("id", ""),
        "text": chat_text(m.get("msg_type"), (m.get("body") or {}).get("content")),
    }
