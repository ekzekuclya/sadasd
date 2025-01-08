import asyncio
import math
import re

import requests
from aiogram.filters import BaseFilter

from ..text import order_text_for_op, order_text, order_text_usd
from ..models import TelegramUser, CurrentCourse, Order, Withdraw
from datetime import datetime, timedelta
from django.utils import timezone
from asgiref.sync import sync_to_async
from aiogram.types import Message, InlineKeyboardButton, ReplyKeyboardMarkup, ChatMemberOwner, ChatMemberAdministrator, \
    CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


async def convert_ltc_to_usdt(ltc_amount, count=0):
    try:
        ltc_amount = float(ltc_amount)
        url = "https://api.binance.com/api/v3/ticker/price?symbol=LTCUSDT"
        response = requests.get(url)

        if response.status_code != 200:
            await convert_ltc_to_usdt(ltc_amount, count+1)

        data = response.json()
        last_price = float(data['price'])  # Цена последней сделки
        total_usdt = ltc_amount * last_price
        total_usdt = total_usdt * 1.01
        return total_usdt
    except Exception as e:
        print(e)


class NewOrInactiveUserFilter(BaseFilter):
    async def __call__(self, msg: Message) -> bool:
        if msg.text:
            user_id = msg.from_user.id
            user, created = TelegramUser.objects.get_or_create(
                user_id=user_id,
                defaults={'last_message_time': timezone.now()}
            )
            if created:
                return True
            if user.is_admin:
                return False
            last_message_time = user.last_message_time
            print("LAST MSG", last_message_time)
            print("TIME NOW", timezone.now())
            if last_message_time is None or timezone.now() - last_message_time > timedelta(minutes=15):
                return True

        return False


