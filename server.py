"""
Flask-сервер: реальный счёт Finam + сигналы + тренд + новости.
"""
from flask import Flask, render_template, jsonify
from config import USE_FINAM_API
from news import get_news
from finam_api import get_account_info
from monitor import get_signals

app = Flask(__name__)


@app.route('/')
def index():
    signals, market = get_signals()
    news = get_news(limit=15)
    account = get_account_info() if USE_FINAM_API else None

    return render_template('index.html',
                           signals=signals,
                           market=market,
                           news=news,
                           account=account)


@app.route('/api/account')
def api_account():
    account = get_account_info()
    if account:
        return jsonify({'success': True, 'account': account})
    return jsonify({'success': False, 'error': 'Не удалось получить данные'}), 500


@app.route('/api/signals')
def api_signals():
    signals, market = get_signals()
    return jsonify({'signals': signals, 'market': market})


if __name__ == '__main__':
    print("=" * 50)
    print("🌐 http://localhost:5000")
    print("=" * 50)
    app.run(debug=False, host='127.0.0.1', port=5000)