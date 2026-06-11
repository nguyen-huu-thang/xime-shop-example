# Issue #1 — `TestApplication` gây cảnh báo pytest collection

- **Mức độ:** Thấp (cosmetic, không ảnh hưởng chức năng)
- **Phase phát hiện:** Phase 0 (viết test health-check)
- **Thành phần:** `xime.testing.TestApplication`

## Hiện tượng

Khi import `TestApplication` từ `xime.testing` vào file test, pytest in cảnh báo:

```
PytestCollectionWarning: cannot collect test class 'TestApplication' because it has a
__init__ constructor (from: test/test_phase0_health.py)
  class TestApplication:
```

Nguyên nhân: pytest tự động coi mọi class tên bắt đầu bằng `Test*` là test class cần thu thập.
`TestApplication` là tiện ích test (có `__init__`) nên pytest cảnh báo không thu thập được.

## Ảnh hưởng

- Không ảnh hưởng kết quả test (test vẫn chạy + pass).
- Chỉ gây nhiễu cảnh báo mỗi lần chạy pytest.

## Đề xuất cho framework

1. Đổi tên class → ví dụ `XimeTestApp` / `IntegrationTestApp` / `AppHarness` (tránh tiền tố `Test`).
   Vẫn có thể giữ alias `TestApplication` để tương thích ngược.
2. Hoặc đặt thuộc tính `__test__ = False` trên class để pytest bỏ qua:
   ```python
   class TestApplication:
       __test__ = False  # pytest: không thu thập như test class
   ```
   (Cách 2 đơn giản, không phá vỡ API hiện tại — khuyến nghị.)

## Workaround tạm thời trong dự án này

Chấp nhận cảnh báo (vô hại). Nếu muốn ẩn, có thể thêm filter trong `pyproject.toml`:

```toml
[tool.pytest.ini_options]
filterwarnings = ["ignore::pytest.PytestCollectionWarning"]
```

Hiện **chưa áp dụng** filter để giữ cảnh báo hiển thị minh bạch.
