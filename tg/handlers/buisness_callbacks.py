import asyncio
import os
from django.db.models import Count
from aiogram import Router, Bot, F
from aiogram.filters import Command, CommandObject, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, InlineKeyboardButton, ReplyKeyboardMarkup, ChatMemberOwner, ChatMemberAdministrator, \
    CallbackQuery, BusinessConnection, KeyboardButton, FSInputFile
from django.db.models import Q
from django.utils import timezone
from binance.async_client import AsyncClient

from .crypto_utils import crypto_sender, txid_checker
from .photo_utils import draw_image
from .start import order_sender, order_canceled, order_paid
from .utils import convert_ltc_to_usdt, NewOrInactiveUserFilter, IsFloatFilter, check_invoice_paid, convert_usdt_to_ltc, \
    coms, IsUSDT, comsusdt, IsLTCReq
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from asgiref.sync import sync_to_async
from ..models import TelegramUser, CurrentCourse, Order, Ticket, Withdraw, Client
from ..text import order_text, ticket_text
from core.config import bot_oper, bot_main
router = Router()
import random
from django.db import models


async def get_profile_link(user_id: int) -> str:
    return f"tg://user?id={user_id}"


@router.business_message(IsUSDT())
async def reposted_usd(msg: Message, bot: Bot):
    try:
        user, created = await sync_to_async(TelegramUser.objects.get_or_create)(user_id=msg.from_user.id)
        if user:
            user.username = msg.from_user.username if msg.from_user.username else None
            user.first_name = msg.from_user.first_name
            user.last_name = msg.from_user.last_name
            user.last_message_time = timezone.now()
            user.save()
        text = msg.text.strip()
        amount = int(text[:-1])
        await comsusdt(msg, amount, user)
    except Exception as e:
        print(f"reposted_usd", e)


@router.business_message(IsFloatFilter())
async def reposted_ltc(msg: Message, bot: Bot):
    try:
        user, created = await sync_to_async(TelegramUser.objects.get_or_create)(user_id=msg.from_user.id)
        if user:
            user.username = msg.from_user.username if msg.from_user.username else None
            user.first_name = msg.from_user.first_name
            user.last_name = msg.from_user.last_name
            user.last_message_time = timezone.now()
            user.save()
        ltc_sum = msg.text.replace(",", ".")
        total_usdt = await convert_ltc_to_usdt(ltc_sum, count=0)
        await coms(msg, total_usdt, ltc_sum, user)

    except Exception as e:
        print(f"reposted_ltc", e)
chat = "-1002279880306"


@router.business_message(IsLTCReq())
async def check_ltc(msg: Message):
    try:
        user, created = await sync_to_async(TelegramUser.objects.get_or_create)(user_id=msg.from_user.id)
        if user:
            user.username = msg.from_user.username if msg.from_user.username else None
            user.first_name = msg.from_user.first_name
            user.last_name = msg.from_user.last_name
            user.last_message_time = timezone.now()
            user.save()
        if user.is_admin:
            withdraw = await sync_to_async(Withdraw.objects.filter)(chat_id=msg.chat.id, active=True)
            withdraw = withdraw.first()
            withdraw.req = msg.text
            if withdraw.symbol == "USDT":
                ltc_amount = await convert_usdt_to_ltc(withdraw.amount)
                withdraw.amount = round(ltc_amount, 8)
            withdraw.save()
            builder = InlineKeyboardBuilder()
            order_text = (f"💵 _Сумма в LTC:_ `{withdraw.amount}`\n`{msg.text}`")
            builder.add(InlineKeyboardButton(text="💸 Отправить", callback_data=f"send_{withdraw.id}"))
            await msg.answer(order_text, parse_mode="Markdown",
                             reply_markup=builder.as_markup())
    except Exception as e:
        print(e)


