# import requests
#
# def convert_ltc_to_usdt(ltc_amount):
#     # Получаем курс LTC к USD
#     url_ltc = "https://api.coingecko.com/api/v3/simple/price?ids=litecoin&vs_currencies=usd"
#     response_ltc = requests.get(url_ltc)
#     ltc_to_usd = response_ltc.json()['litecoin']['usd']
#
#     # Получаем курс USDT к USD
#     url_usdt = "https://api.coingecko.com/api/v3/simple/price?ids=tether&vs_currencies=usd"
#     response_usdt = requests.get(url_usdt)
#     usdt_to_usd = response_usdt.json()['tether']['usd']
#
#     # Конвертируем LTC в USD
#     total_usd = ltc_amount * ltc_to_usd
#
#     # Конвертируем USD в USDT
#     total_usdt = total_usd / usdt_to_usd
#
#     return total_usdt
#
#
# a = convert_ltc_to_usdt(0.519076)
# print(a)


import requests


def convert_ltc_to_usdt(ltc_amount):
    # Получаем данные о ценах LTC/USDT через Binance API
    url = "https://api.binance.com/api/v3/ticker/price?symbol=LTCUSDT"
    response = requests.get(url)

    if response.status_code != 200:
        raise Exception("Ошибка при получении данных с Binance API")

    data = response.json()

    # Получаем последнюю цену
    last_price = float(data['price'])  # Цена последней сделки

    # Используем последнюю цену для конвертации
    total_usdt = ltc_amount * last_price

    # Учитываем комиссию (например, 0.1%)
    commission_rate = 0.01  # 0.1%
    commission = total_usdt * commission_rate
    print(total_usdt + commission)
    print(total_usdt * 1.01)
    total_usdt_after_commission = total_usdt - commission

    # Увеличиваем итоговую сумму на 1%
    total_usdt_after_commission *= 1.01

    return total_usdt, total_usdt_after_commission


# Пример использования
ltc_amount = 0.492525  # количество LTC, которое вы хотите конвертировать
total_usdt, usdt_amount_after_commission = convert_ltc_to_usdt(ltc_amount)

print(f"Сумма в USDT до вычета комиссии: {total_usdt:.2f}$")
print(f"Сумма в USDT после учета комиссии: {usdt_amount_after_commission:.2f}$")