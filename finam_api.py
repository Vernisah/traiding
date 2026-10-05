"""
Клиент Finam Trade API.
С детальным выводом ошибок.
"""
import requests
import json
import os
import time
from datetime import datetime, timedelta

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ==================== НАСТРОЙКИ ====================
API_SECRET = 'tapi_sk_MbEZehFSSuq4TskuLKN3Vw'   # <-- замени на свой
ACCOUNT_ID = '2071784'

BASE_URL = 'https://api.finam.ru'
TOKEN_CACHE_FILE = 'finam_token.json'

TIMEOUT = 25
MAX_RETRIES = 3
RETRY_DELAY = 1.5


# ==================== АВТОРИЗАЦИЯ ====================
def get_token() -> str | None:
    """Получает JWT-токен (кэширует на 23 часа)."""
    if os.path.exists(TOKEN_CACHE_FILE):
        try:
            with open(TOKEN_CACHE_FILE, 'r') as f:
                cache = json.load(f)
            expires = datetime.fromisoformat(cache['expires'])
            if expires > datetime.now():
                return cache['token']
        except Exception:
            pass

    for attempt in range(MAX_RETRIES):
        try:
            r = requests.post(
                f'{BASE_URL}/v1/sessions',
                headers={'Content-Type': 'application/json'},
                data=json.dumps({'secret': API_SECRET}),
                timeout=TIMEOUT,
            )
            if r.status_code != 200:
                print(f"  ⚠️ Auth {attempt+1}/{MAX_RETRIES}: "
                      f"HTTP {r.status_code}, {r.text[:200]}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                continue

            token = r.json().get('token')
            if token:
                with open(TOKEN_CACHE_FILE, 'w') as f:
                    json.dump({
                        'token': token,
                        'expires': (datetime.now() + timedelta(hours=23)).isoformat(),
                    }, f)
                print("  ✅ Токен получен")
                return token
        except Exception as e:
            print(f"  ⚠️ Auth {attempt+1}/{MAX_RETRIES}: {type(e).__name__}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    return None


# ==================== БАЛАНС И ПОЗИЦИИ ====================
def get_account_info() -> dict | None:
    """Получает информацию о счёте с детальным выводом ошибок."""
    token = get_token()
    if not token:
        return None

    url = f'{BASE_URL}/v1/accounts/{ACCOUNT_ID}'

    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(
                url,
                headers={'Authorization': f'Bearer {token}'},
                timeout=TIMEOUT,
            )

            if r.status_code == 401:
                print(f"  ❌ Токен истёк (401). Удаляю кэш и пробую заново...")
                if os.path.exists(TOKEN_CACHE_FILE):
                    os.remove(TOKEN_CACHE_FILE)
                token = get_token()
                if not token:
                    return None
                continue

            if r.status_code == 404:
                print(f"  ❌ Счёт {ACCOUNT_ID} не найден (404). "
                      f"Проверь account_id в finam_api.py")
                return None

            if r.status_code == 429:
                print(f"  ⚠️ Превышен лимит запросов (429). Жду 5 сек...")
                time.sleep(5)
                continue

            if r.status_code != 200:
                print(f"  ⚠️ Finam API {attempt+1}/{MAX_RETRIES}: "
                      f"HTTP {r.status_code}, {r.text[:200]}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
                continue

            # Успех
            data = r.json()

            equity = float(data.get('equity', {}).get('value', 0))

            positions = []
            total_pnl = 0.0
            for pos in data.get('positions', []):
                symbol = pos.get('symbol', '')
                ticker = symbol.split('@')[0] if '@' in symbol else symbol

                qty = float(pos.get('quantity', {}).get('value', 0))
                avg_price = float(pos.get('average_price', {}).get('value', 0))
                curr_price = float(pos.get('current_price', {}).get('value', 0))
                unrealized = float(pos.get('unrealized_pnl', {}).get('value', 0))
                daily = float(pos.get('daily_pnl', {}).get('value', 0))

                positions.append({
                    'ticker': ticker,
                    'quantity': qty,
                    'avg_price': round(avg_price, 2),
                    'current_price': round(curr_price, 2),
                    'unrealized_pnl': round(unrealized, 2),
                    'daily_pnl': round(daily, 2),
                })
                total_pnl += unrealized

            cash_list = []
            for c in data.get('cash', []):
                cash_list.append({
                    'currency': c.get('currency_code', ''),
                    'units': c.get('units', '0'),
                    'nanos': c.get('nanos', 0),
                })

            portfolio_mc = data.get('portfolio_mc', {})
            available_cash = float(
                portfolio_mc.get('available_cash', {}).get('value', 0)
            )

            return {
                'account_id': ACCOUNT_ID,
                'equity': round(equity, 2),
                'available_cash': round(available_cash, 2),
                'unrealized_pnl': round(total_pnl, 2),
                'positions': positions,
                'cash': cash_list,
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
        except Exception as e:
            print(f"  ⚠️ Finam API {attempt+1}/{MAX_RETRIES}: "
                  f"{type(e).__name__}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)

    print("  ❌ Finam API не ответил после всех попыток")
    return None