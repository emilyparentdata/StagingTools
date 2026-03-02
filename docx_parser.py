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


def parse_digest_docx(file_path: str) -> dict:
    """
    Parse a fertility digest DOCX (exported from Google Doc).

    Expected document structure:
      Subject line: <email title>
      Preheader: <preheader>   (skipped)
      <intro paragraph(s)>
      <Article title>          (bold run)
      <Article description>
      BUTTON: Read more        (paragraph with hyperlink — any hyperlink text)
      ... (repeat for up to 5 articles)

    Returns:
        {
            title:      str,
            intro_text: str,
            articles:   [{title, url, description}] × up to 5
        }
    """
    from docx.oxml.ns import qn as _qn

    doc = Document(file_path)

    email_title = ''
    intro_lines = []
    articles = []
    current_article = None
    seen_first_bold = False

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # "Subject line: …" → email title
        m = re.match(r'^Subject\s+line\s*:\s*(.+)$', text, re.I)
        if m:
            email_title = m.group(1).strip()
            continue

        # "Preheader: …" → skip
        if re.match(r'^Preheader\s*:', text, re.I):
            continue

        # "BUTTON: …" → CTA paragraph; extract hyperlink URL
        if re.match(r'^BUTTON\s*:', text, re.I):
            url = _get_hyperlink_url(para, doc, _qn)
            if current_article is not None:
                current_article['url'] = url
                articles.append(current_article)
                current_article = None
            continue

        # Bold paragraph → new article title
        if _is_bold_para(para):
            seen_first_bold = True
            current_article = {'title': text, 'description': '', 'url': ''}
            continue

        # Plain text
        if current_article is not None:
            # First plain line after the title is the description
            if not current_article['description']:
                current_article['description'] = text
        elif not seen_first_bold:
            # We're before the first article — collect as intro
            intro_lines.append(text)

    # Flush any incomplete trailing article
    if current_article is not None:
        articles.append(current_article)

    return {
        'title':      email_title,
        'intro_text': ' '.join(intro_lines),
        'articles':   articles[:5],
    }


def parse_paid_digest_docx(file_path: str) -> dict:
    """
    Parse a paid digest DOCX (exported from Google Doc).

    Supports two formats:

    Format A — section name and URL on the same line:
      Popular this week 1: https://parentdata.org/…
      Popular this week 2: https://parentdata.org/…
      Pregnancy: https://parentdata.org/…

    Format B — section name and URL on separate lines:
      Popular this week
      https://parentdata.org/…
      Pregnancy
      https://parentdata.org/…

    Headings like "Popular this week 1" and "Popular this week 2" are
    normalised into a single section with 2 articles.

    Returns:
        {
            sections: [
                {name: str, articles: [{url: str}]},
                ...
            ]
        }
    """
    doc = Document(file_path)

    sections = []
    url_re = re.compile(r'https?://(?:www\.)?parentdata\.org/\S+', re.I)
    # Strip trailing numbers from headings: "Popular this week 1" → "Popular this week"
    trailing_num_re = re.compile(r'\s+\d+\s*$')

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        url_match = url_re.search(text)

        if url_match:
            url = url_match.group(0).rstrip('.,;:')

            # Check if there's section name text before the URL on the same line
            prefix = text[:url_match.start()].strip().rstrip(':').strip()
            if prefix:
                # "Section name 1: https://…" — extract both section name and URL
                name = trailing_num_re.sub('', prefix).strip()
                if name:
                    if not sections or sections[-1]['name'].lower() != name.lower():
                        sections.append({'name': name, 'articles': []})

            # Append the URL to the current section
            if sections:
                sections[-1]['articles'].append({'url': url})
        else:
            # Pure text line — treat as a section heading
            name = trailing_num_re.sub('', text).strip()
            if not name:
                continue

            # Merge into existing section if name matches the last one
            if sections and sections[-1]['name'].lower() == name.lower():
                continue

            sections.append({'name': name, 'articles': []})

    return {'sections': sections}


