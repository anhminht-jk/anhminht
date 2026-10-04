"""Base.vn (Wework, Request, Workflow...) qua External API.

Base gọi API dạng POST https://<app>.base.vn/extapi/<version>/<entity>/<action>
kèm access token v2 trong form (token v1 đã hết hiệu lực sau Q2/2026).
Token v2 tạo theo từng ứng dụng tại account.base.vn > "Tích hợp với bên thứ ba ver 2".
Biến môi trường (chỉ cần quyền đọc):
  BASE_WEWORK_TOKEN   – token cho ứng dụng Wework (dự án, công việc)
  BASE_SERVICE_TOKEN  – token cho ứng dụng Base Service (luồng phê duyệt)
  BASE_ACCESS_TOKEN   – (tuỳ chọn) dùng chung khi app không có token riêng

Danh sách endpoint để trong config.json (mục "base_endpoints") vì mỗi công ty
dùng bộ module Base khác nhau; giá trị mặc định dưới đây cần đối chiếu với
tài liệu API trong trang quản trị Base ở lần chạy thật đầu tiên.
"""
import os
from datetime import datetime, timezone

from .http import ApiError, request

DEFAULT_ENDPOINTS = [
    {"name": "Wework – dự án", "app": "wework", "path": "extapi/v3/project/list"},
    {"name": "Wework – công việc", "app": "wework", "path": "extapi/v3/task/list"},
    {"name": "Service – phê duyệt", "app": "service", "path": "extapi/v1/ticket/list"},
]

# Base trả về dữ liệu dưới các khoá khác nhau tuỳ module
_LIST_KEYS = ("tasks", "projects", "tickets", "requests", "jobs", "data", "items", "list")
_TEXT_FIELDS = ("name", "title", "content", "description", "status", "username", "creator",
                "assignee", "owner", "approvers", "deadline", "since", "last_update", "stage", "priority")


def token_for(app):
    return os.environ.get(f"BASE_{app.upper()}_TOKEN") or os.environ.get("BASE_ACCESS_TOKEN")


def configured():
    return any(token_for(ep["app"]) for ep in DEFAULT_ENDPOINTS)


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

    def collect(self, endpoints=None):
        for ep in endpoints or DEFAULT_ENDPOINTS:
            if not token_for(ep["app"]):
                continue
            page = 0
            while page < 50:
                params = {**ep.get("params", {}), "page": page}
                r = self.call(ep["app"], ep["path"], params)
                rows = extract_rows(r)
                for row in rows:
                    yield to_item(ep["name"], row)
                if not rows or not ep.get("paged", True) or len(rows) < 20:
                    break
                page += 1


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