@router.message(Command("start"))
async def startish(msg: Message, state: FSMContext, command: CommandObject, bot: Bot):
    user, created = await sync_to_async(TelegramUser.objects.get_or_create)(user_id=msg.from_user.id)
    if user:
        user.username = msg.from_user.username if msg.from_user.username else None
        user.first_name = msg.from_user.first_name
        user.last_name = msg.from_user.last_name
        user.last_message_time = timezone.now()
        user.save()

    if command:
        args = command.args
        tickets = await sync_to_async(Ticket.objects.filter)(ticket=args)
        ticket = tickets.first()
        if ticket:
            if not ticket.activated:
                ticket.user = user
                ticket.activated = True
                ticket.save()
                await msg.answer("Вы активировали 1 билет")
    tickets = await sync_to_async(Ticket.objects.filter)(user=user, activated=True)
    count = tickets.count()

    users_with_ticket_count = await sync_to_async(TelegramUser.objects.annotate)(
        active_ticket_count=Count('ticket', filter=Q(ticket__activated=True)))
    users_with_ticket_count = users_with_ticket_count.order_by('-active_ticket_count')
    user_active_ticket_count = user.ticket_set.filter(activated=True).count()
    position = users_with_ticket_count.filter(active_ticket_count__gte=user_active_ticket_count).count()

    print(f"Позиция пользователя {user.id} по количеству активированных тикетов: {position}")
    names = f"{user.first_name if user.first_name else ''} {user.last_name if user.last_name else ''}"
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="💌 Подпишись", url="https://t.me/Dino_LTC"))
    builder.add(InlineKeyboardButton(text="👨‍💻 Вакансии на работу", url="https://t.me/Zoltium"))
    builder.adjust(1)
    await msg.answer(ticket_text.format(username=names, sumtickets=count, rulya=position), parse_mode="Markdown", reply_markup=builder.as_markup())


async def delete_all_withdrawal_addresses(client):
    try:

        withdrawal_addresses = client.get_withdrawal_addresses()

        # Если адреса есть, выводим их
        if withdrawal_addresses:
            print(f"Найдено {len(withdrawal_addresses)} адресов для удаления.")

            # Проходим по всем адресам и удаляем каждый
            for address in withdrawal_addresses:
                address_id = address['address']  # Получаем идентификатор адреса
                try:
                    client.delete_withdrawal_address(address_id)
                    print(f"Адрес {address_id} удалён.")
                except Exception as e:
                    print(f"Ошибка при удалении адреса {address_id}: {e}")
            return "Все адреса успешно удалены!"
        else:
            return "Нет сохранённых адресов для удаления."
    except Exception as e:
        return f"Ошибка при получении адресов: {e}"


@router.message(Command("/deladdress"))
async def del_addresser(msg: Message):
    db_c = await sync_to_async(Client.objects.first)()
    client = await AsyncClient.create(db_c.key, db_c.secret)
    await del_addresser(client)
    await msg.answer("ГОТОВО")


@router.business_message(F.text == "Отправлено 👍")
async def ticket(msg: Message, bot: Bot):
    user, created = await sync_to_async(TelegramUser.objects.get_or_create)(user_id=msg.from_user.id)
    if user:
        user.username = msg.from_user.username if msg.from_user.username else None
        user.first_name = msg.from_user.first_name
        user.last_name = msg.from_user.last_name
        user.last_message_time = timezone.now()
        user.save()
    if user.is_admin:
        bot_user = await bot.get_me()
        user_bot = bot_user.username
        ticket = await sync_to_async(Ticket.objects.create)()
        url = f"http://t.me/{user_bot}?start={ticket.ticket}"
        text = f"[🎟 *Ваш билет* 🎟]({url})\n`Нажмите на билет, для активации`"
        await msg.answer(text, parse_mode="Markdown")



@router.message(Command("roulette"))
async def finish_roul(msg: Message, state: FSMContext, command: CommandObject, bot: Bot):
    user, created = await sync_to_async(TelegramUser.objects.get_or_create)(user_id=msg.from_user.id)
    if user:
        user.username = msg.from_user.username if msg.from_user.username else None
        user.first_name = msg.from_user.first_name
        user.last_name = msg.from_user.last_name
        user.last_message_time = timezone.now()
        user.save()
    if user.is_admin:
        args = command.args
        if args and args.isdigit():
            num_prizers = int(args)
        else:
            return
        top_prizers = await sync_to_async(lambda:
                                          TelegramUser.objects
                                          .annotate(ticket_count=Count('ticket', filter=models.Q(ticket__activated=True)))
                                          .order_by('-ticket_count')
                                          .filter(ticket_count__gt=0)[:num_prizers]
                                          )()

        if top_prizers:
            response = "[🎊](https://telegra.ph/file/09cbf544d43e49bba72d1.mp4) Победители розыгрыша::\n\n"
            count = 1
            for user in top_prizers:
                response += f"{count}. `{'@'+user.username if user.username else user.user_id}`: `{user.ticket_count}` билетов\n"
                count += 1
                tickets = await sync_to_async(Ticket.objects.filter)(user=user)
                await sync_to_async(tickets.delete)()
            await msg.answer(response, parse_mode="Markdown")
        else:
            await msg.answer("Нет призеров с активированными билетами.")


