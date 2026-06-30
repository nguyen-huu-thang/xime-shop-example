from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.entity.action import Action
from app.entity.interaction import Interaction
from xime.starters.sqlalchemy import CrudRepository


class InteractionRepository(CrudRepository[Interaction]):
    model = Interaction

    async def exists_recent(
        self, user_id: int, product_id: int, action_id: int, since: datetime
    ) -> bool:
        # Throttle: đã có interaction cùng (user, product, action) từ mốc `since` tới nay chưa?
        # Throttle: is there an interaction with the same (user, product, action) since `since`?
        result = await self.session.execute(
            select(Interaction.id)
            .where(Interaction.user_id == user_id)
            .where(Interaction.product_id == product_id)
            .where(Interaction.action_id == action_id)
            .where(Interaction.created_at >= since)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def find_recent_by_user_and_action(
        self, user_id: int, action_id: int, limit: int
    ) -> list[Interaction]:
        # Interaction mới nhất của user theo một loại hành động (vd view -> đã xem gần đây).
        # Most recent interactions of a user for a given action type (e.g. view -> recently viewed).
        result = await self.session.execute(
            select(Interaction)
            .where(Interaction.user_id == user_id)
            .where(Interaction.action_id == action_id)
            .order_by(Interaction.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def trending_product_ids(
        self, since: datetime, limit: int
    ) -> list[int]:
        # Thịnh hành: tổng trọng số điểm (action.score) theo product trong cửa sổ thời gian.
        # Trending: sum of action weights per product within a time window.
        result = await self.session.execute(
            select(Interaction.product_id)
            .join(Action, Action.id == Interaction.action_id)
            .where(Interaction.created_at >= since)
            .group_by(Interaction.product_id)
            .order_by(func.sum(Action.score).desc())
            .limit(limit)
        )
        return [row[0] for row in result.all()]

    async def product_ids_by_user_and_action(
        self, user_id: int, action_id: int
    ) -> set[int]:
        # Tập product_id mà user đã thực hiện một hành động (vd purchase -> đã mua).
        # Distinct product ids a user performed an action on (e.g. purchase -> already bought).
        result = await self.session.execute(
            select(Interaction.product_id)
            .where(Interaction.user_id == user_id)
            .where(Interaction.action_id == action_id)
            .distinct()
        )
        return {row[0] for row in result.all()}
