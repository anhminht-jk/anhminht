import base64
import json
import unittest

from assistant import base_vn, lark
from assistant.collect import render_md


def b64(s):
    return base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")


class LarkTest(unittest.TestCase):
    def test_parse_mail_strips_quote(self):
        msg = {"message_id": "m1", "internal_date": "1759536000000", "subject": "Báo giá",
               "head_from": {"name": "Lan", "mail_address": "lan@ncc.vn"},
               "to": [{"mail_address": "ceo@cty.vn"}],
               "body_plain_text": b64("Gửi anh báo giá mới.\n\nOn Mon, X wrote:\n> cũ")}
        it = lark.parse_mail(msg, "INBOX")
        self.assertEqual(it["text"], "Gửi anh báo giá mới.")
        self.assertEqual(it["from"], "Lan <lan@ncc.vn>")
        self.assertTrue(it["time"].startswith("2025-10-04"))

    def test_chat_text_types(self):
        self.assertEqual(lark.chat_text("text", json.dumps({"text": "chốt KPI"})), "chốt KPI")
        post = {"title": "Họp", "content": [[{"tag": "text", "text": "9h sáng"}]]}
        self.assertEqual(lark.chat_text("post", json.dumps(post)), "Họp\n9h sáng")
        self.assertEqual(lark.chat_text("file", json.dumps({"file_name": "a.xlsx"})), "[file: a.xlsx]")


class BaseTest(unittest.TestCase):
    def test_extract_and_item(self):
        resp = {"code": 1, "tasks": [{"id": 7, "name": "Ra mắt SP", "deadline": 1759536000, "status": "doing"}]}
        rows = base_vn.extract_rows(resp)
        it = base_vn.to_item("Wework", rows[0])
        self.assertEqual(it["subject"], "Ra mắt SP")
        self.assertIn("deadline: 2025-10-04", it["text"])

    def test_render_md(self):
        md = render_md("X", [{"time": "2025-10-04T00:00", "subject": "S", "text": "T"}])
        self.assertIn("## 2025-10-04T00:00 | S", md)


if __name__ == "__main__":
    unittest.main()
