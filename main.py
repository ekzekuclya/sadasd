import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
django.setup()
from aiogram import Bot, Dispatcher
import asyncio
import logging
from aiogram.types import Message
from aiogram import Router, Bot, F
from core.config import bot_oper, bot_main



# router_main = Router()
# router_oper = Router()
#
#
# @router_main.message()
# async def testing(msg: Message, bot: Bot):
#     print(f"Сообщение от пользователя {msg.from_user.id} в боте 1")
#     await msg.answer("Я БОТ 1, ла лаа ла")
#     await oper_sender(msg)
#
#
# @router_oper.message()
# async def testing2(msg: Message, bot: Bot):
#     print(f"Сообщение от пользователя {msg.from_user.id} в боте 2")
#     await msg.answer("Я БОТ 2")
#
#
# async def oper_sender(msg: Message):
#     await bot_oper.send_message(7229911453, f"Пользователь {msg.from_user.id} написал в бот1: {msg.text}")


async def main():
    from aiogram.enums.parse_mode import ParseMode
    from aiogram.fsm.storage.memory import MemoryStorage
    from tg.handlers.start import router_oper
    from tg.handlers.buisness_callbacks import router
    dp1 = Dispatcher(storage=MemoryStorage())
    dp2 = Dispatcher(storage=MemoryStorage())
    dp1.include_routers(router)
    dp2.include_routers(router_oper)
    await bot_main.delete_webhook(drop_pending_updates=True)
    await asyncio.gather(
        dp1.start_polling(bot_main, allowed_updates=dp1.resolve_used_update_types()),
        dp2.start_polling(bot_oper, allowed_updates=dp2.resolve_used_update_types())
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())