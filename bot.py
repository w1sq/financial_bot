'''All tgbot logic is here'''

import typing
import os

import aiogram
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

from db.storage import UserStorage, User
from config import Config
from texts import Texts



class TG_Bot():
    def __init__(self, user_storage: UserStorage):
        self._user_storage:UserStorage = user_storage
        self._bot:aiogram.Bot = aiogram.Bot(token=Config.TGBOT_API_KEY)
        self._storage:MemoryStorage = MemoryStorage()
        self._dispatcher:aiogram.Dispatcher = aiogram.Dispatcher(self._bot, storage=self._storage)
        self._create_keyboards()

    async def init(self):
        '''Custom telegram bot initial function'''
        self._init_handler()

    async def start(self):
        '''Aiogram bot startup'''
        print('Bot has started')
        await self._dispatcher.start_polling()

    async def send_signal(self, message:str):
        for user in await self._user_storage.get_all_members():
            try:
                await self._bot.send_message(user.user_id, message)
            except Exception:
                pass

    async def _show_menu(self, message:aiogram.types.Message, user:User):
        await message.answer(Texts.welcome, reply_markup=self._menu_keyboard_user)

    async def _show_info(self, message:aiogram.types.Message, user:User):
        await message.answer(Texts.info, reply_markup=self._menu_keyboard_user, parse_mode='HTML')

    def _create_settings_keyboard(self, user:User):
        settings_keyboard = InlineKeyboardMarkup()
        if user.notifications:
            settings_keyboard.row(InlineKeyboardButton('✅ Рассылка', callback_data='notifications'))
            enabled_smile = '✅'
        else:
            settings_keyboard.row(InlineKeyboardButton('Рассылка', callback_data='notifications'))
            enabled_smile = '🔇'
        platforms = {'Tinkoff':'1', 'Binance':'2', 'БКС':'3'}
        for platform, code in platforms.items():
            if code in user.platforms:
                settings_keyboard.row(InlineKeyboardButton(f'{enabled_smile} {platform}', callback_data=f'platform {code}'))
            else:
                settings_keyboard.row(InlineKeyboardButton(platform, callback_data=f'platform {code}'))
        return settings_keyboard

    async def _show_settings(self, message:aiogram.types.Message, user:User):
        settings_keyboard = self._create_settings_keyboard(user)
        await message.answer(Texts.settings, reply_markup=settings_keyboard, parse_mode='HTML')

    async def _platform(self, call:aiogram.types.CallbackQuery):
        user = await self._user_storage.get_by_id(call.message.chat.id)
        code = call.data.split()[1]
        if code in user.platforms:
            user_platforms = user.platforms
            user.platforms = user_platforms.replace(code, '')
            await self._user_storage.update_platforms(user)
        else:
            user.platforms += code
            await self._user_storage.update_platforms(user)
        settings_keyboard = self._create_settings_keyboard(user)
        await call.message.edit_text(Texts.settings, reply_markup= settings_keyboard, parse_mode='HTML')

    async def _notifications(self, call:aiogram.types.CallbackQuery):
        user = await self._user_storage.get_by_id(call.message.chat.id)
        await self._user_storage.update_notifications(user)
        user.notifications = not user.notifications
        settings_keyboard = self._create_settings_keyboard(user)
        await call.message.edit_text(Texts.settings, reply_markup= settings_keyboard, parse_mode='HTML')

    async def _reboot(self, message:aiogram.types.Message, user:User):
        await message.answer('Server is rebooting')
        await message.delete()
        os.system('reboot')

    def _init_handler(self):
        self._dispatcher.register_message_handler(self._user_middleware(self._show_menu),
                                                    commands=['start', 'menu'])
        self._dispatcher.register_message_handler(self._user_middleware(self._show_info), text='ℹ️ О Боте')
        self._dispatcher.register_message_handler(self._user_middleware(self._show_settings), text='⚙️ Настройки уведомлений')
        self._dispatcher.register_message_handler(self._user_middleware(self._reboot),
                                                    commands=['reboot'])

        self._dispatcher.register_callback_query_handler(self._platform, aiogram.dispatcher.filters.Text(startswith="platform "))
        self._dispatcher.register_callback_query_handler(self._notifications, aiogram.dispatcher.filters.Text(startswith="notifications"))


    def _user_middleware(self, func:typing.Callable) -> typing.Callable:
        async def wrapper(message:aiogram.types.Message, *args, **kwargs):
            user = await self._user_storage.get_by_id(message.chat.id)
            if user is None:
                split_message = message.text.split()
                if len(split_message) == 2 and split_message[1] == Config.BOT_PASSWORD:
                    user = User(
                        user_id = message.chat.id,
                        role = User.USER
                    )
                    await self._user_storage.create(user)
                    await func(message, user)
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
            .row(KeyboardButton('ℹ️ О Боте')).row(KeyboardButton('⚙️ Настройки уведомлений'))

