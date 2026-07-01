"""
Test đơn vị cho ProductService._to_dtos (batch, chống N+1).

Mục tiêu:
  - Khóa chống N+1: mỗi batch query (attributes/values/options/option_values) chỉ được gọi
    ĐÚNG MỘT LẦN dù danh sách có nhiều sản phẩm. Nếu ai đó vô tình quay lại lặp _to_dto theo
    từng sản phẩm, số lần gọi sẽ tăng theo số sản phẩm và test này gãy.
  - Giá trị DTO đúng ở mọi nhánh của _calc_price_stock: nhiều option (min giá + tổng tồn),
    đúng 1 option (lấy thẳng), 0 option (giá None, tồn 0); và ráp attribute đúng.

Dùng fake sub-service (không chạm DB), theo phong cách test_authz_upgrade.py.
Chạy: pytest test/test_product_dto_batch.py -v
"""
from __future__ import annotations

import pytest

from app.service.product_service import ProductService


# ─── Fake entity nhẹ (chỉ các thuộc tính _to_dtos đọc tới) ───────────────────

class _Prod:
    def __init__(self, id, category_id=None):
        self.id = id
        self.name = f"Prod {id}"
        self.location_address = "HN"
        self.category_id = category_id
        self.description = None
        self.discount_percentage = 0


class _Attr:
    def __init__(self, id, product_id, name):
        self.id = id
        self.product_id = product_id
        self.name = name


class _Val:
    def __init__(self, id, attribute_id, value):
        self.id = id
        self.attribute_id = attribute_id
        self.value = value


class _Opt:
    def __init__(self, id, product_id, price, stock):
        self.id = id
        self.product_id = product_id
        self.price = price
        self.stock = stock


class _OptVal:
    def __init__(self, id, option_id, attribute_value_id):
        self.id = id
        self.option_id = option_id
        self.attribute_value_id = attribute_value_id


class _File:
    def __init__(self, id, target_id, file_path, sort=1):
        self.id = id
        self.target_id = target_id
        self.file_path = file_path
        self.sort = sort
        self.is_active = True
        self.list_table_id = "products"


# ─── Fake sub-service: trả dữ liệu đã chuẩn bị + đếm số lần gọi ──────────────

class _FakeAttrSvc:
    def __init__(self, rows):
        self._rows = rows
        self.calls = 0

    async def find_by_product_ids(self, product_ids):
        self.calls += 1
        return [a for a in self._rows if a.product_id in product_ids]


class _FakeValSvc:
    def __init__(self, rows):
        self._rows = rows
        self.calls = 0

    async def find_by_attribute_ids(self, attribute_ids):
        self.calls += 1
        return [v for v in self._rows if v.attribute_id in attribute_ids]


class _FakeOptSvc:
    def __init__(self, rows):
        self._rows = rows
        self.calls = 0

    async def find_by_product_ids(self, product_ids):
        self.calls += 1
        return [o for o in self._rows if o.product_id in product_ids]


class _FakeOptValSvc:
    def __init__(self, rows):
        self._rows = rows
        self.calls = 0

    async def find_by_option_ids(self, option_ids):
        self.calls += 1
        return [ov for ov in self._rows if ov.option_id in option_ids]


class _FakeFileRepo:
    def __init__(self, rows):
        self._rows = rows
        self.calls = 0

    async def find_active_by_targets(self, table_name, target_ids):
        self.calls += 1
        rows = [f for f in self._rows if f.target_id in target_ids]
        # Mô phỏng ORDER BY target_id, sort, id của query thật.
        rows.sort(key=lambda f: (f.target_id, f.sort, f.id))
        return rows


