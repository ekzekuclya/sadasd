import asyncio
import math
import decimal
from binance.async_client import AsyncClient, BinanceAPIException
import re
from ..models import Withdraw, Client, Ticket
from asgiref.sync import sync_to_async
from binance.async_client import AsyncClient

import asyncio

async def convert_usdt_to_ltc(client, target_ltc_amount):
    try:
        ticker = await client.get_ticker(symbol='LTCUSDT')
        price = float(ticker['lastPrice'])
        percent = 0.1
        adjusted_ltc_amount = target_ltc_amount / (1 - percent / 100)
        adjusted_ltc_amount = round(adjusted_ltc_amount, 3)
        account_info = await client.get_account()
        usdt_balance = next((float(asset['free']) for asset in account_info['balances'] if asset['asset'] == 'USDT'), 0)

        if usdt_balance <= 0:
            print(f"Недостаточно средств на счете USDT: доступно {usdt_balance} USDT.")
            return
        max_ltc = usdt_balance / price
        if adjusted_ltc_amount > max_ltc:
            print(f"Недостаточно средств для покупки {adjusted_ltc_amount} LTC. Максимальное количество: {max_ltc}.")
            return
        order = await client.order_market_buy(
            symbol='LTCUSDT',
            quantity=adjusted_ltc_amount
        )
        return order
    except Exception as e:
        print(f"Произошла ошибка: {e}")




async def crypto_sender(wth_id, msg, bot):
    db_c = await sync_to_async(Client.objects.first)()
    withdraw = await sync_to_async(Withdraw.objects.get)(id=wth_id)
    client = await AsyncClient.create(db_c.key, db_c.secret)
    result = await convert_usdt_to_ltc(client, withdraw.amount)
    result_withdraw = await send_ltc(client, withdraw.amount, withdraw.req)
    withdraw.completed = True
    withdraw.save()
    if result_withdraw:
        print(result_withdraw)
        id_value = result_withdraw['id']
        await msg.answer(f"TXII {id_value}")
        bot_user = await bot.get_me()
        user_bot = bot_user.username
        ticket = await sync_to_async(Ticket.objects.create)()
        url = f"http://t.me/{user_bot}?start={ticket.ticket}"
        text = f"[🎟 *Ваш билет* 🎟]({url})\n`Нажмите на билет, для активации`"
        await msg.answer(text, parse_mode="Markdown")

async def send_ltc(client, amount, to_address, network='LTC'):
    try:
        if amount <= 0:
            return
        account_info = await client.get_account()
        ltc_balance = next((float(asset['free']) for asset in account_info['balances'] if asset['asset'] == 'LTC'), 0)
        if ltc_balance < amount:
            return
        withdrawal = await client.withdraw(
            coin='LTC',
            amount=amount,
            address=to_address,
        )
        print(f"Перевод {amount} LTC успешно отправлен на адрес {to_address}. Ответ: {withdrawal}")
        return withdrawal
    except Exception as e:
        print(f"Произошла ошибка при отправке LTC: {e}")
    finally:
        await client.close_connection()

