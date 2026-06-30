# Kế hoạch tối ưu N+1 cho Product / Variant (Attribute - Option)

> Mục tiêu: gỡ N+1 query trong luồng đọc sản phẩm + biến thể, thêm index/ràng buộc DB.
> Giữ nguyên hành vi nghiệp vụ (DTO trả ra không đổi). Làm từng phase nhỏ, test kỹ mỗi bước.
> Nền tảng: kiến trúc đa lớp (controller -> service -> repository), một tiến trình, không Redis.

> ✅ **ĐÃ HOÀN TẤT (2026-06-30):** Phase 1-5 + 7 xong, full suite **103 passed** (100 cũ + 3 test
> batch mới). Phase 6 (cache trang list) bỏ qua vì list đã xuống ~4 query, ưu tiên thấp.
> Migration `c3e4a5b6d7f8` (5 index + 2 UNIQUE) đã áp vào DB, up/down sạch.

## Bối cảnh mô hình

Mô hình variant/SKU chuẩn (giống Shopify/Magento), KHÔNG phải EAV thuần - giữ nguyên, không đổi:

| Bảng | Vai trò |
|---|---|
| `product_attributes` (product_id, name) | Loại lựa chọn: Size, Color (tên gọi "option" của sàn) |
| `product_attribute_values` (attribute_id, value) | Giá trị: 40, 41, Đỏ |
| `product_options` (product_id, price, stock) | 1 tổ hợp hoàn chỉnh = 1 SKU/variant bán được |
| `product_option_values` (option_id, attribute_value_id) | Bảng nối SKU <-> các giá trị |

## Phân tích N+1 hiện tại (đo theo code)

`ProductService._to_dto(product)` gọi cho **mỗi** sản phẩm:

- `_get_attributes_dict(pid)`: 1 query (attributes) + **N_attr** query (mỗi attribute 1 lần lấy values)
- `_get_price_and_stock(pid)`: 1 query (options) + **N_opt** query (mỗi option lấy option_values, nhánh nhiều option)

`get_paginated_product_dtos` / `get_all_product_dtos` / `get_managed_product_dtos` /
`get_products_by_category_id` / `search_products_by_keywords` đều **lặp `_to_dto` qua từng sản phẩm**.

> Trang 10 sản phẩm, mỗi cái 2 thuộc tính + 3 variant ~= 10 x (1 + 2 + 1 + 3) = **~70 query/trang**.
> `get_paginated_product_dtos` (GET /api/products công khai) **KHÔNG cache** -> chậm mỗi request.

Chỗ nóng thứ hai: `find_product_option_by_json` (người mua chọn size/màu -> lấy giá): load tất cả
option của product, rồi **mỗi option** lại load option_values để so set -> 1 + N_opt query.

**Khuếch đại bởi DB:** Postgres KHÔNG tự tạo index cho khóa ngoại. Hiện `attribute_id`,
`option_id`, `product_id`, `attribute_value_id` chưa có index -> mỗi `find_by_*_id` quét tuần tự.

## Mục tiêu sau tối ưu

- List M sản phẩm: từ `M x (N+1)` xuống **~4 query cố định** (bất kể M, N_attr, N_opt).
- `find_product_option_by_json`: từ `1 + N_opt` xuống **2 query**.
- Mọi FK có index; (tùy chọn) UNIQUE chặn dữ liệu rác.
- DTO trả ra **không đổi** (regression test khóa hành vi).

## Chiến lược kỹ thuật

Dùng **batch query `WHERE col IN (...)`** ở tầng repository, gom + ráp trong RAM ở tầng service.
KHÔNG dùng `relationship()`/`selectinload` để né bẫy lazy-load async mà rule
[`dto-va-validation.md`](../rules/dto-va-validation.md) đã cảnh báo, và để bám kiến trúc đa lớp
(repo trả list entity, service ráp DTO).

---

## Phase 1 - Index + (tùy chọn) UNIQUE [migration, rủi ro thấp]

