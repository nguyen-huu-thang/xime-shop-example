# Phase 9 — Hoàn thiện

**Mục tiêu:** OpenAPI, test, seed admin, rà soát đối chiếu PHP, bàn giao.

## Bước

### OpenAPI / Swagger
- [x] **9.1** Cấu hình OpenAPI: JwtBearer security scheme, public_paths, title/version — `config/web.py`.
- [x] **9.2** Tags đã khai báo trên mọi controller (prefix + tags class attrs). Summary/response_model
  có thể bổ sung thêm sau theo nhu cầu frontend.

### Seed & dữ liệu khởi tạo
- [x] **9.3** Script `seed.py` hoàn thiện: quyền + nhóm admin + tài khoản admin (Admin@123) + gán nhóm.
- [x] **9.4** Seed `list_tables` (24 bảng) — đã làm Phase 8.

### Test
- [x] **9.5** `test/test_phase9_core_flows.py` — unit test: error codes, bcrypt, search relevance,
  file path building. Không cần DB.
- [x] **9.6** Test SearchService với stub ProductService (relevance score, price filter, pagination).

### Rà soát đối chiếu
- [x] **9.7** 18 controller đã tạo, đủ endpoint theo PHP. Checklist ngắn:
  security, permissions, group, group_member, group_permission, user_permission,
  category, product, cart, coupon, order, review, wishlist, notification, file,
  search, health.
- [x] **9.8** AppException keys đã được unit test (test_all_critical_error_codes_present).
- [x] **9.9** Transaction: mọi ghi nhiều bảng trong single `async with transaction()` (order, product).
- [x] **9.10** Phân quyền: mọi endpoint admin/resource đều gọi `authz.require(user, "tên_quyền")`.

### Bàn giao
- [x] **9.11** `README.md` tạo mới: cài đặt, chạy, seed, cấu trúc thư mục, danh sách API.
- [x] **9.12** `.env.example` đầy đủ: DATABASE_URL, JWT_SECRET_KEY, JWT_ALGORITHM, JWT_*_EXPIRE_MINUTES, UPLOAD_DIR.
- [x] **9.13** Checklist tổng trong `ke-hoach/README.md` — cập nhật đầy đủ.

## Đầu ra

Dự án Python chạy tương đương PHP, có Swagger, seed, test luồng chính, tài liệu bàn giao.

## Rủi ro / cần xác minh

- Khác biệt hành vi tinh tế giữa Symfony và FastAPI (status code mặc định, định dạng lỗi) — đối chiếu
  response thực tế nếu frontend phụ thuộc định dạng cũ.
