# Thiết kế Thông báo trong app (in-app notification)

> Trạng thái: ĐANG THIẾT KẾ (2026-06-30). Chưa code. Giữ ĐƠN GIẢN (demo).
> Liên quan: [`notification_service.py`](../../app/service/notification_service.py),
> [`notification_controller.py`](../../app/controller/notification_controller.py),
> [`thiet-ke-checkout.md`](thiet-ke-checkout.md) (điểm móc sự kiện đơn hàng),
> [`thiet-ke-email.md`](thiet-ke-email.md) (kênh email - làm sau khi có starter).

## 1. Mục tiêu & phạm vi

Biến hệ thống thông báo hiện tại (đang là "danh sách toàn cục cho admin") thành **hộp thư của từng
người dùng**: user thấy thông báo của riêng mình, có badge đếm chưa đọc (cái chuông), và một số sự
kiện **tự sinh** thông báo. Mức demo, không làm realtime push phức tạp.

Phạm vi kênh: **chỉ in-app** (`type="push"`). Email là kênh riêng, nối sau qua
[`thiet-ke-email.md`](thiet-ke-email.md).

## 2. Hiện trạng & vấn đề

Bảng `notifications` + service + controller đã có, nhưng:

| Vấn đề | Chi tiết |
|---|---|
| Không theo người dùng | `list`/`unread`/`mark_all` query **toàn bộ** thông báo mọi user (`find_all_notifications`), chặn bằng quyền admin `view_notifications`. Thiếu "thông báo của tôi" + đếm chưa đọc. |
| IDOR | `PATCH /{id}/read` chỉ `require_login()`, không check chủ sở hữu -> user sửa thông báo người khác. |
| Chỉ tạo thủ công | Thông báo chỉ sinh qua `POST` (admin). Không tự sinh khi đặt hàng / đổi trạng thái giao. |
| `detail` dùng sai error code | Trả `E10200` (không tìm thấy sản phẩm) khi không thấy thông báo. |

## 3. Quyết định đã chốt (2026-06-30)

| Vấn đề | Lựa chọn |
|---|---|
| Sự kiện tự sinh thông báo | **Đặt hàng thành công**, **đổi trạng thái giao hàng**, **admin broadcast**. (Bỏ "review được duyệt".) |
| Realtime | **Polling đơn giản** (FE gọi `unread-count` định kỳ / khi đổi trang). KHÔNG WebSocket/SSE. |
| Kênh | Chỉ in-app bây giờ; email nối sau khi có starter. |
| Schema | Thêm 1 cột `link` (nullable) để bấm nhảy tới trang liên quan. Không đổi gì khác. |

## 4. Thay đổi schema

Bảng `notifications` thêm **một** cột:

| Cột thêm | Kiểu | Ghi chú |
|---|---|---|
| link | String(255) nullable | đường dẫn FE để bấm vào (vd `/orders/12`). Null = không điều hướng. |

Giữ nguyên các cột hiện có (`user_id`, `title`, `message`, `type`, `is_read`, `read_at`,
`created_at`). `type` vẫn là kênh: in-app = `"push"`.

> Migration Alembic: `ALTER TABLE notifications ADD COLUMN link VARCHAR(255) NULL`.
> Index gợi ý: `notifications(user_id, is_read)` để truy vấn hộp thư + đếm chưa đọc nhanh.

## 5. Helper tự sinh thông báo

Thêm vào `NotificationService` một helper gọn, fault-tolerant (lỗi tạo thông báo **không** được làm
hỏng nghiệp vụ chính như đặt hàng):

```python
async def notify(
    self, user_id: int, title: str, message: str | None = None, link: str | None = None
) -> None:
    """Tạo 1 thông báo in-app (type='push') cho user. Nuốt lỗi non-critical (chỉ log)
    để không làm hỏng nghiệp vụ gọi nó (đặt hàng, đổi trạng thái...).
    """
```

- Mở transaction riêng bên trong (hoặc nhận cờ để chạy trong transaction đang mở của caller - cân
  nhắc ở Phase code; ưu tiên đơn giản: gọi sau khi nghiệp vụ chính đã commit, nuốt lỗi).
- **Nguyên tắc:** thông báo là phụ. Đặt hàng vẫn thành công kể cả khi ghi thông báo lỗi.

### Điểm móc sự kiện

| Sự kiện | Gọi ở đâu | Nội dung gợi ý |
|---|---|---|
| Đặt hàng thành công | sau `create_order` (COD) / sau callback thanh toán online thành công | title "Đặt hàng thành công", message "Đơn #{id} đã được tạo", link `/orders/{id}` |
| Đổi trạng thái giao hàng | trong nghiệp vụ cập nhật `shipping_status` của đơn | title "Cập nhật đơn hàng", message "Đơn #{id}: {trạng thái}", link `/orders/{id}` |
| Admin broadcast | endpoint create sẵn có (admin chọn user / tất cả) | tùy admin nhập |

