# Thiết kế: Cá nhân hóa người dùng (không AI, chấm điểm theo luật)

> Tận dụng 3 entity đang mồ côi (`Action`, `Interaction`, `Wishlist`) làm kho sự kiện có trọng số,
> dựng cá nhân hóa bằng quy tắc chấm điểm + thống kê. Không ML, không dịch vụ ngoài.
> Kiến trúc đa lớp (controller -> service -> repository), một tiến trình, dùng cache RAM sẵn có.

## Quyết định đã chốt (2026-06-29)

- **Tính năng:** (1) Đã xem gần đây, (2) Thịnh hành/Bán chạy, (3) Gợi ý cho bạn (affinity), (4) Mua/xem cùng (co-occurrence).
- **Cách tính điểm:** **bảng materialized** (affinity lưu sẵn, cập nhật tăng dần), không tính lại toàn bộ mỗi request.
- **Ghi log:** đồng bộ, nhẹ, **có throttle** (chặn trùng `view` cùng user+product trong cửa sổ ngắn).

## Bối cảnh: 3 entity hiện có

| Bảng | Vai trò |
|---|---|
| `actions` (name, **score**) | Từ điển loại hành động + trọng số điểm. "Quy tắc chấm điểm" nằm ở đây. |
| `interactions` (user_id, product_id, action_id, created_at) | Nhật ký sự kiện = implicit feedback (tín hiệu ngầm). |
| `wishlist` (user_id, product_id) | Tín hiệu tường minh. Đã có đủ tầng repo/service/controller. |

> Lưu ý: bản PHP gốc `InteractionService` chỉ ghi log + đếm, **chưa từng dùng `score`**. Đây là
> thiết kế tính năng mới, không phải port. Interaction/Action ở Python mới chỉ có entity.

## Bảng điểm hành động (seed vào `actions`)

| name | score | Ghi |
|---|---|---|
| view | 1 | Xem chi tiết sản phẩm |
| search_click | 1 | Bấm vào kết quả tìm kiếm |
| wishlist | 4 | Thêm vào yêu thích |
| add_to_cart | 5 | Thêm vào giỏ |
| review | 8 | Viết đánh giá |
| purchase | 10 | Mua (tín hiệu mạnh nhất) |

Điểm chỉnh được trong DB mà không sửa code. Cache trong RAM (bảng nhỏ, đọc nhiều - xem Phase 1).

---

## Mô hình dữ liệu

### Giữ nguyên
`actions`, `interactions`, `wishlist`.

### Thêm mới (materialized)

**`user_category_affinity`** - hồ sơ sở thích của user theo ngành hàng:

| Cột | Kiểu | Ghi |
|---|---|---|
| user_id | BigInt FK users.id | PK phần 1 |
| category_id | BigInt FK categories.id | PK phần 2 |
| score | Numeric/Float | Điểm tích lũy đã decay tới `updated_at` |
| updated_at | timestamptz | Mốc thời gian của `score` (dùng để decay tiếp khi đọc) |

PK kép `(user_id, category_id)`. Kích thước nhỏ: users x categories.

**`product_cooccurrence`** - "mua/xem cùng":

| Cột | Kiểu | Ghi |
|---|---|---|
| product_id | BigInt FK products.id | PK phần 1 |
| related_product_id | BigInt FK products.id | PK phần 2 |
| count | Integer | Số lần đồng xuất hiện |

PK kép `(product_id, related_product_id)`. Cập nhật theo **batch định kỳ** (xem Phase 5), không tăng dần mỗi event.

> Trending KHÔNG cần bảng riêng: tính bằng một truy vấn gộp toàn cục theo cửa sổ thời gian rồi
> cache TTL ngắn (toàn site dùng chung một cache entry).

---

## Thuật toán chấm điểm: decay-on-write (quan trọng)

Vấn đề: time-decay (sự kiện cũ nhẹ dần) khó kết hợp với cập nhật tăng dần, vì đóng góp cũ phải
tiếp tục giảm mỗi ngày. Giải pháp chuẩn - **decay khi ghi**:

Khi user U có hành động điểm `S` trên sản phẩm thuộc category `C` tại thời điểm `now`:

```
row = affinity(U, C)              # nếu chưa có: score=0, updated_at=now
elapsed = now - row.updated_at
decayed = row.score × 0.5 ^ (elapsed / HALF_LIFE)   # đưa điểm cũ về "hiện tại"
row.score = decayed + S
row.updated_at = now              # upsert
```

`HALF_LIFE` = chu kỳ bán rã (vd 30 ngày). Mỗi event O(1), không quét lịch sử.

**Khi đọc để xếp hạng**, decay tiếp tới thời điểm đọc cho công bằng giữa các category:

```
current(U, C) = row.score × 0.5 ^ ((read_now - row.updated_at) / HALF_LIFE)
```

