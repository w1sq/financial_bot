from db.db import DB
from typing import List
from dataclasses import dataclass

@dataclass
class User:
    ADMIN = "admin"
    USER = "user"
    BLOCKED = "blocked"

    user_id:int
    role:str

class UserStorage():
    __table = "users"
    def __init__(self, user_db:DB):
        self._db = user_db
    
    async def init(self):
        await self._db.execute(f'''
            CREATE TABLE IF NOT EXISTS {self.__table} (
                id BIGINT PRIMARY KEY,
                role TEXT
            )
        ''')

    async def get_by_id(self, user_id:int) -> User | None:
        data = await self._db.fetchrow(f"SELECT * FROM {self.__table} WHERE id = $1", user_id)
        if data is None:
            return None
        return User(data[0], data[1])

    async def promote_to_admin(self, user_id:int):
        await self._db.execute(f"UPDATE {self.__table} SET role = $1 WHERE id = $2", User.ADMIN, user_id)

    async def demote_from_admin(self, user_id:int):
        await self._db.execute(f"UPDATE {self.__table} SET role = $1 WHERE id = $2", User.USER, user_id)

    async def get_role_list(self, role:str) -> List[int] | None:
        roles = await self._db.fetch(f"SELECT * FROM {self.__table} WHERE role = $1", role)
        if roles is None:
            return None
        return [role[0] for role in roles]

    async def create(self, user:User):
        await self._db.execute(f'''
            INSERT INTO {self.__table} (id, role) VALUES ($1, $2)
        ''', user.id, user.role)

    async def get_all_members(self) -> List[User]| None:
        data = await self._db.fetch(f'''
            SELECT * FROM {self.__table}
        ''')
        if data is None:
            return None
        return [User(user_data[0], user_data[1]) for user_data in data]

    async def get_user_amount(self) -> int:
        return await self._db.fetchval(f"SELECT COUNT(*) FROM {self.__table}")

    async def ban_user(self, user_id:User):
        await self._db.execute(f"UPDATE {self.__table} SET role = $1 WHERE id = $2", User.BLOCKED, user_id)
    
    async def unban_user(self, user_id:User):
        await self._db.execute(f"UPDATE {self.__table} SET role = $1 WHERE id = $2", User.USER, user_id)

    async def delete(self, user_id:int):
        await self._db.execute(f'''
            DELETE FROM {self.__table} WHERE id = $1
        ''', user_id)
