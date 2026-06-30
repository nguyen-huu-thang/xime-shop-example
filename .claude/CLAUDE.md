# Shop Backend (Python/Xime) — Hướng dẫn phiên làm việc

Dự án **migrate shop backend từ PHP/Symfony sang Python** dùng framework **Xime**.
Dự án đã **hoàn thiện migrate (Phase 0-9)** và đang ở **pha tối ưu** (đã có code đầy đủ, test pass).
Xem mục "Trạng thái hiện tại" trong [`../CLAUDE.md`](../CLAUDE.md) để biết các cải tiến đã làm.

> ⚠️ **Quyết định kiến trúc quan trọng:** Dự án này dùng **kiến trúc đa lớp (layered)** giống
> dự án PHP gốc, **KHÔNG** dùng Hexagonal/Clean như Xime khuyến nghị. Đọc kỹ
> [`docs/kien-truc-da-lop.md`](docs/kien-truc-da-lop.md) trước khi viết bất kỳ dòng code nào.

---

## Đọc gì khi bắt đầu

### Bắt buộc đọc trước
1. **Kiến trúc đa lớp & lý do không theo Hexagonal** → [`docs/kien-truc-da-lop.md`](docs/kien-truc-da-lop.md)
2. **Cây thư mục dự án Python** → [`docs/cay-thu-muc.md`](docs/cay-thu-muc.md)
3. **Quy tắc code (đa lớp + Xime DI)** → [`rules/coding-da-lop.md`](rules/coding-da-lop.md)
4. **Kế hoạch tổng thể** → [`docs/ke-hoach/README.md`](docs/ke-hoach/README.md)

### Đọc khi cần (tham chiếu)
- **Quyết định thiết kế đã chốt** → [`docs/quyet-dinh-thiet-ke.md`](docs/quyet-dinh-thiet-ke.md)
- **Kết nối cơ sở dữ liệu (URL, user, host)** → [`docs/database-connection.md`](docs/database-connection.md)
- **Tổng quan & nguồn PHP** → [`docs/tong-quan-du-an.md`](docs/tong-quan-du-an.md)
- **Mapping PHP → Python/Xime** → [`docs/mapping-php-python.md`](docs/mapping-php-python.md)
- **Domain model (schema CSDL, quan hệ, nghiệp vụ)** → [`docs/domain-model.md`](docs/domain-model.md)
- **Mô hình phân quyền** → [`docs/phan-quyen.md`](docs/phan-quyen.md)
- **Hệ thống error code** → [`docs/error-code-system.md`](docs/error-code-system.md)
- **Xác thực JWT** → [`docs/auth-jwt.md`](docs/auth-jwt.md)
- **Review + bổ sung test, bug đã sửa & vấn đề còn tồn (2026-06-29)** → [`docs/review-test-2026-06-29.md`](docs/review-test-2026-06-29.md)
- **Tối ưu N+1 product/variant** → [`docs/toi-uu-product-variant.md`](docs/toi-uu-product-variant.md)
- **Cá nhân hóa người dùng (không AI)** → [`docs/ca-nhan-hoa-nguoi-dung.md`](docs/ca-nhan-hoa-nguoi-dung.md)
- **Thiết kế Checkout/Thanh toán (demo)** → [`docs/thiet-ke-checkout.md`](docs/thiet-ke-checkout.md)
- **Thiết kế Thông báo in-app** → [`docs/thiet-ke-thong-bao.md`](docs/thiet-ke-thong-bao.md)
- **Hệ thống Email (giao dịch + bảo mật OTP/reset/verify đã code)** → [`docs/thiet-ke-email.md`](docs/thiet-ke-email.md)
- **Rà soát & vá phân quyền (search/review IDOR, 2026-06-30)** → [`docs/audit-phan-quyen-2026-06-30.md`](docs/audit-phan-quyen-2026-06-30.md)
- **Chuẩn bị tài liệu công khai (gom việc đã làm + kế hoạch docs/)** → [`docs/chuan-bi-tai-lieu-cong-khai.md`](docs/chuan-bi-tai-lieu-cong-khai.md)
- **Wiring web layer (configure_cors/middleware/exception, đã gỡ ShopWebAdapter)** → [`docs/go-web-adapter-dung-configure.md`](docs/go-web-adapter-dung-configure.md)
- **Lưu ý cấu hình CORS + cookie cross-site** → [`docs/luu-y-cau-hinh-cors.md`](docs/luu-y-cau-hinh-cors.md)
- **Repository pattern (SQLAlchemy)** → [`rules/repository-pattern.md`](rules/repository-pattern.md)
- **DTO & Validation (Pydantic)** → [`rules/dto-va-validation.md`](rules/dto-va-validation.md)
- **Transaction** → [`rules/transaction.md`](rules/transaction.md)

### Tài liệu của framework Xime (đọc khi cần hiểu framework)
- `D:\code\xime\xime framework\CLAUDE.md` — tổng quan framework
- `D:\code\xime\xime framework\.claude\rules\coding.md` — quy tắc DI gốc
- `D:\code\xime\xime framework\.claude\docs\routing-layer.md` — class-based controller
- `D:\code\xime\xime framework\.claude\docs\app-entry-point.md` — entry point & sys.path

---

## Nguồn & đích

| | Đường dẫn |
|---|---|
| **Nguồn PHP** | `D:\code\PHP\shop-backend\src\` |
| **Đích Python** | `d:\code\PYTHON\xime\shop\app\` |
| **Framework Xime** | `D:\code\xime\xime framework\` |
| **App mẫu dùng Xime** | `D:\code\xime\Base Platform\data\app\` |

---

## Cách chạy (khi đã có code)

```bash
python app/main.py        # hoặc: python -m app.main
```

Framework tự thêm `./app` vào `sys.path`.

---

## Nguyên tắc làm việc với kế hoạch

- Mỗi phase trong [`docs/ke-hoach/`](docs/ke-hoach/) là một mốc độc lập, làm xong phase trước rồi mới sang phase sau.
- Sau khi hoàn thành mỗi bước, cập nhật trạng thái `[ ]` → `[x]` trong file phase tương ứng.
- Tuân thủ tiếng Việt khi giao tiếp; comment code: tiếng Anh trên, tiếng Việt dưới.