> Lý do đúng: hàm mũ cộng dồn được - decay rồi cộng tương đương giữ từng sự kiện rồi decay tổng.
> Một số trong DB luôn "đúng tới `updated_at`", đọc thì chiếu tiếp tới hiện tại.

Tùy chọn sửa chữa: lệnh admin "rebuild affinity" quét lại toàn bộ interactions để dựng lại bảng từ
đầu (phòng khi sai lệch tích lũy / đổi công thức). Xem Phase 6.

---

## Cách từng tính năng hoạt động

### 1. Đã xem gần đây (Tier 1)
Query `interactions` WHERE user_id=U AND action=view, ORDER BY created_at DESC, khử trùng product,
LIMIT N. Không cần materialized. Rẻ nhờ index `(user_id, action_id, created_at)`.

### 2. Thịnh hành / Bán chạy (Tier 1, kiêm cold-start)
```
SUM(action.score × decay(created_at)) GROUP BY product_id
WHERE created_at > now - WINDOW         -- vd 14 ngày
ORDER BY score DESC LIMIT N
```
Toàn cục -> cache 1 entry TTL ngắn (vd 15-30 phút). Dùng làm fallback khi user chưa có affinity.

### 3. Gợi ý cho bạn (Tier 2, lõi cá nhân hóa)
1. Đọc top category theo `current(U, C)` từ `user_category_affinity` (đã decay tới read-time).
2. Ứng viên = sản phẩm active, còn hàng, thuộc các category đó, **user chưa mua**.
3. Xếp hạng: `affinity_category × popularity(product)` (popularity từ `products.popularity` hoặc trending).
4. User chưa có affinity (cold-start) -> trả về trending (tính năng 2).
Cache theo user TTL ngắn.

### 4. Mua/xem cùng (Tier 3)
Đọc `product_cooccurrence` WHERE product_id=P ORDER BY count DESC LIMIT N -> sản phẩm liên quan.
Nguồn chính: **đồng mua** từ `order_details` (mạnh, ít nhiễu) + tùy chọn đồng xem từ interactions.
Bảng được dựng lại theo batch (Phase 5).

---

## Ghi interaction ở đâu (đồng bộ, throttle, an toàn)

`InteractionService.record(user_id, product_id, action_name)`:
- Mở transaction ngắn riêng: chèn `interactions` + upsert `user_category_affinity` (decay-on-write).
- **Throttle:** với `view`, nếu đã có interaction cùng (user, product, view) trong `THROTTLE_WINDOW`
  (vd 10 phút) thì bỏ qua. Tín hiệu mạnh (cart/wishlist/purchase/review) luôn ghi.
- **An toàn:** ghi log KHÔNG được làm hỏng hành động chính. Bắt lỗi -> log lại đầy đủ rồi tiếp tục
  (KHÔNG catch rỗng). Riêng `purchase` cân nhắc ghi trong cùng transaction đặt hàng cho nhất quán.

Điểm gắn (chỉ user đã đăng nhập; ẩn danh chưa cá nhân hóa - xem "Điểm còn phải quyết"):

| Sự kiện | Gắn ở |
|---|---|
| view | `ProductController.detail` (nếu đã đăng nhập) |
| add_to_cart | luồng thêm giỏ (CartService) |
| wishlist | `WishlistService` (đã có) |
| purchase | `OrderService` khi tạo đơn thành công |
| review | luồng tạo review |

---

## Kiến trúc đa lớp - thành phần mới

| Tầng | File | Vai trò |
|---|---|---|
| entity | `user_category_affinity.py`, `product_cooccurrence.py` | 2 bảng mới |
| cache | `action_registry.py` | Cache bảng `actions` trong RAM (kiểu `PermissionRegistry`) |
| repository | `interaction_repository.py`, `action_repository.py`, `user_category_affinity_repository.py`, `product_cooccurrence_repository.py` | Truy vấn DB |
| service | `action_service.py` | Tra action theo name (qua registry) |
| service | `interaction_service.py` | record() + throttle + queries (đã xem gần đây) |
| service | `affinity_service.py` | decay-on-write upsert + đọc top category |
| service | `recommendation_service.py` | Facade đọc: trending, gợi ý cho bạn, mua cùng |
| service | `cooccurrence_service.py` | Dựng lại bảng co-occurrence (batch) |
| controller | `recommendation_controller.py` | `/api/recommendations/*`, `/api/products/{id}/related`, `/recently-viewed` |
| dto | response cho từng endpoint | |

Phân quyền: endpoint đọc gợi ý chủ yếu công khai / cần đăng nhập (đã xem, gợi ý cho bạn). Lệnh rebuild
co-occurrence/affinity là **admin** (dùng `require` với quyền mới `manage_recommendations`).

---

## Hiệu năng

