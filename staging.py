"""
app.py — Flask web application for the ParentData email staging tool.

Routes:
    GET  /                 — Serve the single-page UI
    POST /upload           — Accept DOCX/Google Doc/WP URL, run extraction, return JSON
    GET  /articles         — Accept topic tags, return related article suggestions
    POST /refresh-articles — Force re-fetch of the full article index
    POST /generate         — Accept all fields, build final HTML, return it
"""

import csv
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests as _requests
from flask import Flask, render_template, request, jsonify, Response
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB

BASE_DIR = Path(__file__).parent

TEMPLATES = {
    'standard': {
        'label': 'Standard newsletter article',
        'file': BASE_DIR / 'email_templates' / 'latest_template.html',
        'has_welcome': True,
        'has_author_block': True,
        'has_related_reading': True,
        'has_bottom_line': False,
    },
    'fertility': {
        'label': 'Fertility article',
        'file': BASE_DIR / 'email_templates' / 'template_fertilityarticle.html',
        'has_welcome': False,
        'has_author_block': False,
        'has_related_reading': False,
        'has_bottom_line': True,
    },
    'qa': {
        'label': 'Fertility Q&A',
        'file': BASE_DIR / 'email_templates' / 'template_fertilityqa.html',
        'has_welcome': False,
        'has_author_block': False,
        'has_related_reading': False,
        'has_bottom_line': False,
    },
    'marketing': {
        'label': 'Marketing article',
        'file': BASE_DIR / 'email_templates' / 'template_marketing.html',
        'has_welcome': False,
        'has_author_block': True,
        'has_related_reading': False,
        'has_bottom_line': False,
    },
    'fertility_digest': {
        'label': 'Fertility Digest',
        'file': BASE_DIR / 'email_templates' / 'template_fertilitydigest.html',
        'has_welcome': False,
        'has_author_block': False,
        'has_related_reading': False,
        'has_bottom_line': False,
    },
}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/marketing-config')
def marketing_config():
    """Return intro text options from the marketing assets CSV."""
    csv_path = BASE_DIR / 'marketing_assets' / 'article_intro_text_options.csv'
    intro_options = []
    try:
        with open(csv_path, encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get('Name', '').strip()
                text = row.get('Intro Text', '').strip()
                if name and text:
                    intro_options.append({'name': name, 'text': text})
    except Exception:
        pass
    return jsonify({'intro_options': intro_options})


@app.route('/upload', methods=['POST'])
def upload():
    """Accept a DOCX file, Google Doc URL, or WordPress article URL; return extracted JSON fields."""
    template_type = request.form.get('template_type', 'standard')
    if template_type not in TEMPLATES:
        template_type = 'standard'

    wordpress_url = request.form.get('wordpress_url', '').strip()
    google_doc_url = request.form.get('google_doc_url', '').strip()
    has_file = 'file' in request.files and request.files['file'].filename
    wp_url_1 = request.form.get('wp_url_1', '').strip()
    wp_url_2 = request.form.get('wp_url_2', '').strip()

    if not wordpress_url and not google_doc_url and not has_file and not (wp_url_1 and wp_url_2):
        return jsonify({'error': 'Provide a .docx file, a Google Doc link, or a ParentData article URL'}), 400

    # ── Q&A: two WordPress URLs ──────────────────────────────────────────────
    if template_type == 'qa' and wp_url_1 and wp_url_2:
        try:
            from wp_fetcher import fetch_wp_article
            from claude_client import extract_qa_content

            article1 = fetch_wp_article(wp_url_1)
            article2 = fetch_wp_article(wp_url_2)

            qa1 = extract_qa_content(article1['content_html'])
            qa2 = extract_qa_content(article2['content_html'])

            # Build author attribution list (deduplicated, credentials stripped)
            author1 = _strip_name_credentials(article1.get('author_name', ''))
            author2 = _strip_name_credentials(article2.get('author_name', ''))
            qa_authors = list(dict.fromkeys(a for a in [author1, author2] if a))

            return jsonify({
                'qa1': qa1,
                'qa2': qa2,
                'qa_authors': qa_authors,
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # ── Single WordPress article URL path ────────────────────────────────────
    if wordpress_url:
        try:
            from wp_fetcher import fetch_wp_article
            from claude_client import reformat_wp_content

            article = fetch_wp_article(wordpress_url)
            content_html = _strip_featured_image(
                article['content_html'],
                article.get('featured_image_url', ''),
            )
            reformatted = reformat_wp_content(content_html, template_type)

            # Use WP excerpt as subtitle; fall back to Claude-generated if absent
            excerpt_text = article.get('excerpt_text', '')
            subtitle_lines = (
                [excerpt_text] if excerpt_text
                else reformatted.get('subtitle_lines', [])
            )

            response_data = {
                'title':               article.get('title', ''),
                'subtitle_lines':      subtitle_lines,
                'author_name':         article.get('author_name', ''),
                'author_url':          article.get('author_url', 'https://parentdata.org/author/eoster/'),
                'author_title':        article.get('author_title', ''),
                'topic_tags':          article.get('topic_tags', []),
                'featured_image_url':  article.get('featured_image_url', ''),
                'featured_image_alt':  article.get('featured_image_alt', ''),
                'welcome_html':        '',
                'article_body_html':   reformatted.get('article_body_html', ''),
                'bottom_line_html':    reformatted.get('bottom_line_html', ''),
                'graph_count':         0,
                'article_url':         wordpress_url,
            }
            return jsonify(response_data)

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    # ── DOCX / Google Doc path ───────────────────────────────────────────────
    tmp_fd, tmp_path = tempfile.mkstemp(suffix='.docx')
    try:
        os.close(tmp_fd)

        if google_doc_url:
            m = re.search(r'/d/([a-zA-Z0-9_-]+)', google_doc_url)
            if not m:
                return jsonify({'error': 'Could not parse Google Doc ID from URL'}), 400
            export_url = (
                f'https://docs.google.com/document/d/{m.group(1)}/export?format=docx'
            )
            try:
                resp = _requests.get(export_url, timeout=30)
                resp.raise_for_status()
            except Exception as e:
                return jsonify({
                    'error': f'Could not download Google Doc (is it shared publicly?): {e}'
                }), 400
            with open(tmp_path, 'wb') as f:
                f.write(resp.content)
        else:
            file = request.files['file']
            if not file.filename.lower().endswith('.docx'):
                return jsonify({'error': 'File must be a .docx file'}), 400
            file.save(tmp_path)

        return jsonify(_process_docx(tmp_path, template_type))

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _process_docx(tmp_path: str, template_type: str = 'standard') -> dict:
    """Parse the DOCX at tmp_path and return the full response dict."""
    from docx_parser import parse_docx

    parsed = parse_docx(tmp_path)

    if template_type == 'fertility_digest':
        from docx_parser import parse_digest_docx
        from wp_fetcher import fetch_article_image

        digest = parse_digest_docx(tmp_path)
        articles = digest.get('articles', [])

        # Fetch featured image for each article (fails gracefully per article)
        for article in articles:
            img = {'image_url': '', 'image_alt': ''}
            if article.get('url'):
                try:
                    img = fetch_article_image(article['url'])
                except Exception:
                    pass
            article['image_url'] = img.get('image_url', '')
            article['image_alt'] = img.get('image_alt', '') or article.get('title', '')

        return {
            'title':      digest.get('title', ''),
            'intro_text': digest.get('intro_text', ''),
            'articles':   articles,
        }

    from claude_client import extract_fields
    fields = extract_fields(parsed['raw_text'], parsed['mammoth_html'], template_type)

    # Claude's output takes priority; fall back to parser-detected values
    response_data = {
        'title':           fields.get('title') or parsed['detected_title'],
        'subtitle_lines':  fields.get('subtitle_lines') or (
            [parsed['detected_subtitle']] if parsed['detected_subtitle'] else []
        ),
        'author_name':     fields.get('author_name') or parsed['detected_author_name'],
        'author_title':    fields.get('author_title') or parsed['detected_author_title'],
        'topic_tags':      fields.get('topic_tags') or parsed['detected_topic_tags'],
        'welcome_html':    fields.get('welcome_html', ''),
        'article_body_html': fields.get('article_body_html', ''),
        'bottom_line_html':  fields.get('bottom_line_html', ''),
        'graph_count':     parsed.get('graph_count', 0),
        'author_url':      'https://parentdata.org/author/eoster/',
    }

    staging = parsed.get('staging_instructions', {})
    if staging:
        _apply_staging_instructions(response_data, staging)

    return response_data


def _apply_staging_instructions(data: dict, staging: dict) -> None:
    """
    Merge parsed staging instructions into the upload response dict in-place.

    Populates: featured_image_url, featured_image_alt, related_articles,
    and inline_graphs (pre-fill values; count still comes from the DOCX).
    """
    from article_fetcher import find_article_by_url

    # Featured image — alt text from the staging section's Tag field
    if staging.get('featured_image_url'):
        data['featured_image_url'] = staging['featured_image_url']
        data['featured_image_alt'] = staging.get('featured_image_alt', '') or data.get('title', '')

    # Related articles — title looked up from the cached article index;
    # tagline comes directly from the staging instructions Text field.
    related = []
    for ra in staging.get('related_articles', []):
        article_url = ra.get('article_url', '')
        found = find_article_by_url(article_url)
        title = found['title'] if found else _title_from_slug(article_url)
        related.append({
            'title':       title,
            'url':         article_url,
            'image_url':   ra.get('image_url', ''),
            'image_alt':   title,
            'description': ra.get('tagline', ''),
        })
    if related:
        data['related_articles'] = related

    # Inline graphs — clip to graph_count so we only pre-fill slots that exist
    graph_count = data.get('graph_count', 0)
    graphs = [
        {'url': g.get('url', ''), 'alt': g.get('label', '')}
        for g in staging.get('graphs', [])[:graph_count]
    ]
    if graphs:
        data['inline_graphs'] = graphs


def _strip_featured_image(content_html: str, featured_image_url: str) -> str:
    """
    Remove any <figure> blocks from content_html that reference the featured image.

    WordPress often embeds the featured image both as the post's featured_media
    AND as the first block in the article content, which would cause it to appear
    twice in the email. This strips the duplicate before Claude sees the content.

    Matches by base filename so resized variants (e.g. -800x600) are also caught.
    """
    if not featured_image_url or not content_html:
        return content_html

    # Derive base name: "pregnancy-test-800x600.jpg" → "pregnancy-test"
    filename = featured_image_url.rstrip('/').rsplit('/', 1)[-1]
    base = re.sub(r'-\d+x\d+(\.[a-z0-9]+)$', r'\1', filename, flags=re.I)
    stem = re.sub(r'\.[a-z0-9]+$', '', base, flags=re.I)
    if not stem:
        return content_html

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(content_html, 'html.parser')
    for figure in soup.find_all('figure'):
        img = figure.find('img')
        if img:
            src = img.get('src', '') + ' ' + img.get('srcset', '')
            if stem in src:
                figure.decompose()
    return str(soup)


def _strip_name_credentials(name: str) -> str:
    """Return just the person's name, removing title prefixes and credential suffixes."""
    # Strip prefixes: Dr., Prof., Mr., Ms., etc.
    name = re.sub(r'^(Dr|Prof|Professor|Mr|Ms|Mrs|Mx)\.?\s+', '', name, flags=re.IGNORECASE).strip()
    # Strip suffixes after a comma: ", MD", ", PhD", ", OB-GYN", etc.
    name = re.sub(r'\s*,.*$', '', name).strip()
    return name


def _title_from_slug(url: str) -> str:
    """Derive a readable title from a URL slug as a fallback."""
    path = urlparse(url).path.strip('/')
    slug = path.split('/')[-1] if path else ''
    return slug.replace('-', ' ').title()


@app.route('/articles')
def articles():
    """Return related article suggestions from the full ParentData article index."""
    tags = request.args.getlist('tags')
    keywords = request.args.getlist('keywords')

    from article_fetcher import fetch_related_articles, cache_info
    suggestions = fetch_related_articles(topic_tags=tags, keywords=keywords)
    info = cache_info()
    return jsonify({'suggestions': suggestions, 'cache': info})


@app.route('/refresh-articles', methods=['POST'])
def refresh_articles():
    """Force a full re-fetch of the article index from the WordPress API."""
    from article_fetcher import refresh_cache
    result = refresh_cache()
    return jsonify(result)


@app.route('/generate', methods=['POST'])
def generate():
    """Accept all fields, build the email HTML, and return it."""
    data = request.get_json(force=True)
    if not data:
        return jsonify({'error': 'No JSON body received'}), 400

    template_type = data.get('template_type', 'standard')
    if template_type not in TEMPLATES:
        template_type = 'standard'

    template_config = TEMPLATES[template_type]
    template_path = str(template_config['file'])

    try:
        from html_builder import build_email_html
        html = build_email_html(template_path, data, template_type)
        return Response(
            html,
            mimetype='text/html; charset=utf-8',
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, port=port)
