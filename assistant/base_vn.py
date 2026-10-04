"""Base.vn (Wework, Request, Workflow...) qua External API.

Base gọi API dạng POST https://<app>.base.vn/extapi/<version>/<entity>/<action>
kèm access token v2 trong form (token v1 đã hết hiệu lực sau Q2/2026).
Token v2 tạo theo từng ứng dụng tại account.base.vn > "Tích hợp với bên thứ ba ver 2".
Biến môi trường (chỉ cần quyền đọc):
  BASE_WEWORK_TOKEN   – token cho ứng dụng Wework (dự án, công việc)
  BASE_SERVICE_TOKEN  – token cho ứng dụng Base Service (luồng phê duyệt)
  BASE_ACCESS_TOKEN   – (tuỳ chọn) dùng chung khi app không có token riêng

Endpoint Wework đã xác minh tồn tại (04/10/2026, gọi thử với token sai trả JSON):
  extapi/v3/project/list, project/get, task/get, dept/list, user/tasks.
Base Service: chưa tìm được endpoint (mọi đường dẫn extapi/v1..v4 đều 404) –
khai báo trong config.json mục "base_endpoints" khi có tài liệu API.
"""
import os
from datetime import datetime, timezone

from .http import ApiError, request

DEFAULT_ENDPOINTS = [
    # Liệt kê dự án, rồi lấy chi tiết (kèm công việc) từng dự án qua project/get
    {"name": "Wework – dự án", "app": "wework", "path": "extapi/v3/project/list",
     "each": {"name": "Wework – công việc", "path": "extapi/v3/project/get"}},
]

# Base trả về dữ liệu dưới các khoá khác nhau tuỳ module
_LIST_KEYS = ("tasks", "projects", "tickets", "requests", "jobs", "data", "items", "list")
_TEXT_FIELDS = ("name", "title", "content", "description", "status", "username", "creator",
                "assignee", "owner", "approvers", "deadline", "since", "last_update", "stage", "priority")


def token_for(app):
    return os.environ.get(f"BASE_{app.upper()}_TOKEN") or os.environ.get("BASE_ACCESS_TOKEN")


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

    def rows(self, app, path, params=None, paged=True):
        page = 0
        while page < 50:
            rows = extract_rows(self.call(app, path, {**(params or {}), "page": page}))
            yield from rows
            if not rows or not paged or len(rows) < 20:
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
                    for child in self.rows(ep["app"], sub["path"], {"id": row["id"]}, paged=False):
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
    return v


def to_item(module, row):
    fields = {k: _fmt(row[k]) for k in _TEXT_FIELDS if row.get(k) not in (None, "", [])}
    return {
        "source": "base",
        "module": module,
        "id": str(row.get("id", "")),
        "time": str(fields.get("last_update") or fields.get("since") or ""),
        "subject": str(fields.pop("name", "") or fields.pop("title", "")),
        "text": "; ".join(f"{k}: {v}" for k, v in fields.items())[:1500],
    }
