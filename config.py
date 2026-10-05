"""
Конфигурация портфеля MOEX.
"""
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ==================== РЕЖИМ ====================
USE_FINAM_API = True
USE_TREND_FILTER = True   # фильтр по тренду IMOEX

# ==================== ПОРТФЕЛЬ ====================
PORTFOLIO = [
    {'ticker': 'MGNT', 'strategy': 'DOJI',       'lookback': 5, 'type': 'stock'},
    {'ticker': 'MGNT', 'strategy': 'RSI_7',      'lookback': 5, 'type': 'stock'},
    {'ticker': 'MGNT', 'strategy': 'DONCH_20',   'lookback': 5, 'type': 'stock'},
    {'ticker': 'YDEX', 'strategy': 'RSI_7',      'lookback': 5, 'type': 'stock'},
    {'ticker': 'SBER', 'strategy': 'RSI_7',      'lookback': 5, 'type': 'stock'},
    {'ticker': 'CNYRUBF', 'strategy': 'MACD',    'lookback': 5, 'type': 'futures'},
    {'ticker': 'CNYRUBF', 'strategy': 'RSI_7',   'lookback': 5, 'type': 'futures'},
    {'ticker': 'GAZPF',   'strategy': 'EMA_13_50','lookback': 5, 'type': 'futures'},
]

# ==================== ПАРАМЕТРЫ ====================
TAKE_PROFIT_RATIO = 2.0

# ==================== ЗАДЕРЖКИ ====================
REQUEST_DELAY = 0.3
MAX_RETRIES = 3
RETRY_DELAY = 1.0