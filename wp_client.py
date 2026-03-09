"""
wp_client.py — Convert email-styled HTML to WordPress Gutenberg block HTML.

Also includes WordPress REST API helpers for future direct-publish support
(currently blocked by Cloudflare WAF on parentdata.org).
"""

import os
import re
from pathlib import PurePosixPath
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, NavigableString

# ── Config ────────────────────────────────────────────────────────────────────

WP_SITE_URL = os.environ.get('WP_SITE_URL', 'https://parentdata.org').rstrip('/')
WP_API = f'{WP_SITE_URL}/wp-json/wp/v2'
WP_UA = 'Mozilla/5.0 (compatible; ParentData-StagingTool/1.0)'

# Reusable block ID for the subscribe/upgrade CTA
WP_CTA_BLOCK_REF = 17914

# "Post Type" taxonomy term ID for "Article" (slug: data-dive)
WP_POST_TYPE_ARTICLE = 151

# Shared session with User-Agent header (Cloudflare blocks default python-requests UA)
_session = requests.Session()
_session.headers['User-Agent'] = WP_UA


def _wp_auth() -> tuple:
    return (
        os.environ.get('WP_APP_USERNAME', ''),
        os.environ.get('WP_APP_PASSWORD', ''),
    )


# ── Gutenberg block conversion ───────────────────────────────────────────────

def strip_email_styles(
    html: str,
    graphs: list | None = None,
    featured_image_url: str = '',
    photo_credit: str = '',
) -> str:
    """Convert email-styled HTML to WordPress Gutenberg block HTML.

    Produces output with proper <!-- wp:type --> block comments matching
    the format used in parentdata.org posts.  The featured image (with
    photo credit caption) is inserted after the CTA reusable block.
    """
    if not html or not html.strip():
        return ''

    # Replace graph placeholders with standalone image blocks before parsing.
    # Close any open <p> tag, insert the image, then reopen <p> to handle
    # the rare case where a placeholder sits inside a paragraph.
    if graphs:
        for i, g in enumerate(graphs, 1):
            url = g.get('url', '')
            alt = g.get('alt', g.get('label', ''))
            if url:
                img_block = (
                    f'</p>\n'
                    f'<div class="wp-graph-placeholder" data-src="{url}" data-alt="{alt}"></div>\n'
                    f'<p>'
                )
                html = html.replace(f'[[GRAPH_{i}]]', img_block)

    soup = BeautifulSoup(html, 'html.parser')

    # Clean all tags: strip style/class, unwrap spans inside links
    for tag in soup.find_all(True):
        tag.attrs = {
            k: v for k, v in tag.attrs.items()
            if k in ('href', 'src', 'alt', 'target', 'rel', 'id',
                     'data-src', 'data-alt')
        }

    for a_tag in soup.find_all('a'):
        for span in a_tag.find_all('span'):
            span.unwrap()

    # Build block output from top-level elements
    blocks = []
    # Track whether we've inserted the CTA block (after intro, before first heading)
    cta_inserted = False

    for el in list(soup.children):
        if isinstance(el, NavigableString):
            text = str(el).strip()
            if text:
                blocks.append(f'<!-- wp:paragraph -->\n<p>{text}</p>\n<!-- /wp:paragraph -->')
            continue

        if el.name in ('h1', 'h2', 'h3', 'h4'):
            # Insert CTA + featured image before first heading if not done yet
            if not cta_inserted:
                blocks.append(f'<!-- wp:block {{"ref":{WP_CTA_BLOCK_REF}}} /-->')
                if featured_image_url:
                    blocks.append(_make_image_block(
                        featured_image_url, '', photo_credit))
                cta_inserted = True
            level = el.name  # h2, h3, etc.
            inner = _inner_html(el)
            blocks.append(
                f'<!-- wp:heading -->\n'
                f'<{level} class="wp-block-heading">{inner}</{level}>\n'
                f'<!-- /wp:heading -->'
            )

        elif el.name == 'p':
            inner = _inner_html(el)
            if inner.strip():
                blocks.append(
                    f'<!-- wp:paragraph -->\n'
                    f'<p>{inner}</p>\n'
                    f'<!-- /wp:paragraph -->'
                )

        elif el.name in ('ul', 'ol'):
            tag = el.name
            items = []
            for li in el.find_all('li', recursive=False):
                li_inner = _inner_html(li)
                items.append(
                    f'<!-- wp:list-item -->\n'
                    f'<li>{li_inner}</li>\n'
                    f'<!-- /wp:list-item -->'
                )
            items_str = '\n'.join(items)
            blocks.append(
                f'<!-- wp:list -->\n'
                f'<{tag} class="wp-block-list">{items_str}</{tag}>\n'
                f'<!-- /wp:list -->'
            )

        elif el.name == 'img':
            blocks.append(_make_image_block(el.get('src', ''), el.get('alt', '')))

        elif el.name in ('div', 'figure'):
            # Image wrapper or graph placeholder
            if el.get('data-src'):
                # Graph placeholder
                blocks.append(_make_image_block(el['data-src'], el.get('data-alt', '')))
            else:
                img = el.find('img')
                if img:
                    blocks.append(_make_image_block(img.get('src', ''), img.get('alt', '')))
                else:
                    # Generic div with text content
                    text = el.get_text(strip=True)
                    if text:
                        blocks.append(
                            f'<!-- wp:paragraph -->\n'
                            f'<p>{_inner_html(el)}</p>\n'
                            f'<!-- /wp:paragraph -->'
                        )

        elif el.name == 'blockquote':
            inner = _inner_html(el)
            blocks.append(
                f'<!-- wp:quote -->\n'
                f'<blockquote class="wp-block-quote">{inner}</blockquote>\n'
                f'<!-- /wp:quote -->'
            )

        elif el.name == 'hr':
            blocks.append('<!-- wp:separator -->\n<hr class="wp-block-separator"/>\n<!-- /wp:separator -->')

    # If no headings were found, insert CTA + image at the end
    if not cta_inserted:
        blocks.append(f'<!-- wp:block {{"ref":{WP_CTA_BLOCK_REF}}} /-->')
        if featured_image_url:
            blocks.append(_make_image_block(
                featured_image_url, '', photo_credit))

    return '\n\n'.join(blocks)


