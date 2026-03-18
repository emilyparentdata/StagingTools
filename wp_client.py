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

    html_out = '\n\n'.join(blocks)

    # Insert <p id="bottom-line"> anchor 3 paragraphs above the "Bottom Line" heading
    html_out = _insert_bottom_line_anchor_html(html_out)

    return html_out


def _insert_bottom_line_anchor_html(html: str) -> str:
    """Insert <p id="bottom-line"> 3 paragraphs above any heading containing
    'bottom line', searching the final HTML string directly."""
    # Find a heading (any level) containing "bottom line"
    heading_match = re.search(
        r'<!-- wp:heading -->.*?</h[1-6]>\s*<!-- /wp:heading -->',
        html, re.DOTALL | re.IGNORECASE,
    )
    # Filter to only the one that actually says "bottom line"
    bl_match = None
    for m in re.finditer(
        r'<!-- wp:heading -->.*?</h[1-6]>\s*<!-- /wp:heading -->',
        html, re.DOTALL,
    ):
        if re.search(r'bottom\s+line', m.group(), re.IGNORECASE):
            bl_match = m
            break

    if not bl_match:
        # Fallback: look for a bare <h2> without wp:heading comments
        bl_match = re.search(
            r'<h[1-6][^>]*>[^<]*bottom\s+line[^<]*</h[1-6]>',
            html, re.IGNORECASE,
        )

    if not bl_match:
        print('[wp_client] _insert_bottom_line_anchor: no bottom-line heading found')
        return html

    print(f'[wp_client] _insert_bottom_line_anchor: found heading at pos {bl_match.start()}')

    # Find the 3rd <p> tag before the heading, then back up to its
    # <!-- wp:paragraph --> wrapper so we insert before the whole block.
    text_before = html[:bl_match.start()]
    para_starts = [m.start() for m in re.finditer(r'<p[\s>]', text_before)]

    if len(para_starts) >= 3:
        p_pos = para_starts[-3]
        # Back up to the <!-- wp:paragraph --> comment that wraps this <p>
        wp_comment = text_before.rfind('<!-- wp:paragraph -->', 0, p_pos)
        insert_pos = wp_comment if wp_comment != -1 else p_pos
    elif para_starts:
        p_pos = para_starts[0]
        wp_comment = text_before.rfind('<!-- wp:paragraph -->', 0, p_pos)
        insert_pos = wp_comment if wp_comment != -1 else p_pos
    else:
        insert_pos = bl_match.start()

    anchor = (
        '\n\n<!-- wp:paragraph -->\n'
        '<p id="bottom-line"></p>\n'
        '<!-- /wp:paragraph -->\n\n'
    )
    return html[:insert_pos] + anchor + html[insert_pos:]


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

    The coauthors API searches by username (e.g. 'EOster'), not display
    name ('Emily Oster, PhD').  We try multiple search strategies:
    full name, last name, first name.
    """
    # Try full name first, then individual parts (the API matches usernames,
    # so "Emily Oster" won't match but "Oster" will match "EOster")
    queries = [name]
    parts = name.split()
    if len(parts) > 1:
        queries.append(parts[-1])   # last name
        queries.append(parts[0])    # first name

    all_results = {}
    for q in queries:
        resp = _session.get(
            f'{WP_API}/coauthors',
            params={'search': q, 'per_page': 10},
            auth=_wp_auth(),
            timeout=10,
        )
        if resp.ok:
            for author in resp.json():
                all_results[author['id']] = author
        if all_results:
            break  # stop as soon as we get results

    if not all_results:
        return None

    results = list(all_results.values())

    # Pick the entry with the most posts (most likely the active account)
    best = None
    for author in results:
        if best is None or author.get('count', 0) > best.get('count', 0):
            best = author
    return best['id'] if best else None


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
    resp = _session.post(f'{WP_API}/posts', json=payload, auth=_wp_auth(), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    post_id = data['id']

    # Set Rank Math SEO fields via the Rank Math API (the WP post meta
    # endpoint silently drops unregistered rank_math_* keys)
    rank_meta = {}
    if meta_description:
        rank_meta['rank_math_description'] = meta_description
    if focus_keyword:
        rank_meta['rank_math_focus_keyword'] = focus_keyword
    if rank_meta:
        _set_rank_math_meta(post_id, rank_meta)
    return {
        'id': post_id,
        'edit_url': f'{WP_SITE_URL}/wp-admin/post.php?post={post_id}&action=edit',
        'preview_url': data.get('link', f'{WP_SITE_URL}/?p={post_id}&preview=true'),
    }


def _set_rank_math_meta(post_id: int, meta: dict) -> None:
    """Set Rank Math SEO fields via the Rank Math REST API."""
    rank_math_api = f'{WP_SITE_URL}/wp-json/rankmath/v1/updateMeta'
    try:
        resp = _session.post(
            rank_math_api,
            json={'objectID': post_id, 'objectType': 'post', 'meta': meta},
            auth=_wp_auth(),
            timeout=10,
        )
        resp.raise_for_status()
        print(f'[wp_client] Rank Math meta set for post {post_id}: {list(meta.keys())}')
    except Exception as e:
        print(f'[wp_client] Warning: failed to set Rank Math meta: {e}')


def resolve_post_id(url: str) -> int | None:
    """Extract slug from a parentdata.org URL and look up the post ID."""
    path = urlparse(url).path.strip('/')
    slug = path.split('/')[-1] if path else ''
    if not slug:
        return None
    resp = _session.get(
        f'{WP_API}/posts',
        params={'slug': slug, 'per_page': 1},
        auth=_wp_auth(),
        timeout=15,
    )
    resp.raise_for_status()
    results = resp.json()
    if results:
        return results[0]['id']
    return None


def update_post(post_id: int, **fields) -> dict:
    """Update an existing WordPress post. Only non-empty fields are sent."""
    payload = {}
    field_map = {
        'title': 'title',
        'content': 'content',
        'excerpt': 'excerpt',
        'slug': 'slug',
        'featured_media': 'featured_media',
        'categories': 'categories',
        'post-topic': 'post-topic',
        'post-type': 'post-type',
        'coauthors': 'coauthors',
    }
    for key, wp_key in field_map.items():
        val = fields.get(key)
        if val:  # skip None, empty string, empty list, 0
            payload[wp_key] = val

    # Separate Rank Math fields from standard WP meta
    meta = fields.get('meta') or {}
    rank_meta = {}
    wp_meta = {}
    for k, v in meta.items():
        if k.startswith('rank_math_'):
            rank_meta[k] = v
        else:
            wp_meta[k] = v
    if wp_meta:
        payload['meta'] = wp_meta

    resp = _session.post(
        f'{WP_API}/posts/{post_id}',
        json=payload,
        auth=_wp_auth(),
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    if rank_meta:
        _set_rank_math_meta(post_id, rank_meta)

    return {
        'id': post_id,
        'edit_url': f'{WP_SITE_URL}/wp-admin/post.php?post={post_id}&action=edit',
        'preview_url': data.get('link', f'{WP_SITE_URL}/?p={post_id}&preview=true'),
    }


def _prepare_post_fields(fields: dict) -> dict:
    """Extract, convert, and resolve all common WordPress post fields.

    Returns a dict with: title, content, excerpt, slug, featured_media_id,
    category_ids, post_topic_ids, post_type_ids, coauthor_ids,
    meta_description, focus_keyword.
    """
    title = fields.get('title', '')
    body_html = fields.get('article_body_html', '')
    graphs = fields.get('inline_graphs', [])
    featured_url = fields.get('featured_image_url', '')
    featured_alt = fields.get('featured_image_alt', '')
    topic_tags = fields.get('topic_tags', [])
    age_groups = fields.get('age_groups', [])
    photo_credit = fields.get('photo_credit', '')
    author_name = fields.get('author_name', '')

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

    post_topic_ids = []
    for tag_name in topic_tags:
        tag_name = tag_name.strip()
        if not tag_name:
            continue
        try:
            post_topic_ids.append(find_or_create_post_topic(tag_name))
        except Exception as e:
            print(f'[wp_client] Warning: could not resolve post-topic "{tag_name}": {e}')

    category_ids = []
    for group in age_groups:
        group = group.strip()
        if not group:
            continue
        try:
            category_ids.append(find_or_create_category(group))
        except Exception as e:
            print(f'[wp_client] Warning: could not resolve category "{group}": {e}')

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

    # Power keywords from the DOCX override Claude-generated focus keyword
    power_keywords = fields.get('power_keywords', [])
    print(f'[wp_client] power_keywords={power_keywords}, coauthor_ids={coauthor_ids}')
    has_anchor = 'id="bottom-line"' in content
    print(f'[wp_client] bottom-line anchor in content: {has_anchor}')

    return {
        'title': title,
        'content': content,
        'wp_meta': wp_meta,
        'featured_media_id': featured_media_id,
        'category_ids': category_ids,
        'post_topic_ids': post_topic_ids,
        'post_type_ids': [WP_POST_TYPE_ARTICLE],
        'coauthor_ids': coauthor_ids,
        'power_keywords': power_keywords,
    }


def publish_or_update(fields: dict) -> dict:
    """Create a new draft or update an existing post based on original_url."""
    original_url = fields.get('original_url', '').strip()
    prepared = _prepare_post_fields(fields)
    wp_meta = prepared['wp_meta']

    if original_url:
        post_id = resolve_post_id(original_url)
        if not post_id:
            raise ValueError(f'Could not find post for URL: {original_url}')
        meta = {}
        if wp_meta.get('meta_description'):
            meta['rank_math_description'] = wp_meta['meta_description']
        # Power keywords from the doc override Claude-generated focus keyword
        power_kw = prepared.get('power_keywords', [])
        focus_kw = ', '.join(power_kw) if power_kw else wp_meta.get('focus_keyword', '')
        if focus_kw:
            meta['rank_math_focus_keyword'] = focus_kw
        return update_post(
            post_id,
            title=prepared['title'],
            content=prepared['content'],
            excerpt=wp_meta.get('excerpt', ''),
            featured_media=prepared['featured_media_id'],
            categories=prepared['category_ids'],
            **{'post-topic': prepared['post_topic_ids']},
            **{'post-type': prepared['post_type_ids']},
            coauthors=prepared['coauthor_ids'],
            meta=meta or None,
        )
    else:
        return _create_draft_from_prepared(prepared)


def publish_draft(fields: dict) -> dict:
    prepared = _prepare_post_fields(fields)
    return _create_draft_from_prepared(prepared)


def _create_draft_from_prepared(prepared: dict) -> dict:
    """Create a WordPress draft from a _prepare_post_fields result."""
    wp_meta = prepared['wp_meta']
    # Power keywords from the doc override Claude-generated focus keyword
    power_kw = prepared.get('power_keywords', [])
    focus_keyword = ', '.join(power_kw) if power_kw else wp_meta.get('focus_keyword', '')
    return create_draft(
        title=prepared['title'], content=prepared['content'],
        excerpt=wp_meta.get('excerpt', ''), slug=wp_meta.get('slug', ''),
        featured_media_id=prepared['featured_media_id'],
        category_ids=prepared['category_ids'],
        post_topic_ids=prepared['post_topic_ids'],
        post_type_ids=prepared['post_type_ids'],
        coauthor_ids=prepared['coauthor_ids'],
        meta_description=wp_meta.get('meta_description', ''),
        focus_keyword=focus_keyword,
    )