@router.message(Command("top"))
async def show_top(msg: Message, state: FSMContext, command: CommandObject, bot: Bot):
    args = command.args
    if args and args.isdigit():
        num_prizers = int(args)
    else:
        return
    top_prizers = await sync_to_async(lambda:
                                      TelegramUser.objects
                                      .annotate(ticket_count=Count('ticket', filter=models.Q(ticket__activated=True)))
                                      .order_by('-ticket_count')
                                      .filter(ticket_count__gt=0)[:num_prizers]
                                      )()

    if top_prizers:
        response = "[🎊](https://telegra.ph/file/09cbf544d43e49bba72d1.mp4) Победители розыгрыша::\n\n"
        count = 1
        for user in top_prizers:
            response += f"{count}. tg://user?id={user.user_id}: `{user.ticket_count}` билетов\n"
            count += 1
            tickets = await sync_to_async(Ticket.objects.filter)(user=user)
        await msg.answer(response, parse_mode="Markdown")


@router.message(Command("sfdgdfhfgh"))
async def delete_all_tickets(msg: Message):
    all_tickets = await sync_to_async(Ticket.objects.all)()
    activated = 0
    not_activated = 0
    for i in all_tickets:
        if i.activated:
            activated += 1
        elif not i.activated:
            not_activated += 1
        i.delete()
    await msg.answer(f"RESULT:\nactivated tickets: {activated}\nnot activated tickets:{not_activated}")

from aiogram import Bot, Dispatcher, types
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile

import asyncio
import os
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Другие необходимые импорты и настройки вашего бота

