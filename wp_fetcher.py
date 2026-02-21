"""
wp_fetcher.py — Fetch a published ParentData article from the WordPress REST API.

Returns article metadata + raw content HTML for Claude to reformat.
"""

import requests as _requests
from urllib.parse import urlparse

WP_BASE = 'https://parentdata.org/wp-json/wp/v2'
HEADERS = {'User-Agent': 'ParentData-StagingTool/1.0'}


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

    resp = _requests.get(
        f'{WP_BASE}/posts',
        params={
            'slug': slug,
            '_embed': 'wp:featuredmedia,wp:term,author',
            'status': 'publish',
        },
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    posts = resp.json()
    if not posts:
        raise ValueError(
            f'No published post found for slug "{slug}". '
            f'Check that the URL is correct and the article is publicly published.'
        )

    return _parse_post(posts[0])


def _slug_from_url(url: str) -> str:
    """Extract the slug (last non-empty path segment) from a URL."""
    path = urlparse(url).path.strip('/')
    parts = [p for p in path.split('/') if p]
    return parts[-1] if parts else ''


def _parse_post(post: dict) -> dict:
    title = post.get('title', {}).get('rendered', '')
    content_html = post.get('content', {}).get('rendered', '')
    embedded = post.get('_embedded', {})

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
        'subtitle_lines': [],      # Claude extracts from content
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
