"""
Test đơn vị cho ActionRegistry + ActionService (cache RAM bảng actions, không chạm DB).

  - Registry: load/get_by_name/get_by_id/invalidate.
  - Service: nạp một lần (load-once), get_score trả đúng trọng số, 0 nếu không có action,
    và chỉ truy vấn repo MỘT lần dù gọi nhiều lần (cho tới khi invalidate).

Theo phong cách test_product_dto_batch.py: dùng fake, nhanh, ổn định.
Chạy: pytest test/test_action_registry.py -v
"""
from __future__ import annotations

import pytest

from app.cache.action_registry import ActionRegistry
from app.service.action_service import ActionService


class _Action:
    def __init__(self, id, name, score):
        self.id = id
        self.name = name
        self.score = score


class _FakeRepo:
    def __init__(self, rows):
        self._rows = rows
        self.calls = 0

    async def find_all(self):
        self.calls += 1
        return list(self._rows)


class _FakeTxn:
    """async context manager giả - ActionService._ensure_loaded bọc find_all trong transaction."""
    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _make_service():
    rows = [
        _Action(1, "view", 1),
        _Action(2, "add_to_cart", 5),
        _Action(3, "purchase", 10),
    ]
    repo = _FakeRepo(rows)
    return ActionService(_FakeTxn(), repo, ActionRegistry()), repo


# ─── ActionRegistry (pure) ───────────────────────────────────────────────────

def test_registry_load_and_lookup():
    reg = ActionRegistry()
    assert reg.is_loaded() is False
    reg.load([_Action(1, "view", 1), _Action(2, "purchase", 10)])
    assert reg.is_loaded() is True
    assert reg.get_by_name("view").score == 1
    assert reg.get_by_id(2).name == "purchase"
    assert reg.get_by_name("khong_co") is None
    assert len(reg.all()) == 2


def test_registry_invalidate_resets():
    reg = ActionRegistry()
    reg.load([_Action(1, "view", 1)])
    reg.invalidate()
    assert reg.is_loaded() is False
    assert reg.get_by_name("view") is None
    assert reg.all() == []


# ─── ActionService ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_service_get_score():
    svc, _ = _make_service()
    assert await svc.get_score("purchase") == 10
    assert await svc.get_score("view") == 1
    # Action không tồn tại -> score 0 (an toàn cho tính điểm)
    assert await svc.get_score("khong_co") == 0


@pytest.mark.asyncio
async def test_service_loads_once_until_invalidate():
    svc, repo = _make_service()
    await svc.get_score("view")
    await svc.get_score("purchase")
    await svc.get_by_name("add_to_cart")
    assert repo.calls == 1  # load-once: chỉ truy vấn repo 1 lần

    svc.invalidate()
    await svc.get_score("view")
    assert repo.calls == 2  # sau invalidate -> nạp lại
