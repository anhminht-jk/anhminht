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

    def test_collect_fans_out_projects(self):
        import os
        from unittest import mock
        calls = []

        def fake_call(self, app, path, params=None):
            calls.append(path)
            if path.endswith("project/list"):
                return {"code": 1, "projects": [{"id": 5, "name": "Mở cửa hàng Q7", "owners": [{"username": "an"}]}]}
            if path.endswith("user/tasks"):
                self.users.append(params["user"])
                return {"code": 1, "tasks": [{"id": 9, "name": "Thuê mặt bằng", "project_id": "5"},
                                             {"id": 11, "name": "Nộp báo cáo tuần", "ns": {"name": "HCNS"}}]}
            return {"code": 1, "project": {"id": 5}, "tasks": [{"id": 9, "name": "Thuê mặt bằng"}],
                    "subtasks": [{"id": 10, "name": "Ký HĐ"}]}

        with mock.patch.dict(os.environ, {"BASE_WEWORK_TOKEN": "w"}, clear=True), \
             mock.patch.object(base_vn.Base, "call", fake_call), \
             mock.patch.object(base_vn.Base, "users", [], create=True):
            items = list(base_vn.Base().collect())
            self.assertEqual(base_vn.Base.users, ["an"])
        self.assertEqual([i["subject"] for i in items],
                         ["Mở cửa hàng Q7", "Mở cửa hàng Q7 › Thuê mặt bằng", "Mở cửa hàng Q7 › Ký HĐ",
                          "HCNS › Nộp báo cáo tuần"])
        self.assertEqual(calls, ["extapi/v3/project/list", "extapi/v3/project/get.full", "extapi/v3/user/tasks"])

    def test_wework_task_fields(self):
        row = {"id": "1", "name": "Đặt hàng mẫu", "content": "<p>dài</p>", "content_short": "Gọi NCC",
               "username": "lan", "deadline": "1759536000", "completed_time": 0, "overdue": 1,
               "urgent": "0", "status": "0", "tasklist": {"id": "3", "name": "Mua hàng"},
               "owners": [{"username": "minh"}], "last_update": "1759449600"}
        it = base_vn.to_item("Wework", row)
        self.assertEqual(it["time"], "2025-10-03")
        for part in ("content_short: Gọi NCC", "username: lan", "tasklist: Mua hàng", "owners: minh",
                     "deadline: 2025-10-04", "overdue: 1", "status: 0"):
            self.assertIn(part, it["text"])
        self.assertEqual(base_vn.to_item("W", {"content": "<p></p>", "name": "a&amp;b"})["subject"], "a&b")
        self.assertNotIn("content", base_vn.to_item("W", {"content": "<p></p>"})["text"])
        for absent in ("<p>", "completed_time", "urgent"):
            self.assertNotIn(absent, it["text"])

    def test_paging_stops_on_is_remain(self):
        from unittest import mock
        pages = []

        def fake_call(self, app, path, params=None):
            pages.append(params["page"])
            return {"code": 1, "projects": [{"id": i} for i in range(25)], "is_remain": params["page"] == 0}

        with mock.patch.object(base_vn.Base, "call", fake_call):
            self.assertEqual(len(list(base_vn.Base().rows("wework", "p"))), 50)
        self.assertEqual(pages, [0, 1])

    def test_token_per_app(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"BASE_SERVICE_TOKEN": "s"}, clear=True):
            self.assertEqual(base_vn.token_for("service"), "s")
            self.assertIsNone(base_vn.token_for("wework"))
        with mock.patch.dict(os.environ, {"BASE_WEWORK_TOKEN": " <abc~1> "}, clear=True):
            self.assertEqual(base_vn.token_for("wework"), "abc~1")
            self.assertTrue(base_vn.configured())
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(base_vn.configured())


if __name__ == "__main__":
    unittest.main()
