# Phase 0 — Scaffold & Môi trường

**Mục tiêu:** Có cây thư mục, cài Xime + dependency, app chạy được rỗng với 1 endpoint health-check.

## Bước

- [x] **0.1** Xác minh cách cài/dùng Xime. ✅ Xime cài **editable** tại `D:\code\xime\xime framework`,
  import `from xime import Application, BindingConfig`, `from xime.adapters.web import WebAdapter, get, post`.
- [x] **0.2** Tạo `pyproject.toml` với dependency: sqlalchemy[asyncio], asyncpg, alembic, pydantic,
  pyjwt[crypto], passlib[bcrypt], pyyaml, python-multipart. DB là **PostgreSQL** → driver `asyncpg`.
- [x] **0.3** Tạo cây thư mục đa lớp + `__init__.py` cho mọi package.
- [x] **0.4** Tạo `app/main.py`: `Application().use(WebAdapter()).run()`.
- [x] **0.5** Tạo `app/config/dependency.py` — scan `app.controller/service/repository/security`.
- [x] **0.6** Tạo `app/config/web.py` với `configure_controllers("app.controller")` + `configure_openapi(...)`.
  (Dùng `web.py` thay `routing.py` — framework tự import mọi module trong `app.config`.)
- [x] **0.7** Tạo `resources/application.yml`: host + **port 8088** (8080 bị Apache/XAMPP chiếm) + database url.
- [x] **0.8** Tạo `app/controller/health_controller.py`: `GET /api/health` → `{"status": "ok"}`.
- [x] **0.9** Chạy `python -m app.main`, gọi `/api/health` → **200** `{"status":"ok"}`; `/openapi.json` đúng.
- [x] **0.10** Tạo `.gitignore` đầy đủ (secrets, `.env`, keys, `__pycache__`, db cục bộ, runtime...).
- [x] **0.11** Viết test `test/test_phase0_health.py` (2 test: health + openapi) — **PASSED**.

## Đầu ra

✅ App Xime khởi động sạch trên port 8088, health-check trả 200, Swagger hiển thị. Cây thư mục đa lớp
sẵn sàng. Test tự động pass.

## Ghi chú đã chốt

- **Chạy app:** `python -m app.main` (KHÔNG phải `python app/main.py` — cần package `app` để auto-discover config).
- **Port 8088** thay vì 8080 (8080 bị Apache/XAMPP của dự án PHP chiếm).
- Framework tự import các module trong `app.config` (web.py...) sau khi tìm thấy `dependency` — không cần
  khai báo thêm.
- Vấn đề framework nhỏ phát hiện: [`framework-issues/issue-001`](../../framework-issues/issue-001-testapplication-pytest-collection.md).
