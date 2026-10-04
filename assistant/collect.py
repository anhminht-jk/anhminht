"""Thu thập dữ liệu công việc thành bản tổng hợp cho agent đọc.

  python -m assistant.collect --days 60      # lần đầu: học bối cảnh 2 tháng
  python -m assistant.collect --days 1       # hằng ngày

Kết quả: data/runs/<thời điểm>/ gồm items.jsonl + các file .md theo nguồn.
Nguồn nào chưa cấu hình (thiếu token) hoặc lỗi sẽ được ghi rõ trong status.md
và bỏ qua, không làm hỏng cả lượt chạy.
"""
import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import base_vn, lark, zalo


def load_config(path="config.json"):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def sources(cfg, since):
    if os.environ.get("LARK_APP_ID"):
        client = lark.Lark()
        mailbox = os.environ.get("LARK_MAILBOX") or cfg.get("lark_mailbox")
        if mailbox:
            yield "Lark – Email", lambda: client.mail(mailbox, since)
        else:
            yield "Lark – Email", None
        skip = set(cfg.get("lark_skip_chats", []))

        def chat_items():
            for c in client.chats():
                if c.get("name") in skip:
                    continue
                for m in client.chat_messages(c["chat_id"], since):
                    m["chat"] = c.get("name", "")
                    yield m
        yield "Lark – Nhóm chat", chat_items
    else:
        yield "Lark", None
    if os.environ.get("BASE_ACCESS_TOKEN"):
        yield "Base.vn", lambda: base_vn.Base().collect(cfg.get("base_endpoints"))
    else:
        yield "Base.vn", None
    yield "Zalo (file xuất)", lambda: zalo.collect(cfg.get("zalo_folder", "data/zalo"))


def render_md(title, items):
    out = [f"# {title} ({len(items)} mục)\n"]
    for it in sorted(items, key=lambda x: x.get("time", ""), reverse=True):
        head = " | ".join(x for x in [it.get("time", "")[:16], it.get("folder") or it.get("chat") or it.get("module"),
                                       it.get("from"), it.get("subject")] if x)
        out.append(f"## {head}")
        if it.get("to"):
            out.append(f"To: {it['to']}" + (f" | Cc: {it['cc']}" if it.get("cc") else ""))
        out.append(it.get("text", "").strip() + "\n")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=float, default=1.1)
    ap.add_argument("--out", default="data/runs")
    args = ap.parse_args(argv)

    cfg = load_config()
    since = datetime.now(timezone.utc) - timedelta(days=args.days)
    run_dir = Path(args.out) / datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    run_dir.mkdir(parents=True, exist_ok=True)

    status = [f"# Trạng thái thu thập — từ {since:%Y-%m-%d %H:%M} UTC\n"]
    with open(run_dir / "items.jsonl", "w", encoding="utf-8") as jf:
        for i, (name, fetch) in enumerate(sources(cfg, since)):
            if fetch is None:
                status.append(f"- ⚪ {name}: chưa cấu hình")
                continue
            items = []
            try:
                for it in fetch():
                    items.append(it)
                    jf.write(json.dumps(it, ensure_ascii=False) + "\n")
                status.append(f"- ✅ {name}: {len(items)} mục")
            except Exception as e:  # một nguồn lỗi không chặn các nguồn khác
                status.append(f"- ❌ {name}: {e} (đã lấy {len(items)} mục trước khi lỗi)")
            if items:
                (run_dir / f"{i:02d}-{name.split()[0].lower()}-{i}.md").write_text(
                    render_md(name, items), encoding="utf-8")
    (run_dir / "status.md").write_text("\n".join(status) + "\n", encoding="utf-8")
    print(run_dir)
    print("\n".join(status))


if __name__ == "__main__":
    main()
