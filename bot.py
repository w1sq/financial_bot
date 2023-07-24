'''All tgbot logic is here'''

import typing

import aiogram
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

from db.storage import UserStorage, User
from config import Config



class TG_Bot():
    def __init__(self, user_storage: UserStorage):
        self._user_storage:UserStorage = user_storage
        self._bot:aiogram.Bot = aiogram.Bot(token=Config.TGBOT_API_KEY)
        self._storage:MemoryStorage = MemoryStorage()
        self._dispatcher:aiogram.Dispatcher = aiogram.Dispatcher(self._bot, storage=self._storage)
        self._create_keyboards()

    async def init(self):
        self._init_handler()

    async def start(self):
        print('Bot has started')
        await self._dispatcher.start_polling()

    async def _show_menu(self, message:aiogram.types.Message, user:User):
        await message.answer('Добро пожаловать', reply_markup=self._menu_keyboard_user)

    def _init_handler(self):
        self._dispatcher.register_message_handler(self._user_middleware(self._show_menu),
                                                    commands=['start', 'menu'])

    def _user_middleware(self, func:typing.Callable) -> typing.Callable:
        async def wrapper(message:aiogram.types.Message, *args, **kwargs):
            user = await self._user_storage.get_by_id(message.chat.id)
            if user is None:
                user = User(
                    user_id = message.chat.id,
                    role = User.USER
                )
                await self._user_storage.create(user)
            elif user.role == User.BLOCKED:
                pass
            else:
                await func(message, user)
        return wrapper

    def _admin_required(self, func:typing.Callable) -> typing.Callable:
        async def wrapper(message:aiogram.types.Message, user:User, *args, **kwargs):
            if user.role == User.ADMIN:
                await func(message, user)
        return wrapper

    def _create_keyboards(self):
        self._menu_keyboard_user = ReplyKeyboardMarkup(resize_keyboard=True)\
            .row(KeyboardButton('Меню'))
