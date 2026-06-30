"""
Test đơn vị cho AffinityService (decay-on-write + đọc top có decay), không chạm DB.

  - _decay_factor: elapsed 0 -> 1.0; đúng 1 half-life -> 0.5; âm (lệch giờ) -> 1.0.
  - apply: lần đầu tạo row = add_score; lần sau decay điểm cũ rồi cộng (sau 1 half-life: cũ giảm nửa).
  - get_top_category_ids: xếp theo điểm ĐÃ decay tới read-time (điểm cao nhưng cũ có thể thua điểm thấp mới).

Chạy: pytest test/test_affinity.py -v
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.entity.user_category_affinity import UserCategoryAffinity
from app.service.affinity_service import HALF_LIFE_SECONDS, AffinityService

_UTC = timezone.utc


class _FakeAffRepo:
    def __init__(self):
        self.rows: dict[tuple[int, int], UserCategoryAffinity] = {}

    async def get_one(self, user_id, category_id):
        return self.rows.get((user_id, category_id))

    async def save(self, row):
        self.rows[(row.user_id, row.category_id)] = row
        return row

    async def find_by_user(self, user_id):
        return [r for (u, _c), r in self.rows.items() if u == user_id]


class _FakeTxn:
    def __call__(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _make():
    repo = _FakeAffRepo()
    return AffinityService(_FakeTxn(), repo), repo


# ─── _decay_factor ────────────────────────────────────────────────────────────

def test_decay_factor():
    assert AffinityService._decay_factor(0) == 1.0
    assert abs(AffinityService._decay_factor(HALF_LIFE_SECONDS) - 0.5) < 1e-9
    assert abs(AffinityService._decay_factor(2 * HALF_LIFE_SECONDS) - 0.25) < 1e-9
    # elapsed âm (lệch đồng hồ) -> không khuếch đại
    assert AffinityService._decay_factor(-100) == 1.0


# ─── apply (decay-on-write) ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_apply_creates_then_decays_and_adds():
    svc, repo = _make()
    t0 = datetime(2026, 1, 1, tzinfo=_UTC)

    await svc.apply(1, 5, 10, now=t0)
    assert repo.rows[(1, 5)].score == 10.0
    assert repo.rows[(1, 5)].updated_at == t0

    # Sau đúng 1 half-life: 10 * 0.5 + 10 = 15
    t1 = t0 + timedelta(seconds=HALF_LIFE_SECONDS)
    await svc.apply(1, 5, 10, now=t1)
    assert abs(repo.rows[(1, 5)].score - 15.0) < 1e-9
    assert repo.rows[(1, 5)].updated_at == t1


# ─── get_top_category_ids (đọc có decay) ─────────────────────────────────────

@pytest.mark.asyncio
async def test_get_top_orders_by_decayed_score():
    svc, repo = _make()
    t_read = datetime(2026, 2, 1, tzinfo=_UTC)

    # Category 5: điểm cao (100) nhưng cũ 4 half-life -> 100/16 = 6.25
    repo.rows[(1, 5)] = UserCategoryAffinity(
        user_id=1, category_id=5, score=100.0,
        updated_at=t_read - timedelta(seconds=4 * HALF_LIFE_SECONDS),
    )
    # Category 6: điểm thấp (10) nhưng mới -> 10
    repo.rows[(1, 6)] = UserCategoryAffinity(
        user_id=1, category_id=6, score=10.0, updated_at=t_read
    )

    ids = await svc.get_top_category_ids(1, now=t_read)
    assert ids == [6, 5]  # 10 (mới) > 6.25 (cũ)

    # limit
    assert await svc.get_top_category_ids(1, now=t_read, limit=1) == [6]