def _inner_html(tag) -> str:
    """Get the inner HTML of a tag (its children as a string)."""
    return ''.join(str(c) for c in tag.children)


def _make_image_block(src: str, alt: str = '', caption: str = '') -> str:
    """Build a wp:image Gutenberg block."""
    attrs = '{"sizeSlug":"full","linkDestination":"none","align":"center"}'
    caption_html = f'<figcaption class="wp-element-caption">{caption}</figcaption>' if caption else ''
    return (
        f'<!-- wp:image {attrs} -->\n'
        f'<figure class="wp-block-image aligncenter size-full">'
        f'<img src="{src}" alt="{alt}"/>'
        f'{caption_html}'
        f'</figure>\n'
        f'<!-- /wp:image -->'
    )


# ── Media upload (for future API integration) ────────────────────────────────

_MIME_MAP = {
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
    '.png': 'image/png', '.gif': 'image/gif',
    '.webp': 'image/webp', '.svg': 'image/svg+xml',
}


def _find_media_by_filename(filename: str) -> int | None:
    resp = _session.get(
        f'{WP_API}/media',
        params={'search': filename, 'per_page': 5},
        auth=_wp_auth(),
        timeout=15,
    )
    if resp.ok:
        for item in resp.json():
            if filename in item.get('source_url', ''):
                return item['id']
    return None


def upload_media(image_url: str, alt_text: str = '') -> int:
    parsed = urlparse(image_url)
    filename = PurePosixPath(parsed.path).name or 'image.jpg'
    ext = PurePosixPath(filename).suffix.lower()
    content_type = _MIME_MAP.get(ext, 'image/jpeg')

    if WP_SITE_URL.replace('https://', '').replace('http://', '') in image_url:
        existing = _find_media_by_filename(filename)
        if existing:
            return existing

    img_resp = _session.get(image_url, timeout=30)
    img_resp.raise_for_status()

    resp = _session.post(
        f'{WP_API}/media',
        headers={
            'Content-Type': content_type,
            'Content-Disposition': f'attachment; filename="{filename}"',
        },
        data=img_resp.content,
        auth=_wp_auth(),
        timeout=30,
    )
    resp.raise_for_status()
    media_id = resp.json()['id']

    if alt_text:
        _session.post(
            f'{WP_API}/media/{media_id}',
            json={'alt_text': alt_text},
            auth=_wp_auth(),
            timeout=10,
        )
    return media_id


# ── Categories & tags (for future API integration) ───────────────────────────

