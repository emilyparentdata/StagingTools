"""
article_fetcher.py — Fetch ParentData articles and suggest related ones.

Uses the WordPress REST API to build a full article index (with local file
caching). Falls back to the RSS feed if the API is unreachable.

The cache is stored in .article_cache.json next to this file and refreshes
automatically every CACHE_MAX_AGE seconds (default 24 h).
"""

import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

API_BASE = 'https://parentdata.org/wp-json/wp/v2/posts'
RSS_URL = 'https://parentdata.org/feed/'
MEDIA_NS = 'http://search.yahoo.com/mrss/'

CACHE_FILE = Path(__file__).parent / '.article_cache.json'
CACHE_MAX_AGE = 24 * 60 * 60  # 24 hours in seconds

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; ParentData-StagingTool/1.0)',
    'Accept': 'application/json, application/rss+xml, application/xml, text/xml, */*',
}

# Words too short or too common to contribute to relevance scoring
STOP_WORDS = {
    'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can',
    'was', 'has', 'had', 'its', 'one', 'with', 'this', 'that', 'from',
    'they', 'have', 'will', 'your', 'what', 'how', 'does', 'did', 'been',
    'more', 'also', 'when', 'than', 'into', 'each', 'our', 'may',
}


# ── Public API ─────────────────────────────────────────────────────────────────

def fetch_related_articles(
    topic_tags: list = None,
    keywords: list = None,
    count: int = 5,
) -> list:
    """
    Return the top `count` articles most relevant to the given tags/keywords.

    Args:
        topic_tags: Topic tag strings from the document (e.g. ["Hormones"]).
        keywords:   Power keyword strings from the document.
        count:      Maximum number of results to return.

    Returns:
        List of dicts: {title, url, description, image_url, image_alt, score}
    """
    articles = _load_articles()
    search_terms = _build_search_terms(topic_tags, keywords)

    scored = []
    for a in articles:
        combined = (a['title'] + ' ' + a['description']).lower()
        score = sum(1 for t in search_terms if t in combined)
        scored.append({**a, 'score': score})

    scored.sort(key=lambda x: x['score'], reverse=True)
    return scored[:count]


def refresh_cache() -> dict:
    """
    Force a full re-fetch from the WordPress API and save to cache.

    Returns a summary dict: {article_count, fetched_at}
    """
    print('[article_fetcher] Forcing cache refresh…')
    articles = _fetch_wp_api()
    if not articles:
        print('[article_fetcher] WP API failed, falling back to RSS…')
        articles = _fetch_rss()

    fetched_at = time.time()
    if articles:
        CACHE_FILE.write_text(
            json.dumps({'fetched_at': fetched_at, 'articles': articles},
                       ensure_ascii=False),
            encoding='utf-8',
        )
        print(f'[article_fetcher] Cached {len(articles)} articles')

    return {'article_count': len(articles), 'fetched_at': fetched_at}


def find_article_by_url(url: str) -> dict | None:
    """
    Look up a cached article by its exact URL.

    Returns the article dict (title, url, description, image_url, image_alt)
    or None if not found in the index.
    """
    articles = _load_articles()
    url = url.rstrip('/')
    for a in articles:
        if a.get('url', '').rstrip('/') == url:
            return a
    return None


def cache_info() -> dict:
    """Return metadata about the current cache without fetching anything."""
    if not CACHE_FILE.exists():
        return {'cached': False}
    try:
        data = json.loads(CACHE_FILE.read_text(encoding='utf-8'))
        age_seconds = time.time() - data.get('fetched_at', 0)
        return {
            'cached': True,
            'article_count': len(data.get('articles', [])),
            'age_hours': round(age_seconds / 3600, 1),
            'stale': age_seconds >= CACHE_MAX_AGE,
        }
    except Exception:
        return {'cached': False}


# ── Internal helpers ────────────────────────────────────────────────────────────

def _load_articles() -> list:
    """Load from cache if fresh; otherwise fetch and update cache."""
    if CACHE_FILE.exists():
        try:
            data = json.loads(CACHE_FILE.read_text(encoding='utf-8'))
            age = time.time() - data.get('fetched_at', 0)
            if age < CACHE_MAX_AGE:
                count = len(data['articles'])
                print(
                    f'[article_fetcher] Using cached index '
                    f'({count} articles, {int(age / 3600)}h old)'
                )
                return data['articles']
        except Exception:
            pass

    print('[article_fetcher] Fetching full article index from WordPress API…')
    articles = _fetch_wp_api()
    if not articles:
        print('[article_fetcher] WP API failed, falling back to RSS…')
        articles = _fetch_rss()

    if articles:
        try:
            CACHE_FILE.write_text(
                json.dumps({'fetched_at': time.time(), 'articles': articles},
                           ensure_ascii=False),
                encoding='utf-8',
            )
            print(f'[article_fetcher] Cached {len(articles)} articles')
        except Exception as e:
            print(f'[article_fetcher] Cache write failed: {e}')

    return articles


def _fetch_wp_api() -> list:
    """
    Paginate through the WordPress REST API and return all published posts.

    Uses ?_embed=wp:featuredmedia to get featured image URLs in a single
    request per page rather than requiring a separate media lookup per post.
    """
    articles = []
    page = 1

    while True:
        try:
            resp = requests.get(
                API_BASE,
                params={
                    'per_page': 100,
                    'page': page,
                    '_embed': 'wp:featuredmedia',
                    'status': 'publish',
                },
                headers=HEADERS,
                timeout=30,
            )
        except Exception as e:
            print(f'[article_fetcher] WP API request error (page {page}): {e}')
            break

        # WordPress returns 400 when page exceeds total pages
        if resp.status_code == 400:
            break
        try:
            resp.raise_for_status()
        except Exception as e:
            print(f'[article_fetcher] WP API HTTP error (page {page}): {e}')
            break

        try:
            posts = resp.json()
        except Exception:
            break

        if not posts:
            break

        for post in posts:
            title = _strip_html(post.get('title', {}).get('rendered', ''))
            url = post.get('link', '')
            raw_excerpt = _strip_html(post.get('excerpt', {}).get('rendered', ''))
            description = _short_tagline(raw_excerpt)

            # Featured image URL from _embedded block
            image_url = ''
            embedded = post.get('_embedded', {})
            media_list = embedded.get('wp:featuredmedia', [])
            if media_list and isinstance(media_list, list):
                first = media_list[0]
                # Prefer a medium-sized version to keep URLs lightweight
                sizes = first.get('media_details', {}).get('sizes', {})
                image_url = (
                    sizes.get('medium_large', {}).get('source_url')
                    or sizes.get('large', {}).get('source_url')
                    or sizes.get('full', {}).get('source_url')
                    or first.get('source_url', '')
                )

            articles.append({
                'title': title,
                'url': url,
                'description': description,
                'image_url': image_url,
                'image_alt': title,
            })

        total_pages = int(resp.headers.get('X-WP-TotalPages', 1))
        print(f'[article_fetcher] Page {page}/{total_pages} — {len(articles)} articles so far')
        if page >= total_pages:
            break
        page += 1

    return articles


def _fetch_rss() -> list:
    """Fallback: fetch the RSS feed (most recent ~10-20 articles only)."""
    try:
        resp = requests.get(RSS_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception as e:
        print(f'[article_fetcher] RSS fetch failed: {e}')
        return []

    channel = root.find('channel')
    if channel is None:
        return []

    articles = []
    for item in channel.findall('item'):
        title = (item.findtext('title') or '').strip()
        url = (item.findtext('link') or '').strip()
        description = _short_tagline(
            _strip_html((item.findtext('description') or '').strip())
        )
        image_url = ''
        mc = item.find(f'{{{MEDIA_NS}}}content')
        if mc is not None:
            image_url = mc.get('url', '')
        if not image_url:
            enc = item.find('enclosure')
            if enc is not None:
                image_url = enc.get('url', '')
        articles.append({
            'title': title,
            'url': url,
            'description': description,
            'image_url': image_url,
            'image_alt': title,
        })
    return articles


def _build_search_terms(topic_tags, keywords) -> set:
    search_terms = set()
    for source in [topic_tags or [], keywords or []]:
        for term in source:
            for word in re.split(r'\W+', term.lower()):
                if len(word) > 3 and word not in STOP_WORDS:
                    search_terms.add(word)
    return search_terms


def _strip_html(text: str) -> str:
    return re.sub(r'<[^>]+>', '', text).strip()


def _short_tagline(text: str, max_len: int = 70) -> str:
    """Trim to the first sentence; hard-cap at max_len characters."""
    if not text:
        return ''
    m = re.search(r'[.!?]', text)
    if m and m.start() < max_len:
        text = text[:m.start() + 1]
    if len(text) > max_len:
        text = text[:max_len].rsplit(' ', 1)[0].rstrip('.,;:') + '…'
    return text.strip()
