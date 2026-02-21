"""
docx_parser.py — Extract raw text and structure from DOCX files.

Uses python-docx for paragraph-level inspection and mammoth for HTML conversion.
Returns a dict with raw text, mammoth HTML, detected metadata fields, and any
"Additional Information for Staging" section parsed into structured data.
"""

import re
import mammoth
from docx import Document


# Regex patterns for labeled metadata lines
LABEL_PATTERNS = {
    'title':           r'^title\s*:\s*(.+)$',
    'subtitle':        r'^subtitle\s*:\s*(.+)$',
    'author_name':     r'^author(?:\s+name)?\s*:\s*(.+)$',
    'author_title':    r'^author\s+title\s*:\s*(.+)$',
    'topic_tags':      r'^(?:topic\s+)?tags?\s*:\s*(.+)$',
    'power_keywords':  r'^power\s+keywords?\s*:\s*(.+)$',
}

# Detects the staging instructions heading
_STAGING_HEADING_RE = re.compile(
    r'additional\s+information\s+for\s+staging|staging\s+instructions?',
    re.I,
)


def parse_docx(file_path: str) -> dict:
    """
    Parse a DOCX file and return extracted content.

    Returns:
        {
            raw_text: str,
            mammoth_html: str,
            graph_count: int,
            detected_title: str,
            detected_subtitle: str,
            detected_author_name: str,
            detected_author_title: str,
            detected_topic_tags: list[str],
            detected_power_keywords: list[str],
            staging_instructions: {
                featured_image_url: str,
                featured_image_alt: str,
                related_articles: [{article_url, image_url, tagline}],
                graphs: [{url, label}],
            },
        }
    """
    doc = Document(file_path)

    # Find the staging instructions heading (must be a Heading-style paragraph)
    staging_start = None
    for i, para in enumerate(doc.paragraphs):
        if (_STAGING_HEADING_RE.search(para.text)
                and para.style.name.lower().startswith('heading')):
            staging_start = i
            break

    # Article content is everything before the staging section
    article_paras = (
        doc.paragraphs[:staging_start]
        if staging_start is not None
        else doc.paragraphs
    )

    # Raw text for Claude — article content only, staging section excluded
    raw_text = '\n'.join(p.text for p in article_paras)

    # Mammoth converts the full DOCX; we strip the staging section afterwards
    with open(file_path, 'rb') as f:
        mammoth_result = mammoth.convert_to_html(f)
    mammoth_html = mammoth_result.value

    if staging_start is not None:
        staging_heading = doc.paragraphs[staging_start].text
        mammoth_html = _strip_staging_from_html(mammoth_html, staging_heading)

    # Replace base64 embedded images with [[GRAPH_N]] placeholders
    mammoth_html, graph_count = _extract_graph_placeholders(mammoth_html)

    # Scan article paragraphs for labeled metadata fields
    detected = {
        'title': '', 'subtitle': '', 'author_name': '',
        'author_title': '', 'topic_tags': [], 'power_keywords': [],
    }
    for para in article_paras:
        text = para.text.strip()
        if not text:
            continue
        for field, pattern in LABEL_PATTERNS.items():
            m = re.match(pattern, text, re.IGNORECASE)
            if m:
                value = m.group(1).strip()
                if field in ('topic_tags', 'power_keywords'):
                    detected[field] = [t.strip() for t in value.split(',') if t.strip()]
                else:
                    detected[field] = value
                break

    # Parse the staging instructions section if present
    staging_instructions = (
        _parse_staging_instructions(doc.paragraphs[staging_start:])
        if staging_start is not None
        else {}
    )

    return {
        'raw_text': raw_text,
        'mammoth_html': mammoth_html,
        'graph_count': graph_count,
        'detected_title': detected['title'],
        'detected_subtitle': detected['subtitle'],
        'detected_author_name': detected['author_name'],
        'detected_author_title': detected['author_title'],
        'detected_topic_tags': detected['topic_tags'],
        'detected_power_keywords': detected['power_keywords'],
        'staging_instructions': staging_instructions,
    }


