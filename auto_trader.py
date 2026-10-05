"""
Автоторговля: проходит по сигналам, проверяет деньги и позиции, торгует.
"""
import os
import time
from monitor import get_signals
from executor import try_open_position, get_open_positions

os.chdir(os.path.dirname(os.path.abspath(__file__)))


# ==================== НАСТРОЙКИ ====================
AUTO_TRADE_ENABLED = True   # главный выключатель
MAX_POSITION_SIZE = 1       # максимум 1 акция на сделку


def run_once():
    print("=" * 60)
    print(f"🤖 АВТОТОРГОВЛЯ — {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    if not AUTO_TRADE_ENABLED:
        print("⚠️ Автоторговля выключена")
        return

    # 1. Сигналы
    signals, market = get_signals()
    print(f"\n📊 Тренд рынка: {market['trend']}")

    # 2. Позиции
    positions = get_open_positions()
    print(f"💼 Открытые позиции: {positions if positions else 'нет'}")

    # 3. Проходим по сигналам
    for s in signals:
        ticker = s['ticker']
        strategy = s['strategy']
        action = s['action']

        # Отладочный вывод: что вообще в сигнале
        print(f"\n  📌 {ticker} + {strategy}: {action} "
              f"(цена {s.get('price')}, тип {s.get('type')})")

        if action != 'BUY':
            continue

        print(f"\n🎯 СИГНАЛ: {ticker} + {strategy}")

        # Символ для API
        asset_type = s.get('type', 'stock')
        if asset_type == 'futures':
            symbol = f'{ticker}@RTSX'
        else:
            symbol = f'{ticker}@MISX'

        # Пытаемся открыть
        try_open_position(
            ticker=ticker,
            symbol=symbol,
            price=s['price'],
            stop=s['stop'],
            take=s['take'],
            quantity=MAX_POSITION_SIZE,
            asset_type=asset_type,
        )

    print("\n" + "=" * 60)
    print("✅ Проход завершён")
    print("=" * 60)


if __name__ == '__main__':
    run_once()