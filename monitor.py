"""
Логика сигналов.
Данные с MOEX ISS + фильтр по тренду IMOEX.
"""
import requests
import pandas as pd
import numpy as np
import time
import os
from datetime import datetime, timedelta

from config import (PORTFOLIO, TAKE_PROFIT_RATIO, USE_TREND_FILTER,
                    REQUEST_DELAY, MAX_RETRIES, RETRY_DELAY)


# ==================== ЗАГРУЗКА ====================
def _fetch_iss(url, params):
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, params=params, timeout=25)
            r.raise_for_status()
            data = r.json()
            c = data.get('candles', {})
            cols = c.get('columns', [])
            rows = c.get('data', [])
            if not rows:
                return None
            df = pd.DataFrame(rows, columns=cols)
            df = df.rename(columns={'begin': 'timestamp'})
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp').sort_index()
            keep = [x for x in ['open', 'high', 'low', 'close'] if x in df.columns]
            df = df[keep]
            for x in keep:
                df[x] = pd.to_numeric(df[x], errors='coerce')
            return df.dropna()
        except Exception:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            continue
    return None


def get_stock_data(ticker, days=365):
    end = datetime.now()
    start = end - timedelta(days=days)
    url = (f'https://iss.moex.com/iss/engines/stock/markets/shares/'
           f'boards/TQBR/securities/{ticker}/candles.json')
    params = {'from': start.strftime('%Y-%m-%d'),
              'till': end.strftime('%Y-%m-%d'),
              'interval': 24, 'iss.meta': 'off'}
    return _fetch_iss(url, params)


def get_futures_data(secid, days=365):
    end = datetime.now()
    start = end - timedelta(days=days)
    url = (f'https://iss.moex.com/iss/engines/futures/markets/forts/'
           f'securities/{secid}/candles.json')
    params = {'from': start.strftime('%Y-%m-%d'),
              'till': end.strftime('%Y-%m-%d'),
              'interval': 24, 'iss.meta': 'off'}
    return _fetch_iss(url, params)


# ==================== ТРЕНД ====================
def get_market_trend() -> dict:
    url = ('https://iss.moex.com/iss/engines/stock/markets/index/'
           'boards/SNDX/securities/IMOEX/candles.json')
    end = datetime.now()
    start = end - timedelta(days=180)
    params = {'from': start.strftime('%Y-%m-%d'),
              'till': end.strftime('%Y-%m-%d'),
              'interval': 24, 'iss.meta': 'off'}

    df = _fetch_iss(url, params)
    if df is None or len(df) < 50:
        return {'trend': 'UNKNOWN', 'price': None, 'sma50': None, 'change_pct': None}

    sma50 = df['close'].rolling(50).mean()
    last_price = float(df['close'].iloc[-1])
    last_sma = float(sma50.iloc[-1])
    prev = float(df['close'].iloc[-2]) if len(df) > 1 else last_price
    change_pct = (last_price - prev) / prev * 100

    return {
        'trend': 'UP' if last_price > last_sma else 'DOWN',
        'price': round(last_price, 2),
        'sma50': round(last_sma, 2),
        'change_pct': round(change_pct, 2),
    }


# ==================== СИГНАЛЫ ====================
def sig_donch_20(df):
    df = df.copy()
    df['h'] = df['high'].rolling(20).max()
    df['l'] = df['low'].rolling(20).min()
    df['signal_buy'] = df['close'] > df['h'].shift(1)
    df['signal_sell'] = df['close'] < df['l'].shift(1)
    return df

def sig_rsi(df):
    df = df.copy()
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).rolling(7).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(7).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi'] = 100 - (100 / (1 + rs))
    df['signal_buy'] = df['rsi'] < 30
    df['signal_sell'] = df['rsi'] > 70
    return df

def sig_doji(df):
    df = df.copy()
    body = abs(df['close'] - df['open'])
    rng = (df['high'] - df['low']).replace(0, 0.0001)
    small = body / rng < 0.1
    df['signal_buy'] = small
    df['signal_sell'] = small
    return df

def sig_ema_13_50(df):
    df = df.copy()
    df['e13'] = df['close'].ewm(span=13, adjust=False).mean()
    df['s50'] = df['close'].rolling(50).mean()
    df['signal_buy'] = (df['e13'] > df['s50']) & (df['e13'].shift(1) <= df['s50'].shift(1))
    df['signal_sell'] = (df['e13'] < df['s50']) & (df['e13'].shift(1) >= df['s50'].shift(1))
    return df

def sig_macd(df):
    df = df.copy()
    e12 = df['close'].ewm(span=12, adjust=False).mean()
    e26 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = e12 - e26
    df['sl'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['signal_buy'] = (df['macd'] > df['sl']) & (df['macd'].shift(1) <= df['sl'].shift(1))
    df['signal_sell'] = (df['macd'] < df['sl']) & (df['macd'].shift(1) >= df['sl'].shift(1))
    return df


SIGNALS = {
    'DOJI': sig_doji, 'RSI_7': sig_rsi, 'DONCH_20': sig_donch_20,
    'EMA_13_50': sig_ema_13_50, 'MACD': sig_macd,
}


# ==================== ГЛАВНОЕ ====================
def get_signals():
    signals = []

    market = get_market_trend() if USE_TREND_FILTER else {'trend': 'UNKNOWN'}
    trend = market['trend']
    print(f"  📊 Тренд рынка (IMOEX): {trend}")

    for item in PORTFOLIO:
        ticker = item['ticker']
        strategy = item['strategy']
        lookback = item['lookback']
        asset_type = item.get('type', 'stock')

        signal = {
            'ticker': ticker, 'strategy': strategy, 'type': asset_type,
            'action': 'WAIT', 'price': None,
            'stop': None, 'take': None, 'reason': '',
        }

        df = (get_futures_data(ticker, 365) if asset_type == 'futures'
              else get_stock_data(ticker, 365))

        time.sleep(REQUEST_DELAY)

        if df is None or len(df) < 60:
            signal['action'] = 'NO_DATA'
            signal['reason'] = 'нет данных'
            signals.append(signal)
            continue

        if strategy not in SIGNALS:
            signal['action'] = 'NO_DATA'
            signal['reason'] = f'нет сигнала {strategy}'
            signals.append(signal)
            continue

        try:
            df = SIGNALS[strategy](df)
            last = df.iloc[-1]
            price = float(last['close'])
            signal['price'] = round(price, 2)

            if last.get('signal_buy', False):
                if USE_TREND_FILTER and trend == 'DOWN':
                    signal['action'] = 'WAIT'
                    signal['reason'] = 'сигнал есть, но рынок падает'
                    signals.append(signal)
                    continue

                stop = float(df['low'].iloc[-lookback:].min())
                risk = price - stop
                if risk > 0:
                    take = price + risk * TAKE_PROFIT_RATIO
                    signal['action'] = 'BUY'
                    signal['stop'] = round(stop, 2)
                    signal['take'] = round(take, 2)
                    signal['reason'] = 'сигнал на покупку'
                else:
                    signal['reason'] = 'риск ≤ 0'
            else:
                signal['reason'] = 'ждём сигнала'
        except Exception as e:
            signal['action'] = 'NO_DATA'
            signal['reason'] = f'ошибка: {type(e).__name__}'

        signals.append(signal)

    return signals, market