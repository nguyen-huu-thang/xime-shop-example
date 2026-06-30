# Vấn đề phát hiện ở framework Xime

Nơi ghi lại các vấn đề/bất tiện phát hiện khi dùng framework Xime trong quá trình migrate shop.
Mục đích: phản hồi cho tác giả framework để cải thiện.

| # | Mức độ | Tiêu đề | Phase phát hiện | File |
|---|---|---|---|---|
| 1 | Thấp (cosmetic) | `TestApplication` gây cảnh báo pytest collection | Phase 0 | [issue-001-testapplication-pytest-collection.md](issue-001-testapplication-pytest-collection.md) |
| 3 | Trung bình (đề xuất) | Thêm BaseRepository/CRUD chung vào starter SQLAlchemy | Pha tối ưu | [issue-003-base-repository-crud-trong-starter.md](issue-003-base-repository-crud-trong-starter.md) |
| 4 | Trung bình (đang bàn) | Hỗ trợ cấu hình qua biến môi trường (deploy cloud-native) | Pha tối ưu | [issue-004-ho-tro-env-var-cau-hinh.md](issue-004-ho-tro-env-var-cau-hinh.md) |
| 5 | Trung bình (đã xong ✅) | Thêm starter gửi email (SMTP) cho Xime | Pha hoàn thiện backend | [issue-005-email-starter.md](issue-005-email-starter.md) |

> Issue #2 (thiếu hook public cho exception handler / middleware) đã được framework giải quyết
> (configure_exception_handlers / configure_middleware / configure_cors) - đã gỡ khỏi danh sách.
