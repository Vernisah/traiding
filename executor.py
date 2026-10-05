"""
Модуль исполнения заявок через Finam API.
Проверяет деньги, позиции, выставляет заявки и SL/TP.
"""
import requests
import json
import os
import time
from datetime import datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from finam_api import get_token, ACCOUNT_ID, BASE_URL, TIMEOUT


# ==================== ПРОВЕРКА СЧЁТА ====================
def get_available_cash() -> float:
    """Возвращает свободные деньги на счёте."""
    token = get_token()
    if not token:
        return 0.0
    try:
        r = requests.get(
            f'{BASE_URL}/v1/accounts/{ACCOUNT_ID}',
            headers={'Authorization': f'Bearer {token}'},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        portfolio_mc = data.get('portfolio_mc', {})
        return float(portfolio_mc.get('available_cash', {}).get('value', 0))
    except Exception as e:
        print(f"  ⚠️ Ошибка проверки кэша: {type(e).__name__}")
        return 0.0


def get_open_positions() -> dict:
    """Возвращает открытые позиции в виде {ticker: quantity}."""
    token = get_token()
    if not token:
        return {}
    try:
        r = requests.get(
            f'{BASE_URL}/v1/accounts/{ACCOUNT_ID}',
            headers={'Authorization': f'Bearer {token}'},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        positions = {}
        for pos in data.get('positions', []):
            symbol = pos.get('symbol', '')
            ticker = symbol.split('@')[0] if '@' in symbol else symbol
            qty = float(pos.get('quantity', {}).get('value', 0))
            positions[ticker] = qty
        return positions
    except Exception as e:
        print(f"  ⚠️ Ошибка проверки позиций: {type(e).__name__}")
        return {}


# ==================== ЗАЯВКИ ====================
def place_market_order(symbol: str, quantity: int, side: str) -> dict | None:
    """Рыночная заявка."""
    token = get_token()
    if not token:
        return None
    url = f'{BASE_URL}/v1/accounts/{ACCOUNT_ID}/orders'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    payload = {
        'symbol': symbol,
        'quantity': {'value': str(quantity)},
        'side': side,
        'type': 'ORDER_TYPE_MARKET',
        'time_in_force': 'TIME_IN_FORCE_DAY',
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
        if r.status_code != 200:
            print(f"  ❌ Заявка отклонена: HTTP {r.status_code}")
            print(f"     {r.text[:400]}")
            return None
        print(f"  ✅ Заявка принята: {side} {quantity} {symbol}")
        return r.json()
    except Exception as e:
        print(f"  ⚠️ Ошибка заявки: {type(e).__name__}: {e}")
        return None


def place_limit_order(symbol: str, quantity: int, side: str, price: float) -> dict | None:
    """Лимитная заявка."""
    token = get_token()
    if not token:
        return None
    url = f'{BASE_URL}/v1/accounts/{ACCOUNT_ID}/orders'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    payload = {
        'symbol': symbol,
        'quantity': {'value': str(quantity)},
        'side': side,
        'type': 'ORDER_TYPE_LIMIT',
        'time_in_force': 'TIME_IN_FORCE_DAY',
        'limit_price': {'value': f'{price:.2f}'},
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
        if r.status_code != 200:
            print(f"  ❌ Лимитная заявка отклонена: HTTP {r.status_code}")
            print(f"     {r.text[:400]}")
            return None
        print(f"  ✅ Лимитная заявка: {side} {quantity} {symbol} @ {price}")
        return r.json()
    except Exception as e:
        print(f"  ⚠️ Ошибка заявки: {type(e).__name__}: {e}")
        return None


def place_sltp(symbol: str, side: str, quantity: int,
               sl_price: float, tp_price: float) -> dict | None:
    """SL/TP заявка."""
    token = get_token()
    if not token:
        return None
    url = f'{BASE_URL}/v1/accounts/{ACCOUNT_ID}/sltp-orders'
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    payload = {
        'symbol': symbol,
        'side': side,
        'quantity_sl': {'value': str(quantity)},
        'sl_price': {'value': f'{sl_price:.2f}'},
        'quantity_tp': {'value': str(quantity)},
        'tp_price': {'value': f'{tp_price:.2f}'},
        'valid_before': 'VALID_BEFORE_GOOD_TILL_CANCEL',
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
        if r.status_code != 200:
            print(f"  ❌ SL/TP отклонены: HTTP {r.status_code}")
            print(f"     {r.text[:400]}")
            return None
        print(f"  ✅ SL/TP: SL {sl_price}, TP {tp_price}")
        return r.json()
    except Exception as e:
        print(f"  ⚠️ Ошибка SL/TP: {type(e).__name__}: {e}")
        return None


# ==================== ГЛАВНАЯ ЛОГИКА ====================
def try_open_position(ticker: str, symbol: str, price: float,
                     stop: float, take: float, quantity: int = 1,
                     asset_type: str = 'stock') -> bool:
    """Проверяет деньги, позиции, выставляет заявку и SL/TP."""
    print(f"\n  🔍 Проверка {ticker}:")
    print(f"     Цена: {price} ₽ | Стоп: {stop} ₽ | Тейк: {take} ₽ | Кол-во: {quantity}")

    # 1. Деньги
    available = get_available_cash()
    needed = price * quantity
    print(f"     Свободно: {available:.2f} ₽ | Нужно: {needed:.2f} ₽")

    if available < needed:
        print(f"     ❌ Не хватает денег")
        return False

    # 2. Позиции
    positions = get_open_positions()
    if ticker in positions and positions[ticker] > 0:
        print(f"     ❌ Уже есть позиция: {positions[ticker]} шт")
        return False

    # 3. Заявка
    print(f"     ✅ Проверки пройдены. Выставляю...")
    result = place_limit_order(symbol, quantity, 'SIDE_BUY', price)
    if not result:
        return False

    # 4. SL/TP
    time.sleep(2)
    place_sltp(symbol, 'SIDE_SELL', quantity, stop, take)
    print(f"     ✅ Позиция открыта: {ticker} x{quantity} @ ~{price}")
    return True


def try_close_position(ticker: str, symbol: str, quantity: int) -> bool:
    """Закрывает позицию по рынку."""
    result = place_market_order(symbol, quantity, 'SIDE_SELL')
    if result:
        print(f"  ✅ Позиция закрыта: {ticker} x{quantity}")
        return True
    return False