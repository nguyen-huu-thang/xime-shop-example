from __future__ import annotations

from app.entity.action import Action
from xime.starters.sqlalchemy import CrudRepository


class ActionRepository(CrudRepository[Action]):
    model = Action