Tách riêng vì không đụng code Python, thấy kết quả ngay.

- [ ] Tạo migration mới `..._add_product_variant_indexes.py`, `down_revision = "b2d3f4a5c6e7"` (head hiện tại).
- [ ] `op.create_index` cho:
  - `product_attributes(product_id)`
  - `product_attribute_values(attribute_id)`
  - `product_options(product_id)`
  - `product_option_values(option_id)`
  - `product_option_values(attribute_value_id)`
- [ ] UNIQUE (chỉ thêm nếu dữ liệu hiện tại KHÔNG vi phạm - kiểm tra trước bằng truy vấn `GROUP BY ... HAVING COUNT(*)>1`):
  - `UNIQUE(product_attributes.product_id, name)`
  - `UNIQUE(product_option_values.option_id, attribute_value_id)`
  - Nếu có bản ghi trùng -> **dừng, báo người dùng**, không tự xóa dữ liệu (theo quy ước không xóa khi chưa hỏi). Index vẫn thêm bình thường.
- [ ] (Nên) Thêm `index=True` cho các cột FK tương ứng trong entity để DB và model đồng bộ về sau. Ghi chú: migration là nguồn sự thật, entity chỉ để khớp khi tạo mới.
- [ ] `alembic upgrade head` trên DB dev; kiểm tra `\d` các bảng có index; chạy full test (phải vẫn pass).
- [ ] Kiểm tra `alembic downgrade -1` chạy được rồi `upgrade head` lại.

## Phase 2 - Batch method ở repository [gỡ N+1 tầng repo]

Thêm các method `WHERE ... IN (...)`, trả rỗng nếu input rỗng (tránh `IN ()` lỗi SQL):

- [ ] `ProductAttributeRepository.find_by_product_ids(product_ids: set[int]) -> list[ProductAttribute]`
- [ ] `ProductAttributeValueRepository.find_by_attribute_ids(attribute_ids: set[int]) -> list[ProductAttributeValue]`
- [ ] `ProductOptionRepository.find_by_product_ids(product_ids: set[int]) -> list[ProductOption]`
- [ ] `ProductOptionValueRepository.find_by_option_ids(option_ids: set[int]) -> list[ProductOptionValue]`
- [ ] Mỗi method `order_by(id)` để thứ tự values/options ổn định, deterministic.

## Phase 3 - Batch method ở sub-service [ủy thác]

Giữ ProductService nói chuyện qua sub-service (không gọi thẳng repo attr/option), thêm:

- [ ] `ProductAttributeService.find_by_product_ids(product_ids)`
- [ ] `ProductAttributeValueService.find_by_attribute_ids(attribute_ids)`
- [ ] `ProductOptionService.find_by_product_ids(product_ids)`
- [ ] `ProductOptionValueService.find_by_option_ids(option_ids)`
- [ ] Tất cả transaction-agnostic (không tự mở transaction), chạy trong transaction của ProductService.

## Phase 4 - `_to_dtos` gộp trong ProductService [trọng tâm]

- [ ] Viết `_to_dtos(products: list[Product]) -> list[dict]` (chạy trong transaction đang mở):
  1. `product_ids = {p.id}`; rỗng -> trả `[]`.
  2. Batch: attributes theo product_ids -> gom `attrs_by_product`; thu `attr_ids`.
  3. Batch: attribute_values theo attr_ids -> gom `vals_by_attr`.
  4. Batch: options theo product_ids -> gom `opts_by_product`; thu `option_ids`.
  5. Batch: option_values theo option_ids -> gom `optvals_by_option`.
  6. Mỗi product: ráp `attribute` dict + tính price/stock **từ map trong RAM** (0 query thêm).