def _make_service():
    """Dựng ProductService chỉ với 4 sub-service fake; phần còn lại None (không dùng trong _to_dtos).

    Kịch bản 3 sản phẩm:
      - P1: thuộc tính Size[40,41] + Color[Red]; 2 option (100/stock5, 120/stock3) đều có value.
            -> price = min(100,120) = 100, stock = 5+3 = 8.
      - P2: không thuộc tính; đúng 1 option (50/stock9, không value) -> price 50, stock 9.
      - P3: không thuộc tính, không option -> price None, stock 0.
    """
    attrs = [
        _Attr(10, 1, "Size"),
        _Attr(11, 1, "Color"),
    ]
    vals = [
        _Val(100, 10, "40"),
        _Val(101, 10, "41"),
        _Val(102, 11, "Red"),
    ]
    opts = [
        _Opt(1000, 1, 100, 5),
        _Opt(1001, 1, 120, 3),
        _Opt(2000, 2, 50, 9),
    ]
    optvals = [
        _OptVal(1, 1000, 100),  # opt1000 -> 40
        _OptVal(2, 1000, 102),  # opt1000 -> Red
        _OptVal(3, 1001, 101),  # opt1001 -> 41
        _OptVal(4, 1001, 102),  # opt1001 -> Red
        # opt2000 (P2) không có value -> là option mặc định
    ]
    # P1 có 2 ảnh (sort 2 và 1) -> ảnh đại diện là sort nhỏ nhất; P2/P3 không ảnh.
    files = [
        _File(900, 1, "ab/cd/img-late.webp", sort=2),
        _File(901, 1, "ab/cd/img-main.webp", sort=1),
    ]
    # transaction, cache, product_repo, category_repo = None; file_repo + 4 sub-service là fake.
    svc = ProductService(None, None, None, None, _FakeFileRepo(files),
                         _FakeAttrSvc(attrs), _FakeValSvc(vals),
                         _FakeOptSvc(opts), _FakeOptValSvc(optvals))
    return svc


@pytest.mark.asyncio
async def test_to_dtos_batch_calls_each_query_once():
    """Chống N+1: mỗi batch method chỉ gọi 1 lần dù có 3 sản phẩm."""
    svc = _make_service()
    products = [_Prod(1, 5), _Prod(2, 6), _Prod(3, 7)]
    dtos = await svc._to_dtos(products)

    assert svc._attr_svc.calls == 1
    assert svc._attr_val_svc.calls == 1
    assert svc._option_svc.calls == 1
    assert svc._option_val_svc.calls == 1
    assert svc._file_repo.calls == 1  # ảnh cũng batch 1 query
    assert len(dtos) == 3


@pytest.mark.asyncio
async def test_to_dtos_values_correct_all_branches():
    """Giá trị DTO đúng ở 3 nhánh tính giá/tồn + ráp attribute đúng."""
    svc = _make_service()
    dtos = await svc._to_dtos([_Prod(1, 5), _Prod(2, 6), _Prod(3, 7)])
    by_id = {d["id"]: d for d in dtos}

    # P1: nhiều option có value -> min giá, tổng tồn; attribute đầy đủ
    p1 = by_id[1]
    assert p1["price"] == 100
    assert p1["stock"] == 8
    assert p1["attribute"] == {"Size": ["40", "41"], "Color": ["Red"]}
    assert p1["categoryId"] == 5
    # Ảnh đại diện = file sort nhỏ nhất; P2/P3 không ảnh -> None
    assert p1["imageUrl"] == "ab/cd/img-main.webp"

    # P2: đúng 1 option -> lấy thẳng; không attribute
    p2 = by_id[2]
    assert p2["price"] == 50
    assert p2["stock"] == 9
    assert p2["attribute"] == {}
    assert p2["imageUrl"] is None

    # P3: không option -> giá None, tồn 0
    p3 = by_id[3]
    assert p3["price"] is None
    assert p3["stock"] == 0
    assert p3["attribute"] == {}
    assert p3["imageUrl"] is None


@pytest.mark.asyncio
async def test_to_dtos_empty_list_no_query():
    """Danh sách rỗng -> trả [] và KHÔNG phát query nào."""
    svc = _make_service()
    dtos = await svc._to_dtos([])
    assert dtos == []
    assert svc._attr_svc.calls == 0
    assert svc._option_svc.calls == 0
