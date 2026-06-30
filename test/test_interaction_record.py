"""
Test đơn vị cho InteractionService.record() (throttle + fault-tolerant), không chạm DB.

  - Action không tồn tại -> không ghi, không raise.
  - Tín hiệu yếu (view) bị throttle: ghi 2 lần liên tiếp chỉ lưu 1.
  - Tín hiệu mạnh (purchase) không throttle: ghi 2 lần lưu 2.
  - Lỗi khi save -> record() KHÔNG raise (không phá hành động chính).

Dùng fake, theo phong cách test_product_dto_batch.py / test_action_registry.py.
Chạy: pytest test/test_interaction_record.py -v
"""
from __future__ import annotations

import pytest

from app.entity.interaction import Interaction
from app.service.interaction_service import InteractionService


class _FakeAction:
    def __init__(self, id, name, score=1):
        self.id = id
        self.name = name
        self.score = score


class _FakeActionSvc:
    def __init__(self, actions):
        self._by_name = {a.name: a for a in actions}

    async def get_by_name(self, name):
        return self._by_name.get(name)


class _FakeIntRepo:
    def __init__(self, save_raises=False):
        self.saved: list[Interaction] = []
        self._save_raises = save_raises

    async def exists_recent(self, user_id, product_id, action_id, since):
        # Bỏ qua thời gian (test gọi trong cùng cửa sổ): coi như trùng nếu đã lưu cùng bộ khóa.
        return any(
            s.user_id == user_id
            and s.product_id == product_id
            and s.action_id == action_id
            for s in self.saved
        )

    async def save(self, interaction):
        if self._save_raises:
            raise RuntimeError("DB down")
        self.saved.append(interaction)
        return interaction


class _FakeTxn:
    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeProduct:
    def __init__(self, category_id):
        self.category_id = category_id


class _FakeProductRepo:
    def __init__(self, category_id=5):
        self._category_id = category_id

    async def find(self, product_id):
        return _FakeProduct(self._category_id)


class _FakeAffinitySvc:
    def __init__(self):
        self.calls = []

    async def apply(self, user_id, category_id, add_score, now=None):
        self.calls.append((user_id, category_id, add_score))


def _make(actions=None, save_raises=False):
    actions = actions or [_FakeAction(1, "view", 1), _FakeAction(2, "purchase", 10)]
    repo = _FakeIntRepo(save_raises=save_raises)
    affinity = _FakeAffinitySvc()
    svc = InteractionService(
        _FakeTxn(), repo, _FakeActionSvc(actions), affinity, _FakeProductRepo()
    )
    return svc, repo, affinity


@pytest.mark.asyncio
async def test_record_unknown_action_no_save():
    svc, repo, affinity = _make()
    await svc.record(1, 100, "khong_ton_tai")
    assert repo.saved == []
    assert affinity.calls == []  # action không hợp lệ -> không đụng affinity


@pytest.mark.asyncio
async def test_record_view_is_throttled():
    svc, repo, _ = _make()
    await svc.record(1, 100, "view")
    await svc.record(1, 100, "view")  # trùng trong cửa sổ -> bỏ qua
    assert len(repo.saved) == 1
    # Sản phẩm khác thì vẫn ghi
    await svc.record(1, 200, "view")
    assert len(repo.saved) == 2


@pytest.mark.asyncio
async def test_record_purchase_not_throttled():
    svc, repo, _ = _make()
    await svc.record(1, 100, "purchase")
    await svc.record(1, 100, "purchase")  # tín hiệu mạnh -> luôn ghi
    assert len(repo.saved) == 2


@pytest.mark.asyncio
async def test_record_fault_tolerant_on_save_error():
    svc, repo, _ = _make(save_raises=True)
    # Không được raise dù save lỗi
    await svc.record(1, 100, "purchase")
    assert repo.saved == []


@pytest.mark.asyncio
async def test_record_updates_affinity_with_action_score():
    """Ghi thành công -> cập nhật affinity theo category sản phẩm với đúng action.score."""
    svc, repo, affinity = _make()
    await svc.record(7, 100, "purchase")  # product category_id=5 (fake), purchase score=10
    assert len(repo.saved) == 1
    assert affinity.calls == [(7, 5, 10)]
