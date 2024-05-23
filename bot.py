"""All tgbot logic is here"""

import typing
import os

import aiogram
from aiogram.fsm.context import FSMContext
from aiogram.filters.command import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

from db.storage import UserStorage, User
from config import Config
from texts import Texts


class GetMinVolume(StatesGroup):
    volume = State()


class TG_Bot:
    def __init__(self, user_storage: UserStorage):
        self._user_storage: UserStorage = user_storage
        self._bot: aiogram.Bot = aiogram.Bot(
            token=Config.TGBOT_API_KEY, parse_mode="HTML"
        )
        self._storage: MemoryStorage = MemoryStorage()
        self._dispatcher: aiogram.Dispatcher = aiogram.Dispatcher(storage=self._storage)
        self._create_keyboards()

    async def init(self):
        """Custom telegram bot initial function"""
        self._init_handler()

    async def start(self):
        """Aiogram bot startup"""
        print("Bot has started")
        await self._dispatcher.start_polling(self._bot)

    async def send_signal(self, message: str, strategy: str, volume: int):
        for user in await self._user_storage.get_all_recipients(strategy, volume):
            try:
                await self._bot.send_message(user.user_id, message)
            except Exception:
                pass

    async def _show_menu(self, message: Message, user: User):
        await message.answer(Texts.welcome, reply_markup=self._menu_keyboard_user)

    async def _show_info(self, message: Message, user: User):
        await message.answer(Texts.info, reply_markup=self._menu_keyboard_user)

    def _create_settings_keyboard(self, user: User) -> InlineKeyboardMarkup:
        if user.notifications:
            settings_buttons = [
                [
                    InlineKeyboardButton(
                        text="✅ Рассылка", callback_data="notifications"
                    )
                ]
            ]
            enabled_smile = "✅"
        else:
            settings_buttons = [
                [InlineKeyboardButton(text="Рассылка", callback_data="notifications")]
            ]
            enabled_smile = "🔇"
        platforms = {"Никита": "1", "Андрей": "2", "Георгий": "3"}
        settings_buttons.append(
            [
                (
                    InlineKeyboardButton(
                        text=f"{enabled_smile} {platform}",
                        callback_data=f"strategy {code}",
                    )
                    if code in user.strategies
                    else InlineKeyboardButton(
                        text=platform, callback_data=f"strategy {code}"
                    )
                )
                for platform, code in platforms.items()
            ]
        )
        settings_buttons.append(
            [
                InlineKeyboardButton(
                    text=f"""Min. vol: {str(user.min_volume//1000) + " тыс. руб" if user.min_volume < 10**6 else str(round(user.min_volume/10**6, 2)) + "млн. руб"}""",
                    callback_data="change_min_volume",
                )
            ]
        )
        settings_keyboard = InlineKeyboardMarkup(
            inline_keyboard=settings_buttons, resize_keyboard=True
        )
        return settings_keyboard

    async def _show_settings(self, message: Message, user: User):
        settings_keyboard = self._create_settings_keyboard(user)
        await message.answer(Texts.settings, reply_markup=settings_keyboard)

    async def _strategy(self, call: CallbackQuery):
        if call.message is None or call.data is None:
            return
        user = await self._user_storage.get_by_id(call.message.chat.id)
        if user:
            code = call.data.split()[1]
            if code in user.strategies:
                user.strategies = user.strategies.replace(code, "")
            else:
                user.strategies += code
            await self._user_storage.update_strategies(user)
            settings_keyboard = self._create_settings_keyboard(user)
            await call.message.edit_text(
                text=Texts.settings, reply_markup=settings_keyboard
            )

    async def _notifications(self, call: CallbackQuery):
        if call.message is None:
            return
        user = await self._user_storage.get_by_id(user_id=call.message.chat.id)
        if user:
            await self._user_storage.update_notifications(user=user)
            user.notifications = not user.notifications
            settings_keyboard = self._create_settings_keyboard(user)
            await call.message.edit_text(
                text=Texts.settings, reply_markup=settings_keyboard
            )

    async def _change_min_volume(self, call: CallbackQuery, state: FSMContext):
        if call.message is None:
            return
        await self._bot.send_message(
            call.message.chat.id,
            "Пришлите минимальный объем свечи в рублях для уведомления:",
        )
        await state.set_state(GetMinVolume.volume)

    async def _set_min_volume(self, message: Message, state: FSMContext):
        if message.text is None:
            return
        min_volume = message.text.strip()
        if min_volume.isdigit():
            user = await self._user_storage.get_by_id(message.chat.id)
            if user is not None:  # Check if user is not None
                user.min_volume = int(min_volume)
                await self._user_storage.update_min_volume(user, int(min_volume))
                settings_keyb = self._create_settings_keyboard(user)
                await message.answer(
                    "Минимальный объем успешно обновлен:", reply_markup=settings_keyb
                )
                await state.clear()
        else:
            await message.answer("Пришлите только число")

    async def _cancel_handler(
        self, call: aiogram.types.CallbackQuery, state: FSMContext
    ):
        current_state = await state.get_state()
        if current_state is not None:
            await state.clear()
        if call.message is not None:
            await self._bot.edit_message_reply_markup(
                call.message.chat.id, call.message.message_id
            )
            await self._show_menu(
                call.message, await self._user_storage.get_by_id(call.message.chat.id)
            )

    async def _reboot(self, message: Message, user: User):
        await message.answer("Server is rebooting")
        await message.delete()
        os.system("reboot")

    def _init_handler(self):
        self._dispatcher.message.register(
            self._user_middleware(self._show_menu), Command(commands=["start", "menu"])
        )
        self._dispatcher.message.register(
            self._user_middleware(self._show_info),
            aiogram.F.text == "ℹ️ О Боте",
        )
        self._dispatcher.message.register(
            self._user_middleware(self._show_settings),
            aiogram.F.text == "⚙️ Настройки уведомлений",
        )
        self._dispatcher.message.register(
            self._user_middleware(self._reboot), Command("start")
        )

        self._dispatcher.callback_query.register(
            self._strategy, aiogram.F.data.startswith("strategy ")
        )
        self._dispatcher.callback_query.register(
            self._notifications, aiogram.F.data.startswith("notifications")
        )
        self._dispatcher.callback_query.register(
            self._change_min_volume, aiogram.F.data.startswith("change_min_volume")
        )
        self._dispatcher.message.register(self._set_min_volume, GetMinVolume.volume)

        self._dispatcher.callback_query.register(
            self._cancel_handler,
            aiogram.F.data.startswith("cancel"),
            # state="*",
        )

    def _user_middleware(self, func: typing.Callable) -> typing.Callable:
        async def wrapper(message: Message, *args, **kwargs):
            user = await self._user_storage.get_by_id(message.chat.id)
            if user is None:
                split_message = message.text.split() if message.text else []
                if len(split_message) == 2 and split_message[1] == Config.BOT_PASSWORD:
                    user = User(user_id=message.chat.id, role=User.USER)
                    await self._user_storage.create(user)
                    await func(message, user)
            elif user.role == User.BLOCKED:
                pass
            else:
                await func(message, user)

        return wrapper

    def _admin_required(self, func: typing.Callable) -> typing.Callable:
        async def wrapper(message: Message, user: User, *args, **kwargs):
            if user.role == User.ADMIN:
                await func(message, user)

        return wrapper

    def _create_keyboards(self):
        self._menu_keyboard_user = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="ℹ️ О Боте")],
                [KeyboardButton(text="⚙️ Настройки уведомлений")],
            ],
            resize_keyboard=True,
        )
