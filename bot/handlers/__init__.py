# bot/handlers/__init__.py
from aiogram import Dispatcher

from ..config import Settings
from .orders import register_order_handlers


def register_all_handlers(dp: Dispatcher, settings: Settings) -> None:
    register_order_handlers(dp, settings)
