"""
wp_fetcher.py — Fetch a published ParentData article from the WordPress REST API.

Returns article metadata + raw content HTML for Claude to reformat.

Authentication:
    ParentData articles are subscriber-only. Without credentials the REST API
    returns only the public teaser. Set WP_APP_USERNAME and WP_APP_PASSWORD in
    .env to authenticate and receive the full content.

    Generate an Application Password at:
    parentdata.org/wp-admin → Users → Your Profile → Application Passwords
"""

import os
import requests as _requests
from urllib.parse import urlparse

WP_BASE = 'https://parentdata.org/wp-json/wp/v2'
HEADERS = {'User-Agent': 'ParentData-StagingTool/1.0'}


def _wp_auth():
    """Return a (username, password) tuple if WP credentials are configured, else None."""
    username = os.environ.get('WP_APP_USERNAME', '').strip()
    password = os.environ.get('WP_APP_PASSWORD', '').strip()
    if username and password:
        return (username, password)
    return None


def fetch_wp_article(url: str) -> dict:
    """
    Fetch article data for a parentdata.org URL via the WP REST API.

    Returns:
        title, subtitle_lines (empty; Claude fills this from content),
        author_name, author_url, author_title (empty; user fills if needed),
        featured_image_url, featured_image_alt, topic_tags,
        content_html (raw WP block HTML for Claude to reformat),
        welcome_html (always ''), graph_count (always 0)
    """
    slug = _slug_from_url(url)
    if not slug:
        raise ValueError(f'Could not extract slug from URL: {url}')

    auth = _wp_auth()
    if not auth:
        raise ValueError(
            'WP_APP_USERNAME and WP_APP_PASSWORD are not set in .env. '
            'These are required to fetch full article content past the paywall. '
            'Generate an Application Password at: '
            'parentdata.org/wp-admin → Users → Your Profile → Application Passwords'
        )

    resp = _requests.get(
        f'{WP_BASE}/posts',
        params={
            'slug': slug,
            '_embed': 'wp:featuredmedia,wp:term,author',
            'status': 'publish',
        },
        headers=HEADERS,
        auth=auth,
        timeout=30,
    )
    resp.raise_for_status()
    posts = resp.json()
    if not posts:
        raise ValueError(
            f'No published post found for slug "{slug}". '
            f'Check that the URL is correct and the article is published.'
        )

    result = _parse_post(posts[0])

    # The subtitle is stored in a private WP meta field not exposed by the REST
    # API. Fetch the public article page and parse <p class="sub-title">.
    subtitle = _fetch_subtitle_from_page(url)
    if subtitle:
        result['excerpt_text'] = subtitle

    return result


def _slug_from_url(url: str) -> str:
    """Extract the slug (last non-empty path segment) from a URL."""
    path = urlparse(url).path.strip('/')
    parts = [p for p in path.split('/') if p]
    return parts[-1] if parts else ''


def _fetch_subtitle_from_page(url: str) -> str:
    """
    Fetch the public article page and extract the subtitle from
    <p class="sub-title">, which is rendered by the WP theme from a private
    meta field not exposed via the REST API.  Returns '' on any failure.
    """
    try:
        from bs4 import BeautifulSoup
        browser_headers = {
            'User-Agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            )
        }
        resp = _requests.get(url, headers=browser_headers, timeout=15)
        if resp.status_code != 200:
            return ''
        soup = BeautifulSoup(resp.text, 'html.parser')
        p = soup.find('p', class_='sub-title')
        return p.get_text(strip=True) if p else ''
    except Exception:
        return ''


def _parse_post(post: dict) -> dict:
    import re as _re
    title = post.get('title', {}).get('rendered', '')
    content_html = post.get('content', {}).get('rendered', '')
    embedded = post.get('_embedded', {})

    # Extract plain-text excerpt for use as subtitle
    excerpt_html = post.get('excerpt', {}).get('rendered', '')
    excerpt_text = _re.sub(r'<[^>]+>', '', excerpt_html).strip()

    # If the API returns a full HTML page instead of article content, it means
    # the post content is stored in a non-standard way (e.g. paywall HTML or
    # an imported full-page HTML blob). The tool cannot process this.
    if content_html.lstrip().startswith('<!DOCTYPE') or content_html.lstrip().startswith('<html'):
        raise ValueError(
            f'The WordPress API returned a full HTML page instead of article content for "{title}". '
            'This article may be stored in a non-standard format in WordPress. '
            'Please use the DOCX upload path instead.'
        )

    # Author
    author_name = ''
    author_url = ''
    authors = embedded.get('author', [])
    if authors and isinstance(authors[0], dict):
        a = authors[0]
        author_name = a.get('name', '')
        slug = a.get('slug', '')
        author_url = f'https://parentdata.org/author/{slug}/' if slug else ''

    # Featured image
    featured_image_url = ''
    featured_image_alt = ''
    media = embedded.get('wp:featuredmedia', [])
    if media and isinstance(media[0], dict):
        m = media[0]
        featured_image_url = m.get('source_url', '')
        featured_image_alt = m.get('alt_text', '') or title

    # Topic tags
    topic_tags = []
    for taxonomy in embedded.get('wp:term', []):
        for term in taxonomy:
            if isinstance(term, dict) and term.get('taxonomy') == 'post_tag':
                topic_tags.append(term.get('name', ''))

    return {
        'title': title,
        'excerpt_text': excerpt_text,  # Plain-text excerpt for use as subtitle
        'author_name': author_name,
        'author_url': author_url,
        'author_title': '',        # Not in WP API; user can fill in
        'featured_image_url': featured_image_url,
        'featured_image_alt': featured_image_alt,
        'topic_tags': topic_tags,
        'content_html': content_html,
        'welcome_html': '',
        'graph_count': 0,
    }