- [ ] Tách 2 helper thuần RAM, GIỮ NGUYÊN logic cũ từng ký tự:
  - `_build_attributes(attrs, vals_by_attr)` == logic `_get_attributes_dict`: `{attr.name: [v.value, ...]}`.
  - `_calc_price_stock(opts, optvals_by_option)` == logic `_get_price_and_stock`:
    - đúng 1 option -> dùng option đó (price, stock) kể cả khi có values;
    - nhiều option -> chỉ tính option CÓ values; `price = min(prices)` (price not None) hoặc None; `stock = sum(stock)`;
    - 0 option -> price None, stock 0.
- [ ] `_to_dto(product)` viết lại = `(await self._to_dtos([product]))[0]` để hợp nhất logic, tránh lệch.
- [ ] Chuyển các method list sang `_to_dtos(products)`: `get_all_product_dtos`, `get_paginated_product_dtos`,
  `get_managed_product_dtos`, `get_products_by_category_id`, `search_products_by_keywords`.
- [ ] Giữ `_get_attributes_dict` / `_get_price_and_stock` nếu nơi khác còn dùng (vd `_find_option_default`,
  `get_option_default` dùng riêng) - chỉ thay ở luồng dựng DTO. Rà soát hết caller trước khi xóa.

### Test Phase 4
- [ ] Toàn bộ test cũ phải pass (DTO không đổi).
- [ ] Test mới: tạo product 2 thuộc tính + nhiều variant qua seed/fixture, so DTO của `_to_dtos`
  bằng đúng `_to_dto` cũ (price, stock, attribute giống hệt).
- [ ] (Tùy chọn) Test đếm query bằng listener `before_cursor_execute`: list N sản phẩm chỉ phát ~4 query,
  không phụ thuộc N. Khóa chống tái diễn N+1.

## Phase 5 - Gỡ N+1 trong `find_product_option_by_json`

- [ ] Resolve target `pav_ids` như cũ.
- [ ] Load options theo product (1 query) + batch option_values theo `option_ids` (1 query), gom theo option_id.
- [ ] So set trong RAM: option có `{ov.attribute_value_id} == target` -> match. Bỏ vòng load từng option.
- [ ] Test: test find-option hiện có pass; thêm test multi-variant chọn đúng SKU + giá.

## Phase 6 (tùy chọn, ưu tiên thấp) - Cache trang list

Sau Phase 4, list đã ~4 query nên đây là phụ. Nếu làm:
- [ ] Cache `get_paginated_product_dtos` theo key `product:list:{page}:{limit}`.
- [ ] Vấn đề invalidation theo trang: dùng **generation counter** trong cache (key chứa generation),
  mỗi lần write bump generation -> mọi key cũ thành bất khả truy + hết hạn theo TTL. Tránh phải xóa từng key.
- [ ] Cập nhật `_invalidate_product_cache` bump generation.

## Phase 7 - Tài liệu

- [ ] Cập nhật trạng thái các phase trong file này.
- [ ] Ghi tóm tắt vào [`review-test-2026-06-29.md`](review-test-2026-06-29.md) (mục N+1 product).
- [ ] Nếu thêm UNIQUE/đổi mô hình: ghi quyết định vào [`quyet-dinh-thiet-ke.md`](quyet-dinh-thiet-ke.md).

---

## Nguyên tắc thực thi

- Làm tuần tự Phase 1 -> 5; mỗi phase chạy full test trước khi sang phase sau.
- Phase 6 tùy chọn, hỏi lại trước khi làm.
- Không xóa dữ liệu/khóa khi gặp bản ghi trùng ở Phase 1 - dừng và hỏi.
- Comment code: tiếng Anh trên, tiếng Việt dưới. Không dùng dấu gạch ngang dài.

## Backlog (không làm lần này, ghi để nhớ)

- Thêm `sku`, `barcode`, ảnh riêng, `position` (thứ tự hiển thị) cho variant/attribute - đúng chuẩn sàn.
- Tách "default option" (option không có value) ra khỏi bảng variant thật - bỏ nợ kỹ thuật trong `_calc_price_stock`.