> Lưu ý: hiện `OrderService.update_order` chỉ sửa `address`, chưa có nghiệp vụ đổi `shipping_status`
> riêng. Khi làm thông báo "đổi trạng thái giao", có thể cần bổ sung 1 endpoint/nghiệp vụ admin cập
> nhật `shipping_status` (gọn) rồi gọi `notify` trong đó. Ghi nhận để làm cùng phase.

## 6. API (sửa `NotificationController`)

### Thêm - hộp thư người dùng

| Method | Path | Mô tả | Quyền |
|---|---|---|---|
| GET | `/api/notifications/me` | thông báo của user hiện tại, mới nhất trước, phân trang | đăng nhập |
| GET | `/api/notifications/me/unread-count` | số chưa đọc (badge chuông) | đăng nhập |
| PATCH | `/api/notifications/me/read-all` | đọc hết của user hiện tại | đăng nhập |

### Sửa - vá IDOR

| Method | Path | Sửa |
|---|---|---|
| PATCH | `/api/notifications/{id}/read` | thêm check **chủ sở hữu**: chỉ chủ thông báo (hoặc quyền admin) mới đánh dấu đọc |
| GET | `/api/notifications/{id}` | đổi error code khi không thấy: `E10200` -> `E10330` |

### Giữ nguyên - admin

`GET /` (tất cả), `POST /` (tạo/broadcast), `PATCH /read-all` (toàn hệ thống), `DELETE /read`,
`DELETE /{id}`: giữ dưới quyền admin (`view_notifications` / `create_notification` /
`delete_notification`). `POST /` mở rộng cho phép `link` + (tùy chọn) gửi tới "tất cả user".

## 7. Repository - thêm method

```python
async def find_by_user_id(self, user_id, page, limit) -> list[Notification]   # phân trang, desc
async def count_unread_by_user(self, user_id) -> int
async def mark_all_read_by_user(self, user_id) -> int
```

(Giữ các method toàn cục cũ cho trang admin.)

## 8. DTO

- `NotificationResponse`: thêm field `link`.
- `NotificationCreateRequest` (admin): thêm `link` (optional); (tùy chọn) `broadcast: bool` hoặc
  `userIds: list[int]` để gửi nhiều người.
- `UnreadCountResponse { count: int }` cho badge.

## 9. Error code mới

| Key | code | message | http |
|---|---|---|---|
| E10330 | 10330 | Không tìm thấy thông báo | 404 |
| E10331 | 10331 | Không có quyền với thông báo này | 403 |

## 10. Phân quyền

- Hộp thư cá nhân (`/me`, `/{id}/read`): user đăng nhập, **chỉ thao tác trên thông báo của chính
  mình** (owner check, theo mẫu `require_owner_or_permission` đã dùng cho order detail).
- Thao tác admin (xem tất cả, tạo, xóa): giữ permission hiện có.

## 11. Kế hoạch theo phase (mỗi phase có test)

- [x] **Phase 1 - Hộp thư người dùng + vá IDOR.** Cột `link` + migration; repo `find_by_user_id` /
  `count_unread_by_user` / `mark_all_read_by_user`; endpoint `/me`, `/me/unread-count`,
  `/me/read-all`; vá owner check cho `/{id}/read`; error code E10330/E10331; sửa `detail` dùng
  E10330. Test: user chỉ thấy/sửa thông báo của mình, đếm chưa đọc đúng.
- [x] **Phase 2 - Helper `notify` + sự kiện đặt hàng.** Thêm `notify(...)`; gọi sau `create_order`
  (COD) / sau callback thanh toán online (khớp [`thiet-ke-checkout.md`](thiet-ke-checkout.md)).
  Test: đặt hàng -> có 1 thông báo cho chủ đơn; lỗi notify không làm hỏng đặt hàng.
- [x] **Phase 3 - Sự kiện đổi trạng thái giao + admin broadcast.** Nghiệp vụ cập nhật
  `shipping_status` (admin) -> `notify` chủ đơn; mở rộng `POST /` cho broadcast + `link`. Test.
- [x] **Phase 4 - Kênh email.** (ĐÃ CODE) Cờ `also_email` (+ `email_to`) cho `notify` (tạo in-app +
  gửi email nền qua `EmailService.send_notification`). Đã wire vào sự kiện đổi trạng thái giao.
  Xem [`thiet-ke-email.md`](thiet-ke-email.md) Phase B.

## 12. Ghi chú demo (không làm quá)

- Không realtime push; polling là đủ. Có thể nâng SSE/WebSocket sau nếu muốn "đẹp" hơn.
- Không phân loại icon theo `category` ở bản đầu (giữ schema tối thiểu); nếu cần, thêm cột
  `category` sau.
- `notify` ưu tiên đơn giản + nuốt lỗi non-critical; không hàng đợi/retry.