class IsUSDT(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        if message.text:
            text = message.text.strip()
            print(text)
            if text.endswith("$"):
                amount = text[:-1]
                try:
                    int(amount)
                    withdrawals = await sync_to_async(Withdraw.objects.filter)(chat_id=message.chat.id, active=True)
                    if withdrawals.exists():
                        for i in withdrawals:
                            i.active = False
                            i.save()
                        new_withdrawal = await sync_to_async(Withdraw.objects.create)(chat_id=message.chat.id,
                                                                                      amount=amount,
                                                                                      symbol="USDT", active=True)
                    elif not withdrawals:
                        new_withdrawal = await sync_to_async(Withdraw.objects.create)(chat_id=message.chat.id,
                                                                                      amount=amount,
                                                                                      symbol="USDT", active=True)
                    return True
                except ValueError:
                    return False
        return False


class IsFloatFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        if message.text:
            text = message.text.replace(",", ".")
            if "." in text:
                try:
                    amount = float(text)
                    withdrawals = await sync_to_async(Withdraw.objects.filter)(chat_id=message.chat.id, active=True)
                    if withdrawals.exists():
                        for i in withdrawals:
                            i.active = False
                            i.save()
                        new_withdrawal = await sync_to_async(Withdraw.objects.create)(chat_id=message.chat.id,
                                                                                      amount=amount,
                                                                                      symbol="LTC", active=True)
                    elif not withdrawals:
                        new_withdrawal = await sync_to_async(Withdraw.objects.create)(chat_id=message.chat.id,
                                                                                      amount=amount,
                                                                                      symbol="LTC", active=True)
                    return True
                except ValueError:
                    return False
        return False


import re
from aiogram.filters import BaseFilter
from aiogram.types import Message


class IsLTCReq(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        try:
            if message.text:
                req = message.text
                traditional_pattern = r'^[L3][A-Za-z0-9]{26,33}$'
                bech32_pattern = r'^ltc1[qpzry9x8gf2tvdw0s3jn54khce6mua7l]{39,59}$'
                p2sh_pattern = r'^M[A-Za-z0-9]{26,33}$'

                return any([
                    re.match(traditional_pattern, req),
                    re.match(bech32_pattern, req),
                    re.match(p2sh_pattern, req)
                ])
        except Exception as e:
            return False


async def convert_kgs_to_ltc(msg, kgs_amount):
    try:
        kgs_amount = float(kgs_amount)
    except ValueError:
        await msg.answer("Сумма в KGS должна быть числом.\nНапример 100 или 500.")
        return
    try:
        course = await sync_to_async(CurrentCourse.objects.latest)('id')
    except CurrentCourse.DoesNotExist:
        await msg.answer("Ошибка: курс USDT-KGS не найден.")
        return

    usdt_amount = kgs_amount / course.usdt
    url = "https://api.binance.com/api/v3/ticker/price?symbol=LTCUSDT"
    response = requests.get(url)
    if response.status_code != 200:
        await msg.answer("Не удалось получить курс LTC-USDT. Повторите позже.")
        return

    data = response.json()
    ltc_price_usdt = float(data['price'])
    ltc_amount = usdt_amount / ltc_price_usdt


    return ltc_amount


async def check_invoice_paid(msg, order):
    count = 0
    req = False

    while True:
        order = await sync_to_async(Order.objects.get)(id=order.id)
        if order.req and not req:
            text = order_text_for_op.format(ltc_sum=order.ltc_sum, kgs_sum=order.kgs_sum)
            text += "\n`" + order.req + "`\n\n"
            text += "После оплаты нажмите кнопку и отправьте чек"
            builder = InlineKeyboardBuilder()
            builder.add(InlineKeyboardButton(text="Я оплатил, готов отправить чек", callback_data=f"client_payed_{order.id}"))
            builder.add(InlineKeyboardButton(text="Отмена платежа", callback_data=f"client_canceled_{order.id}"))
            builder.adjust(1)
            await msg.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
            order.status = "wait_for_pay"
            order.save()
            req = True
        elif order.status == "declined":
            await msg.answer("❌ Платеж не принят!")
            break
        elif order.status == "confirmed":
            await msg.answer("✅ Платеж поступил, выдаю чек")
            break
        elif count >= 15:
            if not order.req:
                await msg.answer(f"Просим прощения, все реквизиты сейчас заняты, обратитесь позже")
            else:
                await msg.answer("Платеж отменен, просим не злоупотреблять ботом :)")
            break
        elif order.status == "canceled":
            await msg.answer("Платеж отменен, просим не злоупотреблять ботом :)")
            break
        else:
            count += 0.08
            await asyncio.sleep(5)


async def comsusdt(msg, usdt_sum, user):
    if usdt_sum is not None:
        if usdt_sum >= 1:
            course = await sync_to_async(CurrentCourse.objects.first)()
            if usdt_sum <= 5:
                kgs_sum = usdt_sum * course.usdt + course.coms_5
                coms = course.coms_5
            elif 5 < usdt_sum <= 10:
                kgs_sum = usdt_sum * course.usdt + course.coms_5_10
                coms = course.coms_5_10
            elif 10 < usdt_sum <= 20:
                kgs_sum = usdt_sum * course.usdt + course.coms_10_20
                coms = course.coms_10_20
            elif 20 < usdt_sum <= 30:
                kgs_sum = usdt_sum * course.usdt + course.coms_20_30
                coms = course.coms_20_30
            elif 30 < usdt_sum <= 70:
                kgs_sum = usdt_sum * course.usdt + course.coms_30_70
                coms = course.coms_30_70
            elif 70 < usdt_sum <= 120:
                kgs_sum = usdt_sum * course.usdt + course.coms_70_120
                coms = course.coms_70_120

            ord_text = order_text_usd.format(kgs_sum=int(kgs_sum), usdt_sum=usdt_sum)
            # order = await sync_to_async(Order.objects.create)(ltc_sum=float(ltc_sum), status="created",
            #                                                   kgs_sum=kgs_sum, coms=coms, client=user)
            # builder = InlineKeyboardBuilder()
            # builder.add(InlineKeyboardButton(text="Подтверждаю", callback_data=f"order_{order.id}"))
            await msg.answer(f"{ord_text}", parse_mode="Markdown")


async def coms(msg, total_usdt, ltc_sum, user, usdt_sum=None):
    if ltc_sum:
        if total_usdt >= 1:
            course = await sync_to_async(CurrentCourse.objects.first)()
            if total_usdt <= 5:
                kgs_sum = total_usdt * course.usdt + course.coms_5
                coms = course.coms_5
            elif 5 < total_usdt <= 10:
                kgs_sum = total_usdt * course.usdt + course.coms_5_10
                coms = course.coms_5_10
            elif 10 < total_usdt <= 20:
                kgs_sum = total_usdt * course.usdt + course.coms_10_20
                coms = course.coms_10_20
            elif 20 < total_usdt <= 30:
                kgs_sum = total_usdt * course.usdt + course.coms_20_30
                coms = course.coms_20_30
            elif 30 < total_usdt <= 70:
                kgs_sum = total_usdt * course.usdt + course.coms_30_70
                coms = course.coms_30_70
            elif 70 < total_usdt <= 120:
                kgs_sum = total_usdt * course.usdt + course.coms_70_120
                coms = course.coms_70_120

            print(ltc_sum)
            ord_text = order_text.format(ltc_sum=ltc_sum, kgs_sum=int(kgs_sum))
            await msg.answer(f"{ord_text}", parse_mode="Markdown")





def name(user):
    link = "tg://user?id="
    # Проверяем наличие имени, фамилии и username
    if user.username:
        player_username = f"@{user.username}"
    else:
        first_name = user.first_name if user.first_name else "User"
        last_name = f" {user.last_name}" if user.last_name else ""
        player_username = f"[{first_name}{last_name}]({link}{str(user.user_id)})"

    # Экранируем нижнее подчеркивание, чтобы избежать Markdown-разметки
    player_username = player_username.replace("_", r"\_")
    return "👤 " + player_username


async def convert_usdt_to_ltc(usdt_amount):
    try:
        url = "https://api.binance.com/api/v3/ticker/price?symbol=LTCUSDT"
        response = requests.get(url)
        if response.status_code != 200:
            print("Не удалось получить курс LTC-USDT. Повторите позже.")
            return None
        data = response.json()
        ltc_price_usdt = float(data['price'])
        ltc_amount = usdt_amount / ltc_price_usdt
        return ltc_amount

    except Exception as e:
        print(f"Произошла ошибка: {e}")
        return None


async def get_balance(asset, client):
    try:

        balance = client.get_asset_balance(asset=asset)
        return float(balance['free']) if balance else 0.0
    except BinanceAPIException as e:
        print(f"Ошибка получения баланса: {e}")
        return 0.0


async def get_lot_size(symbol, client):
    """Получить параметры LOT_SIZE для символа."""
    try:
        exchange_info = client.get_symbol_info(symbol)
        for filt in exchange_info['filters']:
            if filt['filterType'] == 'LOT_SIZE':
                return {
                    'minQty': float(filt['minQty']),
                    'maxQty': float(filt['maxQty']),
                    'stepSize': float(filt['stepSize']),
                }
    except BinanceAPIException as e:
        print(f"Ошибка получения LOT_SIZE: {e}")
        return None



async def adjust_quantity(qty, step_size):
    return math.floor(qty / step_size) * step_size


async def check_decimals(symbol, client):
    info = await client.get_symbol_info(symbol)
    decimal = 0
    for filt in info['filters']:
        if filt['filterType'] == 'LOT_SIZE':
            step_size = filt['stepSize']
            is_dec = False
            for c in step_size:
                if is_dec:
                    decimal += 1
                if c == '1':
                    break
                if c == '.':
                    is_dec = True
            return decimal
    return 0



async def get_notional_filter(symbol, client):
    try:
        exchange_info = client.get_symbol_info(symbol)
        for filt in exchange_info['filters']:
            if filt['filterType'] == 'NOTIONAL':
                return {
                    'minNotional': float(filt['minNotional']),
                    'maxNotional': float(filt['maxNotional']),
                }
    except BinanceAPIException as e:
        print(f"Ошибка получения NOTIONAL: {e}")
        return None

async def buy_ltc_with_usdt(amount_ltc, client):
    symbol = 'LTCUSDT'
    try:
        # Получение текущей цены
        ticker = client.get_ticker(symbol=symbol)
        price = float(ticker['lastPrice'])
        print(f"Текущая цена {symbol}: {price} USDT")

        # Проверка LOT_SIZE
        lot_size = await get_lot_size(symbol, client)
        if not lot_size:
            return

        # Проверка минимального количества
        min_qty = lot_size['minQty']
        if amount_ltc < min_qty:
            print(f"Минимальное количество для покупки {symbol} — {min_qty}. Ваш запрос: {amount_ltc}")
            return

        # Определяем количество десятичных знаков
        decimal = check_decimals(symbol, client)
        adjusted_qty = round(amount_ltc, decimal)
        print(f"Скорректированное количество LTC: {adjusted_qty}")

        # Проверка баланса USDT
        balance_usdt = float(client.get_asset_balance(asset='USDT')['free'])
        cost = adjusted_qty * price

        if cost > balance_usdt:
            print(f"Недостаточно USDT: нужно {cost}, доступно {balance_usdt}")
            return

        # Проверка NOTIONAL
        notional_filter = get_notional_filter(symbol)
        if not notional_filter:
            return

        # Убедимся, что стоимость ордера лежит в допустимом диапазоне
        if cost < notional_filter['minNotional']:
            print(f"Стоимость ордера слишком мала: нужно минимум {notional_filter['minNotional']} USDT.")
            return
        if cost > notional_filter['maxNotional']:
            print(f"Стоимость ордера слишком велика: максимальный размер {notional_filter['maxNotional']} USDT.")
            return

        # Размещение ордера
        order = client.order_market_buy(
            symbol=symbol,
            quantity=adjusted_qty
        )
        print(f"Успешно куплено {adjusted_qty} LTC за {cost} USDT.")
        return order

    except BinanceAPIException as e:
        print(f"Ошибка при покупке: {e}")
        return None





def withdraw(asset, address, amount, network=None):
    """Вывод средств на внешний адрес."""
    try:
        result = client.withdraw(
            coin=asset,
            address=address,
            amount=amount,
            network=network
        )
        print(f"Вывод успешно выполнен: {result}")
        return result
    except BinanceAPIException as e:
        print(f"Ошибка вывода: {e}")
        return None