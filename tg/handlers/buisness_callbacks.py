import asyncio
import os

from aiogram import Router, Bot, F
from aiogram.filters import Command, CommandObject, BaseFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, InlineKeyboardButton, ReplyKeyboardMarkup, ChatMemberOwner, ChatMemberAdministrator, \
    CallbackQuery, BusinessConnection, KeyboardButton
from django.db.models import Q
from django.utils import timezone
from .start import order_sender, order_canceled, order_paid
from .utils import convert_ltc_to_usdt, NewOrInactiveUserFilter, IsFloatFilter, check_invoice_paid, convert_usdt_to_ltc, coms
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from asgiref.sync import sync_to_async
from ..models import TelegramUser, CurrentCourse, Order
from ..text import order_text
from core.config import bot_oper, bot_main
router = Router()
import random


class Form(StatesGroup):
    waiting_for_ltc = State()
    waiting_for_usdt = State()


class Paid(StatesGroup):
    waiting_for_kvitto = State()


@router.business_message(Form.waiting_for_usdt)
async def waiting_usdt(msg: Message):
    try:
        user, created = await sync_to_async(TelegramUser.objects.get_or_create)(user_id=msg.from_user.id)

        if msg.text:
            try:
                usdt = int(msg.text)
            except Exception as e:
                await msg.answer("Неверный формат")
                return
            ltc_sum = await convert_usdt_to_ltc(usdt)
            ltc_sum = round(ltc_sum, 8)
            total_usdt = await convert_ltc_to_usdt(ltc_sum, count=0)
            await coms(msg, total_usdt, ltc_sum, user)
    except Exception as e:
        await msg.answer("Проверьте правильность набора")
        print(f"async def waiting_ltc, @router.business_message(Form.wфше)", e)


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
        print(f"async def waiting_ltc, @router.business_message(Form.waiting_for_ltc)", e)


@router.business_message(NewOrInactiveUserFilter())
async def start_menu(msg: Message, bot: Bot):
    img1 = "AgACAgIAAxkBAAEBd3RnH2eGnGpliRfuFEyCiM-x1xM7PQACl-QxGzEc-UhiitseAh9XKQEAAwIAA3gAAzYE"
    img2 = "AgACAgIAAxkBAAEBd3ZnH2ewiXQF_l0syudQksRizQz4uwACnOQxGzEc-UgSBHVda-wVngEAAwIAA3gAAzYE"
    images = [img1, img2]
    user, created = await sync_to_async(TelegramUser.objects.get_or_create)(user_id=msg.from_user.id)
    if user:
        user.username = msg.from_user.username if msg.from_user.username else None
        user.first_name = msg.from_user.first_name
        user.last_name = msg.from_user.last_name
        user.last_message_time = timezone.now()
        user.save()
    if user.is_admin:
        if msg.photo:
            await msg.answer("Ждем вас снова🙌")
            return
    text = ("Здравствуйте уважаемый клиент\n\n"
            "Вы обратились к команде по фондовой бирже\n   🔸 Dino Exchange 🔸\n\n\n"
            "Мы автоматизировали систему платежей, для обмена нажмите кнопку или сразу перешлите желаемое колличество LTC\n\n"
            "⬇️Выберите один из вариантов⬇️")

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text='Купить LTC', callback_data="buy_ltc"))
    builder.adjust(1)
    await msg.answer_photo(photo=random.choice(images), caption=text, reply_markup=builder.as_markup())