def _strip_staging_from_html(html: str, heading_text: str) -> str:
    """
    Remove the staging instructions section from mammoth HTML.

    Finds the heading text, walks back to the opening <h tag, and returns
    everything before it.  This avoids overly greedy regex matching across
    the whole document (mammoth also inserts <a id="…"> anchors inside
    heading elements, so a simple tag-match won't work).
    """
    idx = html.find(heading_text)
    if idx < 0:
        idx = html.lower().find(heading_text.lower())
    if idx < 0:
        return html
    # Walk back from the heading text to the opening <h tag
    h_start = html.rfind('<h', 0, idx)
    return html[:h_start] if h_start >= 0 else html[:idx]


def _parse_staging_instructions(paragraphs) -> dict:
    """
    Parse the 'Additional Information for Staging' section from DOCX paragraphs.

    Recognises these sub-sections (order and presence may vary):

      Featured Image
        Image: <url>        ← URL may be on this line or the next line alone
        Tag:   <alt text>

      Related Reading N:    ← handles typos like "Reaading"
        Link:  <article url>
        Image: <image url>
        Text:  <tagline>

      Graph N:
        Image: <image url>
        Tag:   <alt text>
    """
    result = {
        'featured_image_url': '',
        'featured_image_alt': '',
        'related_articles': [],
        'graphs': [],
    }

    # Collect non-empty lines, skipping the heading line itself
    lines = []
    for para in paragraphs:
        text = para.text.strip()
        if text and not _STAGING_HEADING_RE.search(text):
            lines.append(text)

    sections = []          # [(type_str, {key: value}), ...]
    current_type = None
    current_data = {}

    i = 0
    while i < len(lines):
        line = lines[i]

        # ── Section header detection ──────────────────────────────────────
        if re.match(r'featured\s+image\s*:?\s*$', line, re.I):
            if current_type:
                sections.append((current_type, dict(current_data)))
            current_type = 'featured'
            current_data = {}

        elif re.match(r'related\s+rea+ding\s+\d+\s*:?\s*$', line, re.I):
            if current_type:
                sections.append((current_type, dict(current_data)))
            current_type = 'related'
            current_data = {}

        elif re.match(r'graph\s+\d+\s*:?\s*$', line, re.I):
            if current_type:
                sections.append((current_type, dict(current_data)))
            current_type = 'graph'
            current_data = {}

        # ── Key: value pairs inside a section ────────────────────────────
        elif current_type is not None:
            m = re.match(r'^(\w+)\s*:\s*(.*)', line)
            if m:
                key = m.group(1).lower()
                val = m.group(2).strip()
                # If the value is empty, the next line may be a bare URL
                if (not val
                        and i + 1 < len(lines)
                        and re.match(r'https?://', lines[i + 1])):
                    i += 1
                    val = lines[i]
                current_data[key] = val

        i += 1

    # Flush the final section
    if current_type:
        sections.append((current_type, dict(current_data)))

    # Map parsed sections to the result structure
    for sec_type, data in sections:
        if sec_type == 'featured':
            result['featured_image_url'] = data.get('image', '').strip()
            result['featured_image_alt'] = data.get('tag', '').strip()
        elif sec_type == 'related':
            result['related_articles'].append({
                'article_url': data.get('link', '').strip(),
                'image_url':   data.get('image', '').strip(),
                'tagline':     data.get('text', '').strip(),
            })
        elif sec_type == 'graph':
            result['graphs'].append({
                'url':   data.get('image', '').strip(),
                'label': data.get('tag', '').strip(),
            })

    return result


def _extract_graph_placeholders(html: str) -> tuple:
    """
    Replace base64-encoded <img> tags in mammoth HTML with [[GRAPH_N]] markers.
    Returns (cleaned_html, count).
    """
    count = [0]

    def replacer(m):
        count[0] += 1
        return f'[[GRAPH_{count[0]}]]'

    cleaned = re.sub(
        r'<img\b[^>]*\bsrc="data:image/[^"]*"[^>]*>',
        replacer,
        html,
        flags=re.IGNORECASE,
    )
    return cleaned, count[0]
