"""Zalo cá nhân/nhóm: Zalo không có API đọc chat cá nhân, nên dùng file xuất ra.

Cách dùng: CEO/trợ lý dán đoạn chat quan trọng thành file .txt (hoặc Google Doc)
vào thư mục Google Drive "Trợ lý điều hành – Zalo", mỗi nhóm một file, tên file = tên nhóm.
Mỗi lượt chạy, agent tải các file đó về data/zalo/ và đặt thời gian sửa file
(mtime) bằng modifiedTime trên Drive. Module này chỉ đọc file có mtime >= since,
tức là chỉ nhóm chat có nội dung mới so với lần trước.
"""
import hashlib
from datetime import datetime, timezone
from pathlib import Path

PATTERNS = ("*.txt", "*.md")


def collect(folder="data/zalo", since=None):
    files = sorted({f for p in PATTERNS for f in Path(folder).glob(p)})
    for f in files:
        mtime = datetime.fromtimestamp(f.stat().st_mtime, timezone.utc)
        if since and mtime < since:
            continue
        text = f.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            continue
        yield {
            "source": "zalo",
            "id": hashlib.sha1(text.encode()).hexdigest()[:12],
            "chat": f.stem,
            "time": mtime.strftime("%Y-%m-%d %H:%M"),
            "subject": f"Zalo – {f.stem}",
            "text": text[-8000:],  # phần gần nhất
        }
