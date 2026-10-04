"""Base.vn (Wework, Request, Workflow...) qua External API.

Base gọi API dạng POST https://<app>.base.vn/extapi/<version>/<entity>/<action>
kèm access token v2 trong form (token v1 đã hết hiệu lực sau Q2/2026).
Token v2 tạo theo từng ứng dụng tại account.base.vn > "Tích hợp với bên thứ ba ver 2".
Biến môi trường (chỉ cần quyền đọc):
  BASE_WEWORK_TOKEN   – token cho ứng dụng Wework (dự án, công việc)
  BASE_SERVICE_TOKEN  – token cho ứng dụng Base Service (luồng phê duyệt)
  BASE_ACCESS_TOKEN   – (tuỳ chọn) dùng chung khi app không có token riêng

Wework (đã chạy thật 04/10/2026):
  project/list      -> {"projects": [...], "page", "items_per_page", "is_remain", "total"}
  project/get       -> {"project": {...}} – KHÔNG kèm công việc
  project/get.full  -> {"project", "tasklists", "tasks", "subtasks", "milestones"}
  dept/list         -> {"depts": [...]};  user/tasks cần tham số username.
Lỗi trả về dạng {"code": 0, "message": "access_token_invalid_1"}.
Base Service: chưa tìm được endpoint (mọi đường dẫn extapi/v1..v4 đều 404) –
khai báo trong config.json mục "base_endpoints" khi có tài liệu API.
"""
import os
import re
from datetime import datetime, timezone

from .http import ApiError, request

DEFAULT_ENDPOINTS = [
    # Liệt kê dự án, rồi lấy công việc + việc con từng dự án qua project/get.full
    {"name": "Wework – dự án", "app": "wework", "path": "extapi/v3/project/list",
     "each": {"name": "Wework – công việc", "path": "extapi/v3/project/get.full",
              "keys": ["tasks", "subtasks"]}},
]

# Base trả về dữ liệu dưới các khoá khác nhau tuỳ module
_LIST_KEYS = ("tasks", "projects", "depts", "tickets", "requests", "jobs", "data", "items", "list")
_TEXT_FIELDS = ("name", "title", "content_short", "content", "description", "status", "stage",
                "username", "creator_username", "creator", "assignee", "owners", "owner", "approvers",
                "tasklist", "stats", "complete", "deadline", "stime", "etime", "completed_time",
                "overdue", "urgent", "important", "priority", "result_content", "since", "last_update")
_ZERO = (0, "0", "0.00")  # bỏ các trường rỗng dạng số 0, trừ status/stage


def token_for(app):
    t = os.environ.get(f"BASE_{app.upper()}_TOKEN") or os.environ.get("BASE_ACCESS_TOKEN")
    # hay bị dán nguyên mẫu "<token>" hoặc kèm khoảng trắng
    return t.strip().strip("<>").strip() if t else t


def configured():
    return any(k.startswith("BASE_") and k.endswith("_TOKEN") and v for k, v in os.environ.items())


class Base:
    def __init__(self, token_param=None):
        self.token_param = token_param or os.environ.get("BASE_TOKEN_PARAM", "access_token_v2")

    def call(self, app, path, params=None):
        token = token_for(app)
        if not token:
            raise ApiError(f"thiếu BASE_{app.upper()}_TOKEN")
        form = {self.token_param: token, **(params or {})}
        r = request("POST", f"https://{app}.base.vn/{path}", form=form)
        if str(r.get("code", 1)) not in ("1", "200") and r.get("code") is not None:
            raise ApiError(f"Base {app}/{path}: {r.get('message') or r}")
        return r

    def rows(self, app, path, params=None, paged=True, keys=None):
        page = 0
        while page < 50:
            resp = self.call(app, path, {**(params or {}), "page": page})
            if keys:
                rows = [r for k in keys for r in resp.get(k) or []]
            else:
                rows = extract_rows(resp)
            yield from rows
            more = resp.get("is_remain")
            if not rows or not paged or (more is not None and not more) or (more is None and len(rows) < 20):
                return
            page += 1

    def collect(self, endpoints=None):
        for ep in endpoints or DEFAULT_ENDPOINTS:
            if not token_for(ep["app"]):
                continue
            for row in self.rows(ep["app"], ep["path"], ep.get("params"), ep.get("paged", True)):
                yield to_item(ep["name"], row)
                sub = ep.get("each")
                if sub and row.get("id"):
                    for child in self.rows(ep["app"], sub["path"], {"id": row["id"]}, paged=False,
                                           keys=sub.get("keys")):
                        item = to_item(sub["name"], child)
                        item["subject"] = f"{to_item('', row)['subject']} › {item['subject']}"
                        yield item


def extract_rows(resp):
    for k in _LIST_KEYS:
        v = resp.get(k)
        if isinstance(v, list):
            return v
        if isinstance(v, dict):
            inner = extract_rows(v)
            if inner:
                return inner
    return []


def _fmt(v):
    if isinstance(v, (int, float)) and v > 1_000_000_000:  # epoch giây
        return datetime.fromtimestamp(v, tz=timezone.utc).date().isoformat()
    if isinstance(v, str) and v.isdigit() and len(v) == 10:
        return datetime.fromtimestamp(int(v), tz=timezone.utc).date().isoformat()
    if isinstance(v, list):  # owners/followers: [{"username": ...}]
        return ", ".join(str(x.get("username") or x.get("name") or "") if isinstance(x, dict) else str(x)
                         for x in v)
    if isinstance(v, dict):  # tasklist {"name"}, stats {"total", "overdue"...}
        return v.get("name") or ", ".join(f"{k}={x}" for k, x in v.items() if not isinstance(x, (dict, list)))
    if isinstance(v, str) and "<" in v:
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", v)).strip()
    return v


def to_item(module, row):
    fields = {k: _fmt(row[k]) for k in _TEXT_FIELDS
              if row.get(k) not in (None, "", [], {}) and (k in ("status", "stage") or row[k] not in _ZERO)}
    if "content_short" in fields:
        fields.pop("content", None)
    return {
        "source": "base",
        "module": module,
        "id": str(row.get("id", "")),
        "time": str(fields.get("last_update") or fields.get("since") or ""),
        "subject": str(fields.pop("name", "") or fields.pop("title", "")),
        "text": "; ".join(f"{k}: {v}" for k, v in fields.items())[:1500],
    }