def parse_toddler_article_docx(file_path: str) -> dict:
    """
    Parse a ToddlerData article DOCX (exported from Google Doc).

    Expected document structure:
      Subject Line: …
      Preheader: ToddlerData, 18 Months Old
      From Name: …                              (skipped)
      https://parentdata.org/some-article/       (bare URL — only PD link in the doc)
      DISCUSSION QUESTIONS                       (bold heading)
      Here are a few questions…                  (italic intro)
      Does my child meet the CDC milestones…
      What percentile is my child in…
      Do I have any concerns…

    Returns:
        {
            months_old:            str,
            article_url:           str,
            discussion_intro:      str,
            discussion_questions:  [str]
        }
    """
    from docx.oxml.ns import qn as _qn

    doc = Document(file_path)

    months_old = ''
    article_url = ''
    discussion_intro = ''
    discussion_questions = []
    in_questions = False

    _pd_url_re = re.compile(r'https?://(?:www\.)?parentdata\.org/\S+', re.I)

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # "Subject line: …" → skip
        if re.match(r'^Subject\s+line\s*:', text, re.I):
            continue

        # "Preheader: …" → extract months
        m = re.match(r'^Preheader\s*:\s*(.+)$', text, re.I)
        if m:
            months_match = re.search(r'(\d+)\s*months?', m.group(1), re.I)
            if months_match:
                months_old = months_match.group(1)
            continue

        # "From Name: …" → skip
        if re.match(r'^From\s+Name\s*:', text, re.I):
            continue

        # "Discussion Questions" heading (bold, with or without colon)
        if re.match(r'^Discussion\s+Questions?\s*:?\s*$', text, re.I):
            in_questions = True
            continue

        # Lines after the Discussion Questions heading
        if in_questions:
            # First italic paragraph → intro text, not a question
            if not discussion_intro and _is_italic_para(para):
                discussion_intro = text
                continue
            # Numbered question → strip the number prefix
            q_match = re.match(r'^\d+\.\s*(.+)$', text)
            if q_match:
                discussion_questions.append(q_match.group(1).strip())
            elif text:
                # Non-numbered question
                discussion_questions.append(text)
            continue

        # Skip placeholder lines like "[Insert full draft]"
        if re.match(r'^\[.*\]$', text):
            continue

        # ParentData URL — found in text or as a hyperlink in the paragraph
        if not article_url:
            url_match = _pd_url_re.search(text)
            if url_match:
                article_url = url_match.group(0).rstrip('.,;:')
            else:
                # Check hyperlinks embedded in the paragraph XML
                hl_url = _get_hyperlink_url(para, doc, _qn)
                if hl_url and _pd_url_re.match(hl_url):
                    article_url = hl_url

    return {
        'months_old': months_old,
        'article_url': article_url,
        'discussion_intro': discussion_intro,
        'discussion_questions': discussion_questions,
    }


def parse_toddler_qa_docx(file_path: str) -> dict:
    """
    Parse a ToddlerData Q&A DOCX (exported from Google Doc).

    Expected document structure:
      Subject Line: …
      Preheader: ToddlerData, 18 months
      From Name: …                         (skipped)
      <intro paragraph(s)>
      <article URL 1>                      (bare URL or hyperlink)
      <article URL 2>
      <article URL 3>                      (optional)

    Returns:
        {
            months_old:   str,
            intro_text:   str,
            article_urls: [str] × 2–3,
        }
    """
    from docx.oxml.ns import qn as _qn

    doc = Document(file_path)

    _pd_url_re = re.compile(r'https?://(?:www\.)?parentdata\.org/\S+', re.I)

    months_old = ''
    intro_lines = []
    article_urls = []
    seen_first_url = False

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        # "Subject line: …" → skip
        if re.match(r'^Subject\s+line\s*:', text, re.I):
            continue

        # "Preheader: …" → extract months
        m = re.match(r'^Preheader\s*:\s*(.+)$', text, re.I)
        if m:
            months_match = re.search(r'(\d+)\s*months?', m.group(1), re.I)
            if months_match:
                months_old = months_match.group(1)
            continue

        # "From Name: …" → skip
        if re.match(r'^From\s+Name\s*:', text, re.I):
            continue

        # ParentData URL → article link
        url = ''
        url_match = _pd_url_re.search(text)
        if url_match:
            url = url_match.group(0).rstrip('.,;:')
        else:
            hl_url = _get_hyperlink_url(para, doc, _qn)
            if hl_url and _pd_url_re.match(hl_url):
                url = hl_url

        if url:
            seen_first_url = True
            article_urls.append(url)
            continue

        # Plain text before first URL → intro
        if not seen_first_url:
            intro_lines.append(text)

    return {
        'months_old': months_old,
        'intro_text': ' '.join(intro_lines),
        'article_urls': article_urls[:3],
    }


