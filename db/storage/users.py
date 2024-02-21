from db.db import DB
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class User:
    ADMIN = "admin"
    USER = "user"
    BLOCKED = "blocked"

    user_id: int
    role: str
    notifications: bool = True
    strategies: str = "123"
    min_volume: int = 0


class UserStorage:
    __table = "users"

    def __init__(self, user_db: DB):
        self._db = user_db

    async def init(self):
        await self._db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.__table} (
                id BIGINT PRIMARY KEY,
                role TEXT,
                notifications BOOLEAN DEFAULT TRUE,
                strategies TEXT DEFAULT '123',
                min_volume INT DEFAULT 0
            )
        """
        )

    async def get_by_id(self, user_id: int) -> Optional[User]:
        data = await self._db.fetchrow(
            f"SELECT * FROM {self.__table} WHERE id = $1", user_id
        )
        if data is None:
            return None
        return User(data[0], data[1], data[2], data[3], data[4])

    async def promote_to_admin(self, user_id: int):
        await self._db.execute(
            f"UPDATE {self.__table} SET role = $1 WHERE id = $2", User.ADMIN, user_id
        )

    async def demote_from_admin(self, user_id: int):
        await self._db.execute(
            f"UPDATE {self.__table} SET role = $1 WHERE id = $2", User.USER, user_id
        )

    async def update_strategies(self, user: User):
        await self._db.execute(
            f"UPDATE {self.__table} SET strategies = $1 WHERE id = $2",
            user.strategies,
            user.user_id,
        )

    async def update_notifications(self, user: User):
        await self._db.execute(
            f"UPDATE {self.__table} SET notifications = NOT notifications WHERE id=$1",
            user.user_id,
        )

    async def update_min_volume(self, user: User, new_min_volume: int):
        await self._db.execute(
            f"UPDATE {self.__table} SET min_volume = $1 WHERE id = $2",
            new_min_volume,
            user.user_id,
        )

    async def get_role_list(self, role: str) -> List[int] | None:
        roles = await self._db.fetch(
            f"SELECT * FROM {self.__table} WHERE role = $1", role
        )
        if roles is None:
            return None
        return [role[0] for role in roles]

    async def create(self, user: User):
        await self._db.execute(
            f"""
            INSERT INTO {self.__table} (id, role) VALUES ($1, $2)
        """,
            user.user_id,
            user.role,
        )

    async def get_all_recipients(self, strategy: str, volume: int) -> List[User]:
        strategies = {"nikita": 1, "andrey": 2, "george": 3}
        data = await self._db.fetch(
            f"""
            SELECT * FROM {self.__table} WHERE strategies LIKE '%{strategies[strategy]}%' AND notifications = TRUE AND min_volume <= $1 OR min_volume = 0
        """,
            volume,
        )
        if data is None:
            return None
        return [
            User(
                user_data[0],
                user_data[1],
                user_data[2],
                user_data[3],
                user_data[4],
            )
            for user_data in data
        ]

    async def get_all_members(self) -> List[User] | None:
        data = await self._db.fetch(
            f"""
            SELECT * FROM {self.__table}
        """
        )
        if data is None:
            return None
        return [
            User(
                user_data[0],
                user_data[1],
                user_data[2],
                user_data[3],
                user_data[4],
            )
            for user_data in data
        ]

    async def get_user_amount(self) -> int:
        return await self._db.fetchval(f"SELECT COUNT(*) FROM {self.__table}")

    async def ban_user(self, user_id: User):
        await self._db.execute(
            f"UPDATE {self.__table} SET role = $1 WHERE id = $2", User.BLOCKED, user_id
        )

    async def unban_user(self, user_id: User):
        await self._db.execute(
            f"UPDATE {self.__table} SET role = $1 WHERE id = $2", User.USER, user_id
        )

    async def delete(self, user_id: int):
        await self._db.execute(
            f"""
            DELETE FROM {self.__table} WHERE id = $1
        """,
            user_id,
        )
