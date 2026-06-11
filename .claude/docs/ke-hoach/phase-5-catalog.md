# Phase 5 — Catalog (Danh mục & Sản phẩm)

**Mục tiêu:** Category (cây cha-con) + Product + attribute/option (cơ chế tùy chọn sản phẩm) CRUD đầy đủ.

> Nguồn PHP: `CategoryController/Service/Repository`, `ProductController/Service/Repository`,
> `ProductAttribute*`, `ProductOption*`. Nghiệp vụ tùy chọn SP: [`../domain-model.md`](../domain-model.md).

## Bước

### Category
- [x] **5.1** `category_repository.py` — `find_all`, `find(id)`, `find_by_parent_id`.
- [x] **5.2** `category_service.py` — `get_all_categories`, `get_category_by_id`,
  `get_subcategories_by_parent_id`, `create_category`, `update_category`, `delete_category`
  (xóa: gán con + sản phẩm về parent rồi xóa — port đúng `CategoryService::deleteCategory`).
- [x] **5.3** `dto/request/category_request.py` (Create/Update), `dto/response/category_response.py`
  (gồm `hierarchyPath`, `hierarchyPathById` — tính ở service/controller, tránh lazy-load async).
- [x] **5.4** `category_controller.py` — list, detail, create, update, delete, subcategories.
  Áp quyền: create_category/edit_category/delete_category.

### Product + attribute/option
- [x] **5.5** Repository: `product_repository.py` (gồm `find_products_by_category_id`),
  `product_attribute_repository.py`, `product_attribute_value_repository.py`,
  `product_option_repository.py`, `product_option_value_repository.py`.
- [x] **5.6** Service: `product_service.py`, `product_attribute_service.py`,
  `product_attribute_value_service.py`, `product_option_value_service.py` — port nghiệp vụ tổ hợp lựa chọn:
  - Tạo SP → tạo attributes → values → options → option_values.
  - SP không lựa chọn → 1 option duy nhất, attributes rỗng.
  - Tìm option từ tổ hợp attribute_value đã chọn.
- [x] **5.7** DTO request/response cho product + nested options/attributes.
- [x] **5.8** `product_controller.py` — CRUD + quản lý tồn kho (manage_product_stock),
  sản phẩm nổi bật (manage_featured_products). Áp quyền tương ứng.

### Test thủ công
- [ ] **5.9** Tạo category cây 3 cấp, kiểm `hierarchyPath`. Xóa category giữa cây → con + SP dời về parent.
- [ ] **5.10** Tạo SP có 2 thuộc tính (size, màu) → sinh đúng số option = tích các value. Tạo SP không
  lựa chọn → 1 option. Tìm option theo tổ hợp.

## Đầu ra

Catalog CRUD hoàn chỉnh, cơ chế tùy chọn sản phẩm đúng nghiệp vụ.

## Rủi ro / cần xác minh

- Logic sinh tổ hợp option khá phức tạp — đọc kỹ `ProductOptionValueService.php`,
  `ProductService.php` trước khi code.
- Lazy-load quan hệ cha (category) trong async — dùng eager-load khi build hierarchy.
- `is_delete` (soft delete) của product — đối chiếu cách PHP lọc.