@router.callback_query()
async def handle_callback_query(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    if callback_query.data == "buy_ltc":
        text = "Сделайте выбор:"
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="Указать в LTC", callback_data="type_ltc"))
        builder.add(InlineKeyboardButton(text="Указать в USD", callback_data="type_usd"))
        builder.adjust(1)
        await callback_query.message.answer(text, reply_markup=builder.as_markup())
    elif callback_query.data == "type_ltc":
        await callback_query.message.answer("🔸Введите или перешлите желаемое количество LTC:")
        await state.set_state(Form.waiting_for_ltc)
    elif callback_query.data == "type_usd":
        await callback_query.message.answer("🔸Введите или перешлите желаемое количество USD, без знаков $ и точек/запятых:")
        await state.set_state(Form.waiting_for_usdt)
    elif callback_query.data.startswith("order_"):
        data = callback_query.data.split("_")
        order_id = data[1]
        order = await sync_to_async(Order.objects.filter)(id=order_id)
        order = order.first()
        if order.status == "wait_for_op":
            await callback_query.answer("Реквизиты генерируются, пожалуйста дождитесь!")
        elif order.status == "created":
            order.status = "wait_for_op"
            order.save()
            await order_sender(callback_query.message, order)
            await callback_query.message.answer("♻️ Генерируем реквизиты...")
            await asyncio.create_task(check_invoice_paid(callback_query.message, order))
    elif callback_query.data.startswith("client_canceled_"):
        data = callback_query.data.split("_")
        order_id = data[2]
        order = await sync_to_async(Order.objects.filter)(id=order_id)
        order = order.first()
        order.status = "canceled"
        order.save()
        await order_canceled(order)
    elif callback_query.data.startswith("client_payed_"):
        data = callback_query.data.split("_")
        order_id = data[2]
        order = await sync_to_async(Order.objects.filter)(id=order_id)
        order = order.first()
        if not order.status == "declined":
            order.status = "paid"
            order.save()
            await state.set_state(Paid.waiting_for_kvitto)
            await state.update_data(order_id=order_id)
            await callback_query.message.answer("Отправьте фото чека")


async def download_photo(bot: Bot, file_id: str, file_path: str):
    file = await bot.get_file(file_id)
    await bot.download_file(file.file_path, destination=file_path)


# @router.business_message(Paid.waiting_for_kvitto)
# async def waiting_for_kvitto(msg: Message, state: FSMContext):
#     data = await state.get_data()
#     order_id = data.get("order_id")
#     order = await sync_to_async(Order.objects.filter)(id=order_id)
#     order = order.first()
#     if msg.photo:
#         photo_id = msg.photo[-1].file_id
#         photo_path = f"temp_{photo_id}.jpg"
#         await download_photo(msg.bot, photo_id, photo_path)
#         await order_paid(order, photo_path)
#         os.remove(photo_path)
#         await msg.answer("Ожидайте подтверждения, можете отправить кошелек.")
#     if msg.document:
#         file_id = msg.document.file_id
#         file_path = f"temp_{file_id}.pdf"  # или другое расширение в зависимости от типа документа

async def download_document(bot: Bot, file_id: str, file_path: str):
    # Получаем информацию о файле
    file = await bot.get_file(file_id)

    # Скачиваем файл
    await bot.download_file(file.file_path, destination=file_path)


@router.business_message(Paid.waiting_for_kvitto)
async def waiting_for_kvitto(msg: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    order = await sync_to_async(Order.objects.filter)(id=order_id)
    order = order.first()

    if msg.photo:
        file_id = msg.photo[-1].file_id
        file_path = f"temp_{file_id}.jpg"
        file_type = 'photo'
    elif msg.document:
        print("IN DOCUMENT")
        file_id = msg.document.file_id
        file_path = f"temp_{file_id}.pdf"  # или другое расширение в зависимости от типа документа
        file_type = 'document'
    else:
        await msg.answer("Пожалуйста, отправьте фото или документ.")
        return

    await download_photo(msg.bot, file_id, file_path) if file_type == 'photo' else await download_document(msg.bot,
                                                                                                           file_id,
                                                                                                           file_path)
    await order_paid(order, file_path, file_type)
    os.remove(file_path)
    await msg.answer("Ожидайте подтверждения, можете отправить кошелек.")
    await state.clear()


@router.business_message(Form.waiting_for_ltc)
async def waiting_ltc(msg: Message, state: FSMContext):
    try:
        user, created = await sync_to_async(TelegramUser.objects.get_or_create)(user_id=msg.from_user.id)

        if msg.text:
            ltc_sum = msg.text.replace(",", ".")
            total_usdt = await convert_ltc_to_usdt(ltc_sum, count=0)
            await coms(msg, total_usdt, ltc_sum, user)
            await state.clear()
    except Exception as e:
        await msg.answer("Проверьте правильность набора")
        print(f"async def waiting_ltc, @router.business_message(Form.waiting_for_ltc)", e)








