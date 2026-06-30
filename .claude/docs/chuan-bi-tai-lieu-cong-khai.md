# Chuẩn bị tài liệu công khai (docs/) - tổng hợp việc đã làm

> Mục đích: gom các việc đã hoàn tất ở pha tối ưu để **phiên sau viết tài liệu công khai** vào
> `backend/docs/` (thư mục công khai, đẩy lên GitHub). **CHƯA tạo `docs/` bây giờ** - file này chỉ
> chuẩn bị nguồn + bản đồ. Tài liệu công khai **chỉ tiếng Việt, không cần tiếng Anh**.
>
> Khuôn mẫu tham chiếu: `D:\code\xime\Base Platform\data\docs\vn\` (overview, architecture,
> authorization, data-model, integration, storage). Văn phong: tản văn rõ ràng + bảng + sơ đồ ASCII.

## Việc đã hoàn tất (nguồn cho tài liệu công khai)

Tất cả đã có tài liệu nội bộ chi tiết trong `.claude/docs/`. Public docs sẽ chắt lọc lại từ đây.

### 1. Nâng cấp phân quyền (Authorization)
- **Đã làm:** sửa lỗ hổng deny-overrides (leo thang quyền); superadmin bypass; scope theo **nhánh
  category** (cấp ở cha phủ subtree, deny nhánh con chính xác); gom ownership + vá IDOR
  (order/wishlist/cart detail); cache RAM `PermissionRegistry`; lọc danh sách quản trị theo mảng nhân viên.
- **Nguồn:** [`phan-quyen.md`](phan-quyen.md), [`phan-quyen-nang-cap.md`](phan-quyen-nang-cap.md),
  [`quyet-dinh-thiet-ke.md`](quyet-dinh-thiet-ke.md) (QĐ-5 scope_type, QĐ-6 ownership).

### 2. Tối ưu N+1 cho Product / Variant
- **Đã làm:** index FK + UNIQUE; batch query gỡ N+1 khi dựng DTO sản phẩm (`_to_dtos`) và
  `find_product_option_by_json`. List M sản phẩm: từ `M x (N+1)` xuống ~4 query cố định.
- **Nguồn:** [`toi-uu-product-variant.md`](toi-uu-product-variant.md).

### 3. Cá nhân hóa người dùng (không AI, chấm điểm theo luật)
- **Đã làm:** kho sự kiện có trọng số (Action/Interaction); ghi tín hiệu có throttle; affinity
  category materialized **decay-on-write**; endpoint gợi ý (recently-viewed/trending/for-you/related);
  co-occurrence đồng mua; Xime scheduler dựng lại hằng ngày 03:00.
- **Nguồn:** [`ca-nhan-hoa-nguoi-dung.md`](ca-nhan-hoa-nguoi-dung.md).

### Nền tảng đã có sẵn từ trước (cũng cần lên public docs)
- Kiến trúc đa lớp + lý do không Hexagonal: [`kien-truc-da-lop.md`](kien-truc-da-lop.md).
- Domain model / schema: [`domain-model.md`](domain-model.md).
- Error code: [`error-code-system.md`](error-code-system.md). Auth JWT: [`auth-jwt.md`](auth-jwt.md).
- Wiring web layer (CORS/middleware/exception): [`go-web-adapter-dung-configure.md`](go-web-adapter-dung-configure.md).

## Cấu trúc đề xuất cho `backend/docs/` (chỉ tiếng Việt)

> **Để phẳng, KHÔNG có thư mục con `vn/`.** Dự án này một ngôn ngữ nên các file `.md` nằm thẳng
> trong `docs/`. (`data` chia `docs/vn` + `docs/en` vì có hai ngôn ngữ - ta không cần.)

Mô phỏng nội dung `data/docs/vn/` nhưng theo nghiệp vụ shop:

| File public (đề xuất) | Nội dung | Chắt từ nguồn nội bộ |
|---|---|---|
| `docs/tong-quan.md` | Shop backend là gì, công nghệ, cách chạy | `tong-quan-du-an.md`, CLAUDE.md |
| `docs/kien-truc.md` | Kiến trúc đa lớp, luồng controller→service→repository, transaction | `kien-truc-da-lop.md`, `rules/` |
| `docs/mo-hinh-du-lieu.md` | Các bảng chính + quan hệ (user/product/variant/order/...) | `domain-model.md` |
| `docs/phan-quyen.md` | RBAC+ACL, deny-overrides, scope category, ownership | `phan-quyen.md`, `phan-quyen-nang-cap.md` |
| `docs/api.md` | Bản đồ REST endpoint theo nhóm (auth, product, order, gợi ý...) | quét `app/controller/` |
| `docs/ca-nhan-hoa.md` | Mô hình chấm điểm, affinity, gợi ý, co-occurrence, scheduler | `ca-nhan-hoa-nguoi-dung.md` |
| `docs/loi-va-ma-loi.md` | Hệ thống error code `{errorKey, code, message}` | `error-code-system.md` |
| `docs/luu-tru-tep.md` (tùy) | Upload + stream media (HTTP Range) | (storage starter) |

## Lưu ý khi viết public docs (khác tài liệu nội bộ)

- **Đối tượng đọc:** người ngoài / lập trình viên tích hợp, KHÔNG biết lịch sử migrate hay nội bộ
  `.claude`. Bỏ các chi tiết quá trình (số phase, tên migration, "đã sửa bug X"); chỉ mô tả **trạng
  thái hiện tại** và **cách dùng**.
- **Chỉ tiếng Việt.** Không cần bản tiếng Anh (khác `data` có cả en/vn).
- Không dùng gạch ngang dài (—) / en dash (–); chỉ dấu trừ (-).
- Comment code trong ví dụ: tiếng Anh trên, tiếng Việt dưới.
- Có thể kèm sơ đồ ASCII như `data/docs/vn/overview.md`.

## Khi nào làm

Sau khi xong (hoặc song song) các mảng còn thiếu lớn: **trang thanh toán** và **email** (đang chờ
thiết kế). Lúc đó public docs sẽ phản ánh đầy đủ hơn. Hiện chỉ cần giữ file này làm điểm gom.
