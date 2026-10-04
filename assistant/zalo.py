"""Zalo cá nhân/nhóm: Zalo không có API đọc chat cá nhân, nên dùng file xuất ra.

Cách dùng: lưu (copy/paste, hoặc chức năng xuất) đoạn chat quan trọng thành file
.txt vào thư mục data/zalo/ (hoặc một thư mục Google Drive được đồng bộ),
mỗi nhóm một file, tên file = tên nhóm. Agent đọc phần mới so với lần trước.
"""
import hashlib
from pathlib import Path


def collect(folder="data/zalo"):
    for f in sorted(Path(folder).glob("*.txt")):
        text = f.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            continue
        yield {
            "source": "zalo",
            "id": hashlib.sha1(text.encode()).hexdigest()[:12],
            "chat": f.stem,
            "time": "",
            "subject": f"Zalo – {f.stem}",
            "text": text[-8000:],  # phần gần nhất
        }
