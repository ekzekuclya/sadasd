import types

from aiogram import Router, Bot, F
from aiogram.filters import Command, CommandObject, BaseFilter
from aiogram.types import Message, InlineKeyboardButton, ReplyKeyboardMarkup, ChatMemberOwner, ChatMemberAdministrator, \
    CallbackQuery, FSInputFile
from django.db.models import Q
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from asgiref.sync import sync_to_async
from aiogram.fsm.context import FSMContext
from .utils import convert_kgs_to_ltc, name, convert_ltc_to_usdt
from ..text import order_text_for_op
from ..models import TelegramUser, Order, Requisites, MainLtcReq
from core.config import bot_oper, bot_main
from aiogram.enums.parse_mode import ParseMode
router_oper = Router()


class Req(StatesGroup):
    awaiting_req = State()


class ConfirmOrder(StatesGroup):
    awaiting_check = State()


@router_oper.callback_query()
async def take_order_op(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if callback.data.startswith("take_order_"):
        user, created = await sync_to_async(TelegramUser.objects.get_or_create)(user_id=callback.from_user.id)
        data = callback.data.split("_")
        order_id = data[2]
        order = await sync_to_async(Order.objects.filter)(id=order_id)
        order = order.first()
        if user.is_operator:
            if order.operator:
                if order.operator != user:
                    await callback.message.edit_reply_markup(reply_markup=None)
                    await callback.answer("Заявку уже забрали :(")
                    await state.clear()
                elif order.operator == user:
                    await callback.answer("Заявку уже ваша")
                    await callback.message.edit_reply_markup(reply_markup=None)
                    await state.clear()
            elif not order.operator:
                order.operator = user
                order.status = "wait_for_req"
                order.save()
                await callback.message.answer("Отправьте реквизиты")
                await state.set_state(Req.awaiting_req)
                await state.update_data(order_id=order_id)
    if callback.data.startswith("confirm_order_"):
        data = callback.data.split("_")
        order_id = data[2]
        order = await sync_to_async(Order.objects.filter)(id=order_id)
        order = order.first()
        order.status = "confirmed"
        order.save()
        await state.set_state(ConfirmOrder.awaiting_check)
        await state.update_data(order_id=order.id)
        await callback.message.answer("Отправьте чек")
    if callback.data.startswith("decline_order_"):
        data = callback.data.split("_")
        order_id = data[2]
        order = await sync_to_async(Order.objects.filter)(id=order_id)
        order = order.first()
        order.status = "declined"
        order.save()


@router_oper.message(ConfirmOrder.awaiting_check)
async def confirm_order(msg: Message, state: FSMContext):
    bot = bot_oper
    if msg.photo:
        if msg.photo:
            photo_id = msg.photo[-1].file_id
            data = await state.get_data()
            order_id = data.get("order_id")
            order = await sync_to_async(Order.objects.get)(id=order_id)
            user, created = await sync_to_async(TelegramUser.objects.get_or_create)(user_id=msg.from_user.id)

            text = ""
            text += order_text_for_op.format(ltc_sum=order.ltc_sum, kgs_sum=order.kgs_sum)
            admins = await sync_to_async(TelegramUser.objects.filter)(is_admin=True)
            if admins:
                for i in admins:
                    await bot.send_photo(i.user_id, photo=photo_id, caption=f"Оператор отправил средства \n{name(order.client)}\n{text}", parse_mode="Markdown")
            await msg.answer(f"Так держать ордер исполнен!\n\n{text}", parse_mode=ParseMode.MARKDOWN)


@router_oper.message(Req.awaiting_req)
async def awaiting_req(msg: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    order = await sync_to_async(Order.objects.filter)(id=order_id)
    order = order.first()
    order.req = msg.text
    order.save()
    await msg.answer(f"Реквизиты отправлены контр-агенту, ожидайте поступления! \n\n{msg.text}")
    await state.clear()


async def order_sender(msg: Message, order):
    bot = bot_oper
    operators = await sync_to_async(TelegramUser.objects.filter)(is_operator=True)
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Забрать ордер", callback_data=f"take_order_{order.id}"))
    if operators:
        for i in operators:
            order_com = i.operator_percent
            kgs_sum_for_op = order.coms * order_com
            total_usdt = await convert_ltc_to_usdt(order.ltc_sum)
            kgs_sum_for_op += total_usdt
            ltc_amount = await convert_kgs_to_ltc(msg, kgs_sum_for_op)
            order.sum_for_op = float(ltc_amount) + float(order.ltc_sum)
            sum_for_op_text = f"{float(ltc_amount) + float(order.ltc_sum)}"
            if len(sum_for_op_text) >= 7:
                order.sum_for_op = f"{float(ltc_amount) + float(order.ltc_sum):.8f}"
            order.save()
            text = order_text_for_op.format(ltc_sum=order.sum_for_op, kgs_sum=order.kgs_sum)
            await bot.send_message(i.user_id, text, reply_markup=builder.as_markup(), parse_mode="Markdown")


# async def order_paid(order, photo):
#     bot = bot_oper
#     builder = InlineKeyboardBuilder()
#     builder.add(InlineKeyboardButton(text="Платеж поступил", callback_data=f"confirm_order_{order.id}"))
#     builder.add(InlineKeyboardButton(text="Липовый чек", callback_data=f"decline_order_{order.id}"))
#     if order.operator:
#         photo = FSInputFile(photo)
#         text = order_text_for_op.format(kgs_sum=order.kgs_sum, ltc_sum=order.sum_for_op)
#         main_req = await sync_to_async(MainLtcReq.objects.first)()
#         text += f"\n\n`{main_req.req}`"
#         await bot.send_photo(order.operator.user_id, photo=photo, caption=text,reply_markup=builder.as_markup(), parse_mode="Markdown")


async def order_paid(order, file_path, file_type):
    bot = bot_oper
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="Платеж поступил", callback_data=f"confirm_order_{order.id}"))
    builder.add(InlineKeyboardButton(text="Липовый чек", callback_data=f"decline_order_{order.id}"))
    if order.operator:
        file = FSInputFile(file_path)
        text = order_text_for_op.format(kgs_sum=order.kgs_sum, ltc_sum=order.sum_for_op)
        main_req = await sync_to_async(MainLtcReq.objects.first)()
        text += f"\n\n`{main_req.req}`"

        if file_type == 'photo':
            await bot.send_photo(order.operator.user_id, photo=file, caption=text, reply_markup=builder.as_markup(),
                                 parse_mode="Markdown")
        elif file_type == 'document':
            await bot.send_document(order.operator.user_id, document=file, caption=text,
                                    reply_markup=builder.as_markup(), parse_mode="Markdown")


async def order_canceled(order):
    bot = bot_oper
    text = order_text_for_op.format(ltc_sum=order.ltc_sum, kgs_sum=order.kgs_sum)
    text += "\n\n❌ Контр-агент отменил платеж"
    await bot.send_message(order.operator.user_id, text, parse_mode="Markdown")





