# Phase 8 — Phụ trợ (Search, ListTable, Interaction/Action)

**Mục tiêu:** Tìm kiếm sản phẩm + các bảng phụ trợ.

> Nguồn PHP: `SearchController`, `ListTableController/Service`, `ActionService`, `InteractionService`.

## Bước

### Search
- [x] **8.1** Đọc `SearchController.php` để nắm tiêu chí tìm kiếm (theo tên, danh mục, popularity...).
- [x] **8.2** `search_service.py` — query sản phẩm theo từ khóa/bộ lọc, sắp xếp theo relevance score.
- [x] **8.3** `search_controller.py`. Không cần DTO riêng — query params thuần.

### ListTable
- [x] **8.4** `list_table_service.py` — đầy đủ CRUD + sync_list_table() (đã làm Phase 7 + mở rộng Phase 8).
- [x] **8.5** Seed `list_tables` trong `seed.py` — idempotent, 24 bảng.

### Interaction / Action (tùy chọn)
- [x] **8.6** Bỏ qua — schema đã có Phase 2, logic "để làm màu" per kế hoạch.

### Test thủ công
- [ ] **8.7** Tìm kiếm trả đúng sản phẩm, sắp xếp theo popularity.

## Đầu ra

Tìm kiếm hoạt động; bảng phụ trợ sẵn sàng.

## Rủi ro / cần xác minh

- Mức độ phức tạp của search (full-text? chỉ LIKE?) — đọc PHP để quyết định, không over-engineer.
