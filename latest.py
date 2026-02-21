"""
app.py — Flask web application for the ParentData email staging tool.

Routes:
    GET  /                 — Serve the single-page UI
    POST /upload           — Accept DOCX, run parser + Claude extraction, return JSON
    GET  /articles         — Accept topic tags, return related article suggestions
    POST /refresh-articles — Force re-fetch of the full article index
    POST /generate         — Accept all fields, build final HTML, return it
"""

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

TEMPLATE_PATH = Path(__file__).parent / 'email_templates' / 'latest_template.html'


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    """Accept a DOCX file upload or a Google Doc URL; return extracted JSON fields."""
    google_doc_url = request.form.get('google_doc_url', '').strip()
    has_file = 'file' in request.files and request.files['file'].filename

    if not google_doc_url and not has_file:
        return jsonify({'error': 'Provide a .docx file or a Google Doc link'}), 400

    tmp_fd, tmp_path = tempfile.mkstemp(suffix='.docx')
    try:
        os.close(tmp_fd)

        if google_doc_url:
            # Download DOCX export from Google Docs
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

        return jsonify(_process_docx(tmp_path))

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _process_docx(tmp_path: str) -> dict:
    """Parse the DOCX at tmp_path and return the full response dict."""
    from docx_parser import parse_docx
    from claude_client import extract_fields

    parsed = parse_docx(tmp_path)
    fields = extract_fields(parsed['raw_text'], parsed['mammoth_html'])

    # Claude's output takes priority; fall back to parser-detected values
    response_data = {
        'title': fields.get('title') or parsed['detected_title'],
        'subtitle_lines': fields.get('subtitle_lines') or (
            [parsed['detected_subtitle']] if parsed['detected_subtitle'] else []
        ),
        'author_name': fields.get('author_name') or parsed['detected_author_name'],
        'author_title': fields.get('author_title') or parsed['detected_author_title'],
        'topic_tags': fields.get('topic_tags') or parsed['detected_topic_tags'],
        'welcome_html': fields.get('welcome_html', ''),
        'article_body_html': fields.get('article_body_html', ''),
        'graph_count': parsed.get('graph_count', 0),
        'author_url': 'https://parentdata.org/author/eoster/',
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

    try:
        from html_builder import build_email_html
        html = build_email_html(str(TEMPLATE_PATH), data)
        return Response(
            html,
            mimetype='text/html; charset=utf-8',
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, port=port)
