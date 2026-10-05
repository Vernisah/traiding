"""
Парсер новостей с РБК и других источников.
"""
import feedparser
import os
from datetime import datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))

RSS_FEEDS = {
    'РБК': 'https://rssexport.rbc.ru/rbcnews/news/30/full.rss',
    'Лента': 'https://lenta.ru/rss/news',
    'ТАСС': 'https://tass.ru/rss/v2.xml',
}

KEYWORDS = [
    'акци', 'биржа', 'мосбирж', 'сбер', 'газпром', 'яндекс', 'магнит',
    'нефть', 'рубль', 'доллар', 'фьючерс', 'трейдер', 'инвестор',
    'дивиденд', 'прибыль', 'убыток', 'рынок', 'торги', 'цб', 'ставк',
]


def get_news(limit: int = 15) -> list:
    news_list = []
    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:30]:
                title = entry.get('title', '')
                link = entry.get('link', '')
                title_lower = title.lower()
                if any(kw in title_lower for kw in KEYWORDS):
                    try:
                        dt = datetime(*entry.published_parsed[:6])
                        pub_str = dt.strftime('%d.%m %H:%M')
                    except Exception:
                        pub_str = ''
                    news_list.append({
                        'source': source,
                        'title': title,
                        'link': link,
                        'published': pub_str,
                        'timestamp': entry.get('published_parsed', None),
                    })
        except Exception as e:
            print(f"  ⚠️ Ошибка загрузки {source}: {type(e).__name__}")
            continue

    news_list.sort(
        key=lambda x: x['timestamp'] or (0, 0, 0, 0, 0, 0),
        reverse=True,
    )
    return news_list[:limit]