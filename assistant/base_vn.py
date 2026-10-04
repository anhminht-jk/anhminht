"""Base.vn (Wework, Request, Workflow...) qua External API.

Base gọi API dạng POST https://<app>.base.vn/extapi/<version>/<entity>/<action>
kèm access token trong form. Token tạo tại: Base Account > Tích hợp/API.
Biến môi trường: BASE_ACCESS_TOKEN (chỉ cần quyền đọc).

Danh sách endpoint để trong config.json (mục "base_endpoints") vì mỗi công ty
dùng bộ module Base khác nhau; giá trị mặc định dưới đây cần đối chiếu với
tài liệu API trong trang quản trị Base ở lần chạy thật đầu tiên.
"""
import os
from datetime import datetime, timezone

from .http import ApiError, request

DEFAULT_ENDPOINTS = [
    {"name": "Wework – dự án", "app": "wework", "path": "extapi/v3/project/list"},
    {"name": "Wework – công việc", "app": "wework", "path": "extapi/v3/task/list",
     "params": {"status": "active"}},
    {"name": "Request – đề xuất", "app": "request", "path": "extapi/v1/request/list"},
    {"name": "Workflow – quy trình", "app": "workflow", "path": "extapi/v1/jobs/get"},
]

# Base trả về dữ liệu dưới các khoá khác nhau tuỳ module
_LIST_KEYS = ("tasks", "projects", "requests", "jobs", "data", "items", "list")
_TEXT_FIELDS = ("name", "title", "content", "description", "status", "username", "creator",
                "assignee", "owner", "deadline", "since", "last_update", "stage", "priority")


class Base:
    def __init__(self, token=None, token_param=None):
        self.token = token or os.environ["BASE_ACCESS_TOKEN"]
        self.token_param = token_param or os.environ.get("BASE_TOKEN_PARAM", "access_token_v2")

    def call(self, app, path, params=None):
        form = {self.token_param: self.token, **(params or {})}
        r = request("POST", f"https://{app}.base.vn/{path}", form=form)
        if str(r.get("code", 1)) not in ("1", "200") and r.get("code") is not None:
            raise ApiError(f"Base {app}/{path}: {r.get('message') or r}")
        return r

    def collect(self, endpoints=None):
        for ep in endpoints or DEFAULT_ENDPOINTS:
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
