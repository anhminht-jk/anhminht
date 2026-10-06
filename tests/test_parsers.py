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

    def test_service_ticket_summary(self):
        import base64 as b64
        import json as js
        from datetime import datetime, timezone
        now = datetime(2026, 1, 10, 0, 0, tzinfo=timezone.utc)
        h = lambda hours: str(int(now.timestamp()) + hours * 3600)
        proj = b64.b64encode(js.dumps({"title": "Dự án A"}).encode()).decode().rstrip("=")
        form = [{"name": "Phân loại đề xuất", "type": "select", "value": "Nóng"},
                {"name": "Dự án", "type": "select-master", "value": proj},
                {"name": "Số tiền đề nghị", "type": "currency", "value": "2000000"}]
        tickets = [
            {"id": "1", "root_id": "0", "name": "Phiếu sắp hạn", "username": "an", "since": h(-48), "form": form},
            {"id": "11", "root_id": "1", "status": "10", "block_metatype": "custom", "name": "Đề nghị"},
            {"id": "12", "root_id": "1", "status": "0", "block_metatype": "approval", "name": "CHT duyệt",
             "assignees": [{"username": "binh"}], "deadline": h(5)},
            {"id": "2", "root_id": "0", "name": "Phiếu quá hạn", "username": "an", "form": []},
            {"id": "21", "root_id": "2", "status": "0", "name": "KT duyệt", "assignees": [{"username": "chi"}],
             "deadline": h(-1)},
            {"id": "3", "root_id": "0", "name": "Phiếu treo", "username": "an"},
            {"id": "31", "root_id": "3", "status": "0", "name": "Đề nghị thanh toán", "deadline": "0",
             "assignees": [{"username": "an", "signed": 3}]},
            {"id": "4", "root_id": "0", "name": "Phiếu xong", "username": "an"},
            {"id": "41", "root_id": "4", "status": "9", "block_metatype": "end_service", "name": "Hoàn thành"},
        ]
        items = {i["id"]: i for i in base_vn.ticket_items("Base Service", "QT thanh toán", tickets, now)}
        self.assertEqual(sorted(items), ["1", "2", "3", "4"])
        t1 = items["1"]["text"]
        for part in ("dự án: Dự án A", "phân loại đề xuất: Nóng", "số tiền đề nghị: 2000000",
                     "bước hiện tại: CHT duyệt", "người phụ trách: binh", "SẮP ĐẾN HẠN"):
            self.assertIn(part, t1)
        self.assertEqual(items["1"]["subject"], "QT thanh toán › Phiếu sắp hạn")
        self.assertIn("QUÁ HẠN", items["2"]["text"])
        self.assertIn("không đặt hạn", items["3"]["text"])
        self.assertIn("HOÀN THÀNH", items["4"]["text"])

    def test_collect_service_endpoint(self):
        import os
        from unittest import mock

        def fake_call(self, app, path, params=None):
            self.calls.append((app, path, (params or {}).get("service_id")))
            if path.endswith("service/get.all"):
                return {"code": 1, "services": [{"id": "7", "name": "QT A"}]}
            return {"code": 1, "tickets": [{"id": "1", "root_id": "0", "name": "P1"}]}

        with mock.patch.dict(os.environ, {"BASE_SERVICE_TOKEN": "s"}, clear=True), \
             mock.patch.object(base_vn.Base, "call", fake_call), \
             mock.patch.object(base_vn.Base, "calls", [], create=True):
            items = list(base_vn.Base().collect())
            self.assertEqual(base_vn.Base.calls, [("service", "extapi/v1/service/get.all", None),
                                                  ("service", "extapi/v1/ticket/get.all", "7")])
        self.assertEqual([i["subject"] for i in items], ["QT A › P1"])


if __name__ == "__main__":
    unittest.main()


class ZaloTest(unittest.TestCase):
    def test_only_files_changed_since(self):
        import os
        import tempfile
        from datetime import datetime, timedelta, timezone
        from assistant import zalo
        with tempfile.TemporaryDirectory() as d:
            for name in ("Nhom A", "Nhom B"):
                with open(os.path.join(d, name + ".txt"), "w", encoding="utf-8") as f:
                    f.write("An 09:00\nGửi báo giá trước 10h\n")
            old = (datetime.now(timezone.utc) - timedelta(days=3)).timestamp()
            os.utime(os.path.join(d, "Nhom B.txt"), (old, old))
            since = datetime.now(timezone.utc) - timedelta(days=1)
            items = list(zalo.collect(d, since))
            self.assertEqual([i["chat"] for i in items], ["Nhom A"])
            self.assertEqual(len(list(zalo.collect(d))), 2)
