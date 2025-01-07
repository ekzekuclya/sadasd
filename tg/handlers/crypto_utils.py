import asyncio
import math
from binance.async_client import AsyncClient, BinanceAPIException
import re
from ..models import Withdraw, Client
from asgiref.sync import sync_to_async
async def get_balance(client, asset):
    try:
        balance = await client.get_asset_balance(asset=asset)
        return float(balance['free']) if balance else 0.0
    except BinanceAPIException as e:
        print(f"Ошибка получения баланса: {e}")
        return 0.0
async def get_lot_size(client, symbol):
    """Получить параметры LOT_SIZE для символа."""
    try:
        exchange_info = await client.get_symbol_info(symbol)
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
async def check_decimals(client, symbol):
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
    print("Не найден фильтр LOT_SIZE.")
    return 0
async def get_notional_filter(client, symbol):
    try:
        exchange_info = await client.get_symbol_info(symbol)
        for filt in exchange_info['filters']:
            if filt['filterType'] == 'NOTIONAL':
                return {
                    'minNotional': float(filt['minNotional']),
                    'maxNotional': float(filt['maxNotional']),
                }
    except BinanceAPIException as e:
        print(f"Ошибка получения NOTIONAL: {e}")
        return None


async def buy_ltc_with_usdt(client, amount_ltc):
    symbol = 'LTCUSDT'
    try:
        ticker = await client.get_ticker(symbol=symbol)
        price = float(ticker['lastPrice'])
        print(f"Текущая цена {symbol}: {price} USDT")

        lot_size = await get_lot_size(client, symbol)
        if not lot_size:
            return

        min_qty = lot_size['minQty']
        if amount_ltc < min_qty:
            print(f"Минимальное количество для покупки {symbol} — {min_qty}. Ваш запрос: {amount_ltc}")
            return

        decimal = await check_decimals(client, symbol)
        adjusted_qty = round(amount_ltc, decimal)
        print(f"Скорректированное количество LTC: {adjusted_qty}")

        balance_usdt = float((await client.get_asset_balance(asset='USDT'))['free'])
        cost = adjusted_qty * price

        if cost > balance_usdt:
            print(f"Недостаточно USDT: нужно {cost}, доступно {balance_usdt}")
            return

        notional_filter = await get_notional_filter(client, symbol)
        if not notional_filter:
            return

        if cost < notional_filter['minNotional']:
            print(f"Стоимость ордера слишком мала: нужно минимум {notional_filter['minNotional']} USDT.")
            return
        if cost > notional_filter['maxNotional']:
            print(f"Стоимость ордера слишком велика: максимум {notional_filter['maxNotional']} USDT.")
            return

        order = await client.order_market_buy(
            symbol=symbol,
            quantity=adjusted_qty
        )
        print(f"Успешно куплено {adjusted_qty} LTC за {cost} USDT.")
        return order

    except BinanceAPIException as e:
        print(f"Ошибка при покупке: {e}")
        return None


async def withdraw(client, asset, address, amount, network=None):
    """Вывод средств на внешний адрес."""
    try:
        result = await client.withdraw(
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


async def crypto_sender(withdraw_id):
    binance = await sync_to_async(Client.objects.first)()
    client = await AsyncClient.create(api_key=binance.key, api_secret=binance.secret)
    withdraw = await sync_to_async(Withdraw.objects.get)(id=withdraw_id)

    try:
        info = await client.get_symbol_info('LTCUSDT')

        balance = await get_balance(client, "USDT")

        await buy_ltc_with_usdt(client, withdraw.amount)
    finally:
        await client.close_connection()