@router.callback_query()
async def handle_callback_query(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    if callback_query.data.startswith("send"):
        user, created = await sync_to_async(TelegramUser.objects.get_or_create)(user_id=callback_query.from_user.id)
        if user.is_admin:
            data = callback_query.data.split("_")
            withdraw_id = data[1]
            withdraw = await sync_to_async(Withdraw.objects.get)(id=withdraw_id)
            if not withdraw.completed:
                withdraw.completed = True
                withdraw.save()
                data = await crypto_sender(withdraw_id, callback_query.message)
                print("POLUCHENNAYA DATA", data)
                if data:
                    temp_file_path = await draw_image(data)

                    with open(temp_file_path, 'rb') as img_file:
                        await callback_query.message.answer_photo(photo=FSInputFile(temp_file_path))

                    os.remove(temp_file_path)  # Удаляем временный файл после отправки
                await callback_query.answer("ЗАВЕРШЕНО")


            elif withdraw.completed:
                await callback_query.answer("ОРДЕР УЖЕ ВЫПОЛНЕН")
#         text = "Сделайте выбор:"
#         builder = InlineKeyboardBuilder()
#         builder.add(InlineKeyboardButton(text="Указать в LTC", callback_data="type_ltc"))
#         builder.add(InlineKeyboardButton(text="Указать в USD", callback_data="type_usd"))
#         builder.adjust(1)
#         await callback_query.message.answer(text, reply_markup=builder.as_markup())
#     elif callback_query.data == "type_ltc":
#         await callback_query.message.answer("🔸Введите или перешлите желаемое количество LTC:")
#         await state.set_state(Form.waiting_for_ltc)
#     elif callback_query.data == "type_usd":
#         await callback_query.message.answer("🔸Введите или перешлите желаемое количество USD, без знаков $ и точек/запятых:")
#         await state.set_state(Form.waiting_for_usdt)
#     elif callback_query.data.startswith("order_"):
#         data = callback_query.data.split("_")
#         order_id = data[1]
#         order = await sync_to_async(Order.objects.filter)(id=order_id)
#         order = order.first()
#         if order.status == "wait_for_op":
#             await callback_query.answer("Реквизиты генерируются, пожалуйста дождитесь!")
#         elif order.status == "created":
#             order.status = "wait_for_op"
#             order.save()
#             await order_sender(callback_query.message, order)
#             await callback_query.message.answer("♻️ Генерируем реквизиты...")
#             await asyncio.create_task(check_invoice_paid(callback_query.message, order))
#     elif callback_query.data.startswith("client_canceled_"):
#         data = callback_query.data.split("_")
#         order_id = data[2]
#         order = await sync_to_async(Order.objects.filter)(id=order_id)
#         order = order.first()
#         order.status = "canceled"
#         order.save()
#         await callback_query.message.edit_reply_markup(reply_markup=None)
#         await order_canceled(order)
#     elif callback_query.data.startswith("client_payed_"):
#         data = callback_query.data.split("_")
#         order_id = data[2]
#         order = await sync_to_async(Order.objects.filter)(id=order_id)
#         order = order.first()
#         if order.status == "wait_for_pay":
#             order.status = "paid"
#             order.save()
#             await state.set_state(Paid.waiting_for_kvitto)
#             await state.update_data(order_id=order_id)
#             await callback_query.message.answer("Отправьте фото чека")
#         else:
#             await callback_query.message.edit_reply_markup(reply_markup=None)
#             await callback_query.message.answer("Платеж на другой стадии")
#
#
# async def download_photo(bot: Bot, file_id: str, file_path: str):
#     file = await bot.get_file(file_id)
#     await bot.download_file(file.file_path, destination=file_path)
#
#
# # @router.business_message(Paid.waiting_for_kvitto)
# # async def waiting_for_kvitto(msg: Message, state: FSMContext):
# #     data = await state.get_data()
# #     order_id = data.get("order_id")
# #     order = await sync_to_async(Order.objects.filter)(id=order_id)
# #     order = order.first()
# #     if msg.photo:
# #         photo_id = msg.photo[-1].file_id
# #         photo_path = f"temp_{photo_id}.jpg"
# #         await download_photo(msg.bot, photo_id, photo_path)
# #         await order_paid(order, photo_path)
# #         os.remove(photo_path)
# #         await msg.answer("Ожидайте подтверждения, можете отправить кошелек.")
# #     if msg.document:
# #         file_id = msg.document.file_id
# #         file_path = f"temp_{file_id}.pdf"  # или другое расширение в зависимости от типа документа
#
# async def download_document(bot: Bot, file_id: str, file_path: str):
#     # Получаем информацию о файле
#     file = await bot.get_file(file_id)
#
#     # Скачиваем файл
#     await bot.download_file(file.file_path, destination=file_path)
#
#
# @router.business_message(Paid.waiting_for_kvitto)
# async def waiting_for_kvitto(msg: Message, state: FSMContext):
#     data = await state.get_data()
#     order_id = data.get("order_id")
#     order = await sync_to_async(Order.objects.filter)(id=order_id)
#     order = order.first()
#
#     if msg.photo:
#         file_id = msg.photo[-1].file_id
#         file_path = f"temp_{file_id}.jpg"
#         file_type = 'photo'
#     elif msg.document:
#         print("IN DOCUMENT")
#         file_id = msg.document.file_id
#         file_path = f"temp_{file_id}.pdf"  # или другое расширение в зависимости от типа документа
#         file_type = 'document'
#     else:
#         await msg.answer("Пожалуйста, отправьте фото или документ.")
#         return
#
#     await download_photo(msg.bot, file_id, file_path) if file_type == 'photo' else await download_document(msg.bot,
#                                                                                                            file_id,
#                                                                                                            file_path)
#     await order_paid(order, file_path, file_type)
#     os.remove(file_path)
#     await msg.answer("Ожидайте подтверждения, можете отправить кошелек.")
#     await state.clear()
#
#
# @router.business_message(Form.waiting_for_ltc)
# async def waiting_ltc(msg: Message, state: FSMContext):
#     try:
#         user, created = await sync_to_async(TelegramUser.objects.get_or_create)(user_id=msg.from_user.id)
#
#         if msg.text:
#             ltc_sum = msg.text.replace(",", ".")
#             total_usdt = await convert_ltc_to_usdt(ltc_sum, count=0)
#             await coms(msg, total_usdt, ltc_sum, user)
#             await state.clear()
#     except Exception as e:
#         await msg.answer("Проверьте правильность набора")
#         print(f"async def waiting_ltc, @router.business_message(Form.waiting_for_ltc)", e)








