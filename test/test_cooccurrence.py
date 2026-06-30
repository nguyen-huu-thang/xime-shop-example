"""
Test đơn vị cho CooccurrenceService._count_cooccurrence (thuần RAM, không DB).

Đếm đồng mua: mỗi đơn sinh các cặp sản phẩm có hướng; count = số đơn chứa cả hai. Không cặp tự thân.

Chạy: pytest test/test_cooccurrence.py -v
"""
from __future__ import annotations

from app.service.cooccurrence_service import CooccurrenceService


def test_count_cooccurrence_pairs_and_counts():
    # Đơn 1 = {10,20,30}; Đơn 2 = {10,20}
    pairs = [(1, 10), (1, 20), (1, 30), (2, 10), (2, 20)]
    rows = CooccurrenceService._count_cooccurrence(pairs)
    d = {(a, b): c for a, b, c in rows}

    # (10,20) xuất hiện ở cả 2 đơn -> 2 (cả hai chiều)
    assert d[(10, 20)] == 2
    assert d[(20, 10)] == 2
    # (10,30) chỉ ở đơn 1 -> 1
    assert d[(10, 30)] == 1
    assert d[(30, 10)] == 1
    # Không có cặp tự thân
    assert (10, 10) not in d
    assert (20, 20) not in d


def test_count_cooccurrence_single_item_order_no_pairs():
    # Đơn chỉ 1 sản phẩm -> không sinh cặp nào
    rows = CooccurrenceService._count_cooccurrence([(1, 10)])
    assert rows == []


def test_count_cooccurrence_empty():
    assert CooccurrenceService._count_cooccurrence([]) == []
