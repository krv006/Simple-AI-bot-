# bot/handlers/__init__.py
from aiogram import Dispatcher

from .orders import register_order_handlers
from ..config import Settings


def register_all_handlers(dp: Dispatcher, settings: Settings) -> None:
    register_order_handlers(dp, settings)