- Index `interactions`: `(user_id, created_at)`, `(product_id)`, `(action_id)`, `(user_id, product_id, action_id)` (cho throttle).
- `user_category_affinity`: PK `(user_id, category_id)` + index `user_id`.
- `product_cooccurrence`: PK `(product_id, related_product_id)` + index `product_id`.
- Cache RAM: bảng `actions` (registry); trending (1 entry toàn cục, TTL ngắn); gợi ý theo user (TTL ngắn).
- Invalidation đơn giản theo TTL là đủ cho web nhỏ; không cần xóa thủ công.

---

## Kế hoạch theo phase (làm tuần tự, test mỗi bước)

### Phase 1 - Nền: Action + registry + seed
- [ ] `ActionRegistry` (cache RAM bảng actions, kiểu PermissionRegistry: load/get_by_name/invalidate).
- [ ] `ActionRepository`, `ActionService` (get_by_name qua registry).
- [ ] Seed bảng `actions` theo bảng điểm (idempotent), thêm quyền `manage_recommendations` vào seed.
- [ ] Test: registry trả đúng score; seed idempotent.

### Phase 2 - Ghi interaction + throttle (chưa affinity)
- [ ] `InteractionRepository` (find_recent_views, exists_recent(user,product,action,window), find_by_user...).
- [ ] `InteractionService.record()` chèn interaction + throttle view; bắt lỗi an toàn.
- [ ] Migration: bảng đã có, chỉ thêm **index** cho `interactions`.
- [ ] Gắn record() vào view/cart/wishlist/purchase/review (chỉ user đăng nhập).
- [ ] Test: throttle chặn view trùng; tín hiệu mạnh luôn ghi; lỗi record không vỡ hành động chính.

### Phase 3 - Affinity (materialized, decay-on-write)
- [ ] Migration: bảng `user_category_affinity`.
- [ ] `UserCategoryAffinityRepository` (get(user,category), upsert).
- [ ] `AffinityService`: hàm decay-on-write (HALF_LIFE cấu hình), read top-category có decay read-time.
- [ ] `InteractionService.record()` gọi AffinityService cập nhật affinity trong cùng transaction.
- [ ] Test: công thức decay đúng (mốc thời gian giả lập); upsert cộng dồn đúng; cũ giảm đúng nửa sau 1 half-life.

### Phase 4 - Endpoint đọc: đã xem gần đây + trending + gợi ý cho bạn
- [ ] `RecommendationService`: recently_viewed(user), trending(window) có cache, for_you(user) có cache + fallback trending.
- [ ] `RecommendationController`: `/recently-viewed`, `/trending`, `/for-you`.
- [ ] DTO response; tái dùng `_to_dtos` (sau khi tối ưu N+1) để dựng sản phẩm.
- [ ] Test: cold-start -> trending; user có affinity -> đúng thứ tự; loại sản phẩm đã mua.

### Phase 5 - Mua/xem cùng (co-occurrence, batch)
- [ ] Migration: bảng `product_cooccurrence`.
- [ ] `ProductCooccurrenceRepository` (top_related(product, limit), bulk upsert).
- [ ] `CooccurrenceService.rebuild()`: quét order_details (đồng mua) [+ interactions], dựng top-K mỗi product.
- [ ] Endpoint admin `POST /api/admin/recommendations/rebuild-cooccurrence` (quyền manage_recommendations).
- [ ] Endpoint công khai `GET /api/products/{id}/related`.
- [ ] Test: rebuild từ vài đơn mẫu cho ra cặp đúng; related trả theo count giảm dần.

### Phase 6 - Lệnh sửa chữa + tài liệu
- [ ] Endpoint admin "rebuild affinity" (quét lại interactions dựng lại bảng) - phòng sai lệch/đổi công thức.
- [ ] Cập nhật `phan-quyen.md` (quyền mới), `review-test-2026-06-29.md`, file này (trạng thái phase).

---

## Điểm còn phải quyết (hỏi trước khi tới phase liên quan)

1. **Làm tươi co-occurrence:** Xime có scheduler không? Nếu không -> dùng endpoint admin + cron ngoài
   (vd gọi hằng đêm). Cần xác nhận hướng trước Phase 5.
2. **User ẩn danh:** trước mắt chỉ cá nhân hóa user đăng nhập. Có muốn theo dõi ẩn danh qua session/cookie
   để gộp khi đăng nhập không? (Mặc định: KHÔNG, đơn giản trước.)
3. **HALF_LIFE và WINDOW:** mặc định 30 ngày (half-life affinity) và 14 ngày (cửa sổ trending) - chỉnh sau khi có dữ liệu thật.

## Backlog (ghi để nhớ, không làm lần này)

- Cảnh báo giảm giá cho sản phẩm trong wishlist.
- Gợi ý bổ trợ chéo ngành theo luật (mua giày -> gợi ý tất).
- Affinity theo thuộc tính (brand/màu) ngoài category.
- Theo dõi + gộp lịch sử người dùng ẩn danh.