def parse_toddler_digest_docx(file_path: str) -> dict:
    """
    Parse a ToddlerData digest DOCX (exported from Google Doc).

    Expected document structure:
      Subject Line: <email title>
      Preheader: ToddlerData, 18 Months Old
      From Name: …                            (skipped)
      <intro paragraph(s)>
      <article URL>                            (bare URL or hyperlink)
      <article description>
      … (repeat for up to 3 articles)
      Win of the Month / Win of the Week       (bold heading)
      <quote text>
      —Attribution

    Returns:
        {
            title:            str,
            months_old:       str,
            intro_text:       str,
            articles:         [{title, description, url}] × up to 3,
            win_text:         str,
            win_attribution:  str,
        }
    """
    from docx.oxml.ns import qn as _qn

    doc = Document(file_path)

    _pd_url_re = re.compile(r'https?://(?:www\.)?parentdata\.org/\S+', re.I)

    email_title = ''
    months_old = ''
    intro_lines = []
    articles = []
    win_text = ''
    win_attribution = ''
    in_win = False
    seen_first_url = False
    last_was_url = False  # True if the previous paragraph was an article URL

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            last_was_url = False
            continue

        # "Subject line: …" → email title
        m = re.match(r'^Subject\s+line\s*:\s*(.+)$', text, re.I)
        if m:
            email_title = m.group(1).strip()
            last_was_url = False
            continue

        # "Preheader: …" → extract months
        m = re.match(r'^Preheader\s*:\s*(.+)$', text, re.I)
        if m:
            months_match = re.search(r'(\d+)\s*months?\s*old', m.group(1), re.I)
            if months_match:
                months_old = months_match.group(1)
            last_was_url = False
            continue

        # "From Name: …" → skip
        if re.match(r'^From\s+Name\s*:', text, re.I):
            last_was_url = False
            continue

        # "Win of the Week/Month" heading (bold)
        if re.match(r'^Win\s+of\s+the\s+(Week|Month)\s*:?\s*$', text, re.I):
            in_win = True
            last_was_url = False
            continue

        # Inside Win section
        if in_win:
            # Attribution line starts with em-dash or hyphen
            if re.match(r'^[\u2014\u2013\-]\s*', text):
                win_attribution = re.sub(r'^[\u2014\u2013\-]\s*', '', text).strip()
            elif not win_text:
                win_text = text
            last_was_url = False
            continue

        # ParentData URL → new article (check text and hyperlinks)
        url = ''
        url_match = _pd_url_re.search(text)
        if url_match:
            url = url_match.group(0).rstrip('.,;:')
        else:
            hl_url = _get_hyperlink_url(para, doc, _qn)
            if hl_url and _pd_url_re.match(hl_url):
                url = hl_url

        if url:
            seen_first_url = True
            articles.append({'title': '', 'description': '', 'url': url})
            last_was_url = True
            continue

        # Description line right after a URL
        if last_was_url and articles:
            articles[-1]['description'] = text
            last_was_url = False
            continue

        # Plain text before first article URL → intro
        if not seen_first_url:
            intro_lines.append(text)

        last_was_url = False

    return {
        'title': email_title,
        'months_old': months_old,
        'intro_text': ' '.join(intro_lines),
        'articles': articles[:3],
        'win_text': win_text,
        'win_attribution': win_attribution,
    }


def _get_hyperlink_url(para, doc, qn) -> str:
    """Return the URL of the first hyperlink in a paragraph, or ''."""
    for hl in para._element.findall('.//' + qn('w:hyperlink')):
        r_id = hl.get(qn('r:id'), '')
        if r_id and r_id in doc.part.rels:
            rel = doc.part.rels[r_id]
            target = getattr(rel, '_target', None)
            if target and target.startswith('http'):
                return target
    return ''


def _is_bold_para(para) -> bool:
    """Return True if the first non-empty run in the paragraph is bold."""
    for run in para.runs:
        if run.text.strip():
            return bool(run.bold)
    return False


def _is_italic_para(para) -> bool:
    """Return True if the first non-empty run in the paragraph is italic."""
    for run in para.runs:
        if run.text.strip():
            return bool(run.italic)
    return False


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
        'wp_url': '',
        'fade_from': '',
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

        # ── Top-level labeled fields (detected anywhere in staging section) ─
        if re.match(r'wp\s*(url)?\s*:', line, re.I):
            result['wp_url'] = re.sub(r'^[^:]+:\s*', '', line).strip()

        elif re.match(r'fade\s*from\s*:', line, re.I):
            result['fade_from'] = re.sub(r'^[^:]+:\s*', '', line).strip()

        # ── Section header detection ──────────────────────────────────────
        elif re.match(r'featured\s+image\s*:?\s*$', line, re.I):
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