def find_or_create_category(name: str) -> int:
    # Try slug-based lookup first (more reliable than search)
    slug = name.lower().replace(' ', '-')
    resp = _session.get(
        f'{WP_API}/categories',
        params={'slug': slug, 'per_page': 5},
        auth=_wp_auth(),
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json()
    if results:
        return results[0]['id']

    # Fall back to search
    resp = _session.get(
        f'{WP_API}/categories',
        params={'search': name, 'per_page': 10},
        auth=_wp_auth(),
        timeout=10,
    )
    resp.raise_for_status()
    for cat in resp.json():
        if cat['name'].lower() == name.lower():
            return cat['id']
    resp = _session.post(
        f'{WP_API}/categories',
        json={'name': name},
        auth=_wp_auth(),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()['id']


def find_or_create_post_topic(name: str) -> int:
    """Find or create a term in the 'post-topic' custom taxonomy."""
    resp = _session.get(
        f'{WP_API}/post-topic',
        params={'search': name, 'per_page': 10},
        auth=_wp_auth(),
        timeout=10,
    )
    resp.raise_for_status()
    for topic in resp.json():
        if topic['name'].lower() == name.lower():
            return topic['id']
    resp = _session.post(
        f'{WP_API}/post-topic',
        json={'name': name},
        auth=_wp_auth(),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()['id']


def find_coauthor(name: str) -> int | None:
    """Look up a Co-Authors Plus author by display name or username.

    The coauthors API 'name' field is a username (e.g. 'EOster'), not
    the display name ('Emily Oster, PhD').  We search and match loosely.
    """
    resp = _session.get(
        f'{WP_API}/coauthors',
        params={'search': name, 'per_page': 10},
        auth=_wp_auth(),
        timeout=10,
    )
    if resp.ok:
        results = resp.json()
        # Pick the entry with the most posts (most likely the active one)
        best = None
        for author in results:
            if best is None or author.get('count', 0) > best.get('count', 0):
                best = author
        if best:
            return best['id']
    return None


# ── Draft creation (for future API integration) ──────────────────────────────

def create_draft(
    title, content, excerpt='', slug='', featured_media_id=0,
    category_ids=None, post_topic_ids=None, post_type_ids=None,
    coauthor_ids=None, meta_description='', focus_keyword='',
):
    payload = {'title': title, 'content': content, 'status': 'draft'}
    if excerpt:
        payload['excerpt'] = excerpt
    if slug:
        payload['slug'] = slug
    if featured_media_id:
        payload['featured_media'] = featured_media_id
    if category_ids:
        payload['categories'] = category_ids
    if post_topic_ids:
        payload['post-topic'] = post_topic_ids
    if post_type_ids:
        payload['post-type'] = post_type_ids
    if coauthor_ids:
        payload['coauthors'] = coauthor_ids
    meta = {}
    if meta_description:
        meta['rank_math_description'] = meta_description
    if focus_keyword:
        meta['rank_math_focus_keyword'] = focus_keyword
    if meta:
        payload['meta'] = meta

    resp = _session.post(f'{WP_API}/posts', json=payload, auth=_wp_auth(), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    post_id = data['id']
    return {
        'id': post_id,
        'edit_url': f'{WP_SITE_URL}/wp-admin/post.php?post={post_id}&action=edit',
        'preview_url': data.get('link', f'{WP_SITE_URL}/?p={post_id}&preview=true'),
    }


def publish_draft(fields: dict) -> dict:
    title = fields.get('title', '')
    body_html = fields.get('article_body_html', '')
    graphs = fields.get('inline_graphs', [])
    featured_url = fields.get('featured_image_url', '')
    featured_alt = fields.get('featured_image_alt', '')
    topic_tags = fields.get('topic_tags', [])
    age_groups = fields.get('age_groups', [])
    photo_credit = fields.get('photo_credit', '')

    content = strip_email_styles(
        body_html, graphs,
        featured_image_url=featured_url,
        photo_credit=photo_credit,
    )
    if not content.strip():
        raise ValueError('No article body to publish')

    from claude_client import generate_wp_meta
    raw_text = BeautifulSoup(body_html, 'html.parser').get_text(' ', strip=True)
    wp_meta = generate_wp_meta(raw_text, title)

    featured_media_id = 0
    if featured_url:
        try:
            featured_media_id = upload_media(featured_url, featured_alt)
        except Exception:
            pass

    # Topic tags → post-topic taxonomy
    post_topic_ids = []
    for tag_name in topic_tags:
        tag_name = tag_name.strip()
        if not tag_name:
            continue
        try:
            post_topic_ids.append(find_or_create_post_topic(tag_name))
        except Exception as e:
            print(f'[wp_client] Warning: could not resolve post-topic "{tag_name}": {e}')

    # Age groups → categories
    category_ids = []
    for group in age_groups:
        group = group.strip()
        if not group:
            continue
        try:
            category_ids.append(find_or_create_category(group))
        except Exception as e:
            print(f'[wp_client] Warning: could not resolve category "{group}": {e}')

    # Post type → "Article" (term 151 in post-type taxonomy)
    post_type_ids = [WP_POST_TYPE_ARTICLE]

    # Author — look up via Co-Authors Plus taxonomy
    author_name = fields.get('author_name', '')
    coauthor_ids = []
    if author_name:
        try:
            cid = find_coauthor(author_name)
            if cid:
                coauthor_ids.append(cid)
            else:
                print(f'[wp_client] Warning: coauthor not found for "{author_name}"')
        except Exception as e:
            print(f'[wp_client] Warning: coauthor lookup failed for "{author_name}": {e}')

    return create_draft(
        title=title, content=content,
        excerpt=wp_meta.get('excerpt', ''), slug=wp_meta.get('slug', ''),
        featured_media_id=featured_media_id,
        category_ids=category_ids, post_topic_ids=post_topic_ids,
        post_type_ids=post_type_ids, coauthor_ids=coauthor_ids,
        meta_description=wp_meta.get('meta_description', ''),
        focus_keyword=wp_meta.get('focus_keyword', ''),
    )
