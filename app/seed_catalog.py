"""
Seed dữ liệu catalog (demo) từ dump PHP cũ.

Nạp lại sản phẩm / danh mục / biến thể / ảnh / đánh giá từ bản dump PostgreSQL
của dự án PHP cũ (`web.sql`) vào DB dự án Python, để khỏi nhập tay từ đầu.

Restore demo catalog data from the legacy PHP PostgreSQL dump.

Chạy:  python -m app.seed_catalog
Idempotent: bỏ qua các bản ghi đã tồn tại (so theo id / code), chạy lại an toàn.

LƯU Ý:
- Dữ liệu THẬT (giữ nguyên): categories, products, product_attributes,
  product_attribute_values, product_options, product_option_values, files, reviews, wishlist.
- Dữ liệu ẢO / chỉnh: users (đặt lại mật khẩu demo, bỏ hash PHP cũ), coupons (tạo mới theo
  schema coupon đã nâng cấp).
- Ảnh vật lý: copy thủ công thư mục `public/data` từ dự án PHP sang (đã làm khi seed lần đầu).
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import Boolean, DateTime, Integer, Numeric, insert, select, text
from sqlalchemy.sql.sqltypes import BigInteger, SmallInteger

from xime import Application
from xime.starters.sqlalchemy import Base, SqlAlchemyTransactionManager
from xime.starters.sqlalchemy.session import AsyncSessionFactory

# Import entity để Base.metadata có đủ bảng (table objects dùng để insert).
# Import entities so Base.metadata is populated with the target tables.
import app.entity.category  # noqa: F401
import app.entity.coupon  # noqa: F401
import app.entity.file  # noqa: F401
import app.entity.list_table  # noqa: F401
import app.entity.product  # noqa: F401
import app.entity.product_attribute  # noqa: F401
import app.entity.product_attribute_value  # noqa: F401
import app.entity.product_option  # noqa: F401
import app.entity.product_option_value  # noqa: F401
import app.entity.review  # noqa: F401
import app.entity.user  # noqa: F401
import app.entity.wishlist  # noqa: F401
from app.service.user_service import UserService

# Đường dẫn bản dump PHP cũ. Sửa nếu bạn để file ở nơi khác.
# Path to the legacy PHP dump.
LEGACY_DUMP = Path(r"D:\code\PHP\shop-backend\web.sql")

# Mật khẩu demo dùng chung cho tất cả tài khoản import (bỏ hash PHP cũ).
DEMO_PASSWORD = "Demo@123"

# Các bảng cần lấy từ dump + thứ tự insert (tôn trọng khóa ngoại).
# Tables to pull from the dump, in FK-safe insert order.
CATALOG_TABLES = [
    "list_table",
    "categories",
    "products",
    "product_attributes",
    "product_attribute_values",
    "product_options",
    "product_option_values",
    "files",
    "reviews",
    "wishlist",
]


# ── Parse COPY format ────────────────────────────────────────────────────────

def _unescape(field: str) -> str | None:
    r"""Giải mã 1 field theo COPY text format (\N = null, \n \t \r \\ ...)."""
    if field == r"\N":
        return None
    out: list[str] = []
    i = 0
    mapping = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\"}
    while i < len(field):
        c = field[i]
        if c == "\\" and i + 1 < len(field):
            nxt = field[i + 1]
            out.append(mapping.get(nxt, nxt))
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def parse_copy_blocks(text: str, wanted: set[str]) -> dict[str, tuple[list[str], list[list]]]:
    """Trích các khối COPY của những bảng cần, trả {table: (columns, rows)}."""
    result: dict[str, tuple[list[str], list[list]]] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("COPY public."):
            # COPY public.<table> (col1, col2, ...) FROM stdin;
            head = line[len("COPY public."):]
            table = head[: head.index(" ")]
            cols_part = head[head.index("(") + 1 : head.index(")")]
            columns = [c.strip() for c in cols_part.split(",")]
            i += 1
            rows: list[list] = []
            while i < len(lines) and lines[i] != "\\.":
                fields = lines[i].split("\t")
                rows.append([_unescape(f) for f in fields])
                i += 1
            if table in wanted:
                result[table] = (columns, rows)
        i += 1
    return result


# ── Convert giá trị theo kiểu cột đích ───────────────────────────────────────

def _convert(value, col_type):
    if value is None:
        return None
    if isinstance(col_type, Boolean):
        return value == "t"
    if isinstance(col_type, (Integer, BigInteger, SmallInteger)):
        return int(value)
    if isinstance(col_type, Numeric):
        return Decimal(value)
    if isinstance(col_type, DateTime):
        # Dump dạng 'YYYY-MM-DD HH:MM:SS' (naive) -> datetime.
        return datetime.fromisoformat(value)
    return value


def _rows_as_dicts(table_name: str, columns: list[str], rows: list[list]) -> list[dict]:
    table = Base.metadata.tables[table_name]
    col_types = {c: table.columns[c].type for c in columns}
    out: list[dict] = []
    for raw in rows:
        out.append({col: _convert(val, col_types[col]) for col, val in zip(columns, raw)})
    return out


# ── Seed ─────────────────────────────────────────────────────────────────────

async def _insert_missing(session, table_name: str, dict_rows: list[dict], key: str = "id") -> int:
    """Insert những bản ghi chưa có (so theo `key`). Trả số dòng đã thêm."""
    if not dict_rows:
        return 0
    table = Base.metadata.tables[table_name]
    existing = set(
        (await session.execute(select(table.c[key]))).scalars().all()
    )
    new_rows = [r for r in dict_rows if r.get(key) not in existing]
    # Sắp xếp theo id để thỏa self-FK (vd categories.parent_id < id).
    if new_rows and key == "id" and all(isinstance(r.get("id"), int) for r in new_rows):
        new_rows.sort(key=lambda r: r["id"])
    if new_rows:
        await session.execute(insert(table), new_rows)
    return len(new_rows)


async def _reset_sequence(session, table_name: str) -> None:
    """Đặt lại sequence id về MAX(id) để insert sau không đụng id thủ công.

    table_name lấy từ whitelist cố định nên nội suy thẳng vào câu lệnh là an toàn.
    """
    await session.execute(
        text(
            f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
            f"GREATEST(COALESCE((SELECT MAX(id) FROM {table_name}), 0), 1))"
        )
    )


def _build_user_rows(columns: list[str], rows: list[list]) -> list[dict]:
    """Dựng user demo: giữ id/username/email/phone/address, đặt lại mật khẩu demo."""
    raw_dicts = _rows_as_dicts("users", columns, rows) if "users" in Base.metadata.tables else []
    hashed = UserService.hash_password(DEMO_PASSWORD)
    users: list[dict] = []
    for r in raw_dicts:
        users.append({
            "id": r["id"],
            "username": r["username"],
            "email": r["email"],
            "password": hashed,
            "phone": r.get("phone"),
            "address": r.get("address"),
            "is_active": True,
            "email_verified": True,
            "is_superadmin": False,
            "created_at": r.get("created_at"),
            "updated_at": r.get("updated_at"),
        })
    return users


def _fake_coupons() -> list[dict]:
    """Vài mã giảm giá demo theo schema coupon đã nâng cấp.

    Mọi dict phải cùng tập khóa - insert nhiều dòng (executemany) yêu cầu đồng nhất.
    """
    now = datetime(2026, 1, 1)
    end = datetime(2026, 12, 31, 23, 59, 59)
    # Field mặc định cho 1 coupon; mỗi mã override phần cần thiết.
    def coupon(**kw) -> dict:
        base = {
            "code": "", "discount": Decimal("0"), "discount_type": "fixed",
            "max_discount": None, "min_order_amount": Decimal("0"),
            "applies_to": "product", "usage_limit": None, "used_count": 0,
            "per_user_once": False, "start_date": now, "end_date": end, "is_active": True,
        }
        base.update(kw)
        return base

    return [
        coupon(code="WELCOME10", discount=Decimal("10"), discount_type="percent",
               max_discount=Decimal("100000"), min_order_amount=Decimal("200000"),
               usage_limit=1000, per_user_once=True),
        coupon(code="SALE50K", discount=Decimal("50000"), discount_type="fixed",
               min_order_amount=Decimal("500000")),
        coupon(code="FREESHIP", discount=Decimal("100"), discount_type="percent",
               max_discount=Decimal("30000"), min_order_amount=Decimal("300000"),
               applies_to="shipping"),
        coupon(code="BIGSALE20", discount=Decimal("20"), discount_type="percent",
               max_discount=Decimal("500000"), min_order_amount=Decimal("1000000"),
               usage_limit=200),
    ]


async def seed_catalog() -> None:
    if not LEGACY_DUMP.exists():
        raise SystemExit(f"Không tìm thấy dump cũ: {LEGACY_DUMP}")

    text = LEGACY_DUMP.read_text(encoding="utf-8")
    wanted = set(CATALOG_TABLES) | {"users"}
    blocks = parse_copy_blocks(text, wanted)

    application = Application()
    await application.start()
    try:
        tm = application.get(SqlAlchemyTransactionManager)
        sessions = application.get(AsyncSessionFactory)

        async with tm():
            session = sessions.current()

            # Guard: nếu đã có sản phẩm thì coi như đã seed (tránh nạp trùng).
            from app.entity.product import Product
            count = (await session.execute(select(Product.id))).scalars().first()
            already = count is not None

            # 1. users demo (đặt lại mật khẩu) - cần trước files/reviews/wishlist.
            if "users" in blocks:
                ucols, urows = blocks["users"]
                added = await _insert_missing(session, "users", _build_user_rows(ucols, urows))
                print(f"users: +{added} (mật khẩu demo = {DEMO_PASSWORD!r})")

            # 2. các bảng catalog theo thứ tự FK.
            for table_name in CATALOG_TABLES:
                if table_name not in blocks:
                    print(f"{table_name}: (không có trong dump, bỏ qua)")
                    continue
                cols, rows = blocks[table_name]
                key = "id"
                dicts = _rows_as_dicts(table_name, cols, rows)
                added = await _insert_missing(session, table_name, dicts, key=key)
                print(f"{table_name}: +{added}/{len(rows)}")

            # 3. coupons ảo theo schema mới.
            added = await _insert_missing(session, "coupons", _fake_coupons(), key="code")
            print(f"coupons (demo): +{added}")

            await session.flush()

            # 4. reset sequence cho mọi bảng serial vừa insert.
            for table_name in [
                "users", "categories", "products", "product_attributes",
                "product_attribute_values", "product_options", "product_option_values",
                "files", "reviews", "wishlist", "coupons",
            ]:
                await _reset_sequence(session, table_name)
            print("Đã reset sequence id.")

            if already:
                print("(Lưu ý: DB đã có sản phẩm từ trước - chỉ thêm bản ghi còn thiếu.)")

        print("Seed catalog hoàn tất.")
    finally:
        await application.stop()


if __name__ == "__main__":
    asyncio.run(seed_catalog())
