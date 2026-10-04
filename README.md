# Trợ lý điều hành

Agent đọc email công ty (Lark), nhóm chat Lark, Base Wework, Base Service (phê duyệt) và chat Zalo xuất ra file.
Mỗi sáng agent đăng **bản tin điều hành** kèm danh sách **đầu việc đề xuất** lên dashboard và gửi tóm tắt qua email.
Agent chỉ triển khai những việc anh/chị đã bấm **Duyệt**.

Dashboard: https://claude.ai/artifact/7iJYX6WBbpY7j4oJYA2zV2

```
Lark Mail ─┐
Lark Chat ─┤                 ┌─> Bộ nhớ công việc (Notion)
Base.vn   ─┼─> collect.py ─> Claude (theo CLAUDE.md) ─┼─> Bản tin + đề xuất (dashboard) ─> email
Zalo file ─┘                 └─> Thực thi việc đã duyệt
```

## Cài đặt (làm một lần)

### 1. Tạo app trên Lark để đọc email và chat
1. Vào https://open.larksuite.com/app → **Create Custom App**.
2. Mục **Permissions & Scopes**, bật các quyền:
   - `mail:user_mailbox.message:readonly`: đọc email
   - `im:chat:readonly`, `im:message:readonly`, `im:message.group_msg`: đọc nhóm chat có bot
3. Mục **Features** → bật **Bot**. Thêm bot vào các nhóm chat điều hành cần agent theo dõi.
4. **Publish** app và nhờ quản trị viên Lark của công ty duyệt.
5. Ghi lại **App ID** và **App Secret**.

### 2. Lấy token Base.vn (token v2, mỗi ứng dụng một token)
Vào account.base.vn → **Tích hợp với bên thứ ba ver 2** → thêm token cho từng ứng dụng:
- **Wework**: quyền đọc dự án, công việc
- **Base Service**: quyền đọc các phiếu/luồng phê duyệt

Đặt "thành viên phụ trách" là anh/chị, để token thấy đúng phạm vi việc anh/chị quản lý.

### 3. Khai báo vào môi trường Claude Code
Không dán token vào khung chat. Mở menu môi trường cloud trên thanh tiêu đề phiên → **Edit**:
- **Environment variables**:
  ```
  LARK_APP_ID=cli_xxx
  LARK_APP_SECRET=xxx
  LARK_MAILBOX=email-cong-ty@congty.com
  BASE_WEWORK_TOKEN=xxx
  BASE_SERVICE_TOKEN=xxx
  ```
- **Network access** → Custom → thêm `open.larksuite.com`, `wework.base.vn`, `service.base.vn`, giữ nguyên danh sách mặc định.
  Hướng dẫn: https://code.claude.com/docs/en/cloud-environments#network-access

### 4. Zalo
Zalo không có API đọc chat cá nhân. Chép các đoạn chat quan trọng vào file `.txt`
trong `data/zalo/`, mỗi nhóm một file, tên file là tên nhóm.

## Chạy thử
```bash
python3 -m unittest discover -s tests
python3 -m assistant.collect --days 60   # lần đầu: đọc lại 2 tháng
```
