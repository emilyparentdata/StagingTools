"""
html_builder.py — BeautifulSoup-based surgical substitution into the email template.

Loads the base template and replaces:
  - Page <title>
  - h1.headline-mobile (article title)
  - p.sub-text (subtitle lines)
  - Welcome banner section (removed; welcome text goes into article body section 1)
  - First article body section (welcome HTML + opening paragraphs + featured image)
  - Second article body section (main article body from first H1 onward)
  - Author block (name, title, link)
  - Related article cards (image, title, description, Read more button)
  - Footer copyright year
"""

import re
from datetime import datetime
from bs4 import BeautifulSoup, NavigableString


# ── Inline styles ────────────────────────────────────────────────────────────

STYLE_P_SUB = (
    "margin: 0; font-family: 'Lora', Georgia, serif; font-weight: 400; "
    "font-size: 18px; line-height: 32px; letter-spacing: -0.8px; color: #000000;"
)


# ── Public entry point ───────────────────────────────────────────────────────

def build_email_html(template_path: str, fields: dict) -> str:
    """
    Build the finished email HTML.

    fields keys:
        title               str
        subtitle_lines      list[str]
        welcome_html        str   (Emily's intro section incl. <hr>; empty string if Emily wrote article)
        article_body_html   str   (full article body, starting with optional intro paragraphs then H1s)
        author_name         str
        author_title        str
        author_url          str
        featured_image_url  str
        featured_image_alt  str
        related_articles    list[{title, url, image_url, image_alt, description}]

    Returns final HTML string.
    """
    with open(template_path, encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    _update_title(soup, fields)
    _update_headline(soup, fields)
    _update_subtitle(soup, fields)
    _remove_welcome_banner(soup)
    _replace_article_sections(soup, fields)
    _update_author_block(soup, fields)
    _update_related_articles(soup, fields.get('related_articles', []))
    _update_copyright(soup)

    html = str(soup)

    # Replace [[GRAPH_N]] placeholders with inline image blocks
    html = _replace_graph_placeholders(html, fields.get('inline_graphs', []))

    # Run all email-checker auto-fixes so the output is already clean
    return apply_email_fixes(html)


# ── Private helpers ──────────────────────────────────────────────────────────

def _update_title(soup, fields):
    """Update the <title> tag."""
    if soup.title:
        soup.title.string = f"{fields.get('title', '')} - ParentData"


def _update_headline(soup, fields):
    """Update the h1.headline-mobile element."""
    h1 = soup.find('h1', class_='headline-mobile')
    if h1:
        h1.clear()
        h1.append(NavigableString(fields.get('title', '')))


def _update_subtitle(soup, fields):
    """Replace all p.sub-text elements with the new subtitle lines."""
    first_sub = soup.find('p', class_='sub-text')
    if not first_sub:
        return
    parent_td = first_sub.find_parent('td')
    if not parent_td:
        return

    # Remove all existing subtitle paragraphs
    for p in parent_td.find_all('p', class_='sub-text'):
        p.decompose()

    # Insert new paragraphs
    lines = fields.get('subtitle_lines', [])
    if not lines and fields.get('subtitle'):
        lines = [fields['subtitle']]

    for line in lines:
        new_p = BeautifulSoup(
            f'<p class="sub-text" style="{STYLE_P_SUB}">{line}</p>',
            'html.parser',
        ).p
        parent_td.append(new_p)


def _remove_welcome_banner(soup):
    """
    Remove the standalone welcome-banner <tr> (the blue .welcome-message block).
    In the staged output this section is absent; the welcome text lives in the
    first article body section instead.
    """
    welcome_p = soup.find('p', class_='welcome-message')
    if not welcome_p:
        return
    outer_tr = _outer_email_tr(welcome_p, soup)
    if outer_tr:
        outer_tr.decompose()


def _replace_article_sections(soup, fields):
    """
    Replace the two article body content sections.

    Section 1 (padding 0px 40px 0px):
        Row A: welcome_html (Emily's intro + <hr>)
        Row B: opening paragraphs (before first H1) + featured image

    Section 2 (padding 0px 40px 20px):
        Row: main article body (from first H1 onward)
    """
    article_tds = _find_article_body_tds(soup)

    body_html = fields.get('article_body_html', '')
    intro_html, main_html = _split_at_first_heading(body_html)

    welcome_html = fields.get('welcome_html', '')
    img_url = fields.get('featured_image_url', '')
    img_alt = _escape_attr(fields.get('featured_image_alt', ''))

    if len(article_tds) >= 1:
        tbody = article_tds[0].find('tbody')
        if tbody:
            tbody.clear()
            # Row A: welcome/bio section
            row_a_html = (
                f'<tr><td style="padding-bottom: 8px; padding-top: 24px; width: 100%;">'
                f'{welcome_html}'
                f'</td></tr>'
            )
            # Row B: intro paragraphs + featured image
            image_div = (
                f'<div style="position: relative; display: inline-block; width: 100%;">'
                f'<img alt="{img_alt}" class="fluid"'
                f' src="{img_url}"'
                f' style="width: 100%; max-width: 552px; height: auto; display: block; border-radius: 16px;">'
                f'</div>'
            )
            row_b_html = (
                f'<tr><td style="padding-bottom: 8px; width: 100%;">'
                f'{intro_html}'
                f'{image_div}'
                f'</td></tr>'
            )
            tbody.append(BeautifulSoup(row_a_html + row_b_html, 'html.parser'))

    if len(article_tds) >= 2:
        tbody = article_tds[1].find('tbody')
        if tbody:
            tbody.clear()
            row_html = (
                f'<tr><td rowspan="3" style="padding-bottom: 8px; width: 100%;">'
                f'{main_html}'
                f'</td></tr>'
            )
            tbody.append(BeautifulSoup(row_html, 'html.parser'))


def _update_author_block(soup, fields):
    """Update the author block: name, title, and 'About X' link."""
    author_td = None
    for td in soup.find_all('td'):
        classes = td.get('class', [])
        if 'tablebox' in classes and 'table-box-mobile' in classes:
            author_td = td
            break

    if not author_td:
        return

    paragraphs = author_td.find_all('p')
    author_name = fields.get('author_name', '')
    author_title = fields.get('author_title', '')
    author_url = fields.get('author_url', '#')
    first_name = author_name.split()[0] if author_name else 'Author'

    if len(paragraphs) >= 1:
        paragraphs[0].clear()
        paragraphs[0].append(NavigableString(author_name))

    if len(paragraphs) >= 2:
        paragraphs[1].clear()
        paragraphs[1].append(NavigableString(author_title))

    if len(paragraphs) >= 3:
        link = paragraphs[2].find('a')
        if link:
            link['href'] = author_url
            link.clear()
            link.append(NavigableString(f'About {first_name}'))


def _update_related_articles(soup, articles: list):
    """Update the two related article card slots."""
    if not articles:
        return

    # Find "More from ParentData" heading
    more_h2 = None
    for h2 in soup.find_all('h2'):
        if 'More from ParentData' in h2.get_text():
            more_h2 = h2
            break
    if not more_h2:
        return

    section_tbody = more_h2.find_parent('tbody')
    if not section_tbody:
        return

    # Collect card rows (rows after the h2 heading row)
    card_rows = []
    found_heading_row = False
    for tr in section_tbody.find_all('tr', recursive=False):
        if not found_heading_row:
            if tr.find('h2') and 'More from ParentData' in tr.get_text():
                found_heading_row = True
        else:
            card_rows.append(tr)

    for i, (card_tr, article) in enumerate(zip(card_rows, articles)):
        is_last = (i == len(articles) - 1)
        _rebuild_article_card(card_tr, article, is_last=is_last)


def _rebuild_article_card(card_tr, article: dict, is_last: bool = False):
    """Rebuild a single article card row with fresh content."""
    td = card_tr.find('td')
    if not td:
        return

    td_style = '' if is_last else 'padding-bottom: 32px;'
    td['style'] = td_style

    url = _escape_attr(article.get('url', '#'))
    img_src = _escape_attr(article.get('image_url', ''))
    img_alt = _escape_attr(article.get('image_alt') or article.get('title', ''))
    title = article.get('title', '')
    description = article.get('description', '')

    card_html = f"""<table border="0" cellpadding="0" cellspacing="0" role="presentation" width="100%">
<tbody>
<tr>
<td align="center" style="padding-bottom: 16px;"><a href="{url}" style="display: block;"> <img alt="{img_alt}" class="fluid" height="150" src="{img_src}" style="width: 100%; max-width: 330px; height: auto; display: block; border-radius: 12px;" width="330"> </a></td>
</tr>
<tr>
<td style="text-align: center;">
<h3 class="h3-heading" style="margin: 0 0 8px 0; font-family: 'Lora', Georgia, serif; font-weight: bold; font-size: 18px; line-height: 24px; letter-spacing: -0.8px; color: #000000;"><a href="{url}" style="color: #000000; text-decoration: none;">{title}</a></h3>
<p style="margin: 0; font-family: 'DM Sans', Arial, Helvetica, sans-serif; font-weight: 400; font-size: 16px; line-height: 24px; letter-spacing: -0.8px; color: #000000;">{description}</p>
</td>
</tr>
<tr>
<td align="center" style="padding: 15px 0; text-align: center;">
<table align="center" border="0" cellpadding="0" cellspacing="0" role="presentation">
<tbody>
<tr>
<td style="border: 2px solid #000000; border-radius: 3px;"><a href="{url}" rel="noopener" style="display: inline-block; padding: 6px 14px; font-family: 'DM Sans', Arial, sans-serif; font-size: 12px; font-weight: 600; color: #000000; text-decoration: none;" target="_blank"> Read more </a></td>
</tr>
</tbody>
</table>
</td>
</tr>
</tbody>
</table>"""

    td.clear()
    td.append(BeautifulSoup(card_html, 'html.parser'))


def _update_copyright(soup):
    """Update the footer copyright year to the current year."""
    year = datetime.now().year
    for p in soup.find_all('p'):
        text = p.get_text()
        if 'Copyright' in text and 'ParentData' in text:
            p.clear()
            p.append(NavigableString(f'Copyright \u00a9 {year} ParentData, All rights reserved.'))
            break


# ── Utilities ────────────────────────────────────────────────────────────────

def _outer_email_tr(element, soup):
    """Find the direct child <tr> of the main email table's <tbody> that contains element."""
    main_table = soup.find('table', class_='email-container')
    if not main_table:
        return None
    main_tbody = main_table.find('tbody')
    if not main_tbody:
        return None
    for tr in main_tbody.find_all('tr', recursive=False):
        if tr.find(lambda tag: tag is element):
            return tr
    return None


def _find_article_body_tds(soup):
    """Return the two <td class='table-box-mobile no-pad-t-b'> elements in order."""
    result = []
    for td in soup.find_all('td'):
        classes = td.get('class', [])
        if 'table-box-mobile' in classes and 'no-pad-t-b' in classes:
            result.append(td)
    return result


def _split_at_first_heading(html: str):
    """
    Split HTML at the first <h1> or <h2> tag.
    Returns (before_html, from_heading_html).
    """
    if not html:
        return '', ''
    m = re.search(r'<h[12][\s>]', html, re.IGNORECASE)
    if m:
        return html[:m.start()], html[m.start():]
    return html, ''


def _escape_attr(value: str) -> str:
    """Escape a string for safe use in an HTML attribute value."""
    return value.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')


# ── Graph placeholder replacement ────────────────────────────────────────────

def _replace_graph_placeholders(html: str, inline_graphs: list) -> str:
    """
    Replace [[GRAPH_1]], [[GRAPH_2]], … with properly styled inline image blocks.

    inline_graphs: list of {'url': str, 'alt': str} in order (index 0 = GRAPH_1).
    Placeholders with no corresponding entry are left as-is so they're visible
    in the output and easy to spot.
    """
    def replace_graph(m):
        n = int(m.group(1))           # 1-based
        idx = n - 1
        if idx >= len(inline_graphs):
            return m.group(0)         # leave placeholder visible if no URL given
        graph = inline_graphs[idx]
        url = _escape_attr(graph.get('url', ''))
        alt = _escape_attr(graph.get('alt', f'Graph {n}'))
        return (
            f'<div style="position: relative; display: inline-block; width: 100%; margin: 16px 0;">'
            f'<img alt="{alt}" class="fluid" src="{url}"'
            f' style="width: 100%; max-width: 552px; height: auto; display: block; border-radius: 8px;">'
            f'</div>'
        )

    return re.sub(r'\[\[GRAPH_(\d+)\]\]', replace_graph, html)


# ── Email compatibility fixes (mirrors email-checker applyFixes engine) ───────

def apply_email_fixes(html: str) -> str:
    """
    Apply all email compatibility fixes, equivalent to the email-checker
    auto-fix engine, so the checker step is no longer needed:

      1. <strong>/<b>  → <span style="font-weight:bold">
      2. <em>/<i>       → <span style="font-style:italic">
      3. <u>            → <span style="text-decoration:underline">
      4. <img> missing display:block → add it
      5. <img> missing alt            → add alt=""
      6. <script> / <iframe>          → removed
      7. Gmail iOS link fix: add inline styles + <span> wrapper to every <a href>
      8. Iterable-injected heights (fractional px or ≥300px on table/tr/td) → height:auto
      9. table-box-mobile <td> with zero top-padding missing no-top-pad → add class
    """
    soup = BeautifulSoup(html, 'html.parser')

    # 1–3. Semantic tags → inline-styled spans
    for tag in soup.find_all(['strong', 'b']):
        tag.name = 'span'
        tag['style'] = 'font-weight:bold;' + (tag.get('style') or '')

    for tag in soup.find_all(['em', 'i']):
        tag.name = 'span'
        tag['style'] = 'font-style:italic;' + (tag.get('style') or '')

    for tag in soup.find_all('u'):
        tag.name = 'span'
        tag['style'] = 'text-decoration:underline;' + (tag.get('style') or '')

    # 4–5. <img> fixes
    for img in soup.find_all('img'):
        style = img.get('style', '')
        if 'display' not in style.lower():
            img['style'] = 'display:block;margin:0 auto;' + style
        if not img.has_attr('alt'):
            img['alt'] = ''

    # 6. Remove <script> and <iframe>
    for tag in soup.find_all(['script', 'iframe']):
        tag.decompose()

    # 9. no-top-pad class
    for td in soup.find_all('td'):
        classes = td.get('class', [])
        if 'table-box-mobile' not in classes or 'no-top-pad' in classes:
            continue
        style = td.get('style', '')
        if (re.search(r'\bpadding-top\s*:\s*0', style, re.I) or
                re.search(r'\bpadding\s*:\s*0px?\b', style, re.I)):
            td['class'] = classes + ['no-top-pad']

    html = str(soup)

    # 7. Gmail iOS link fix (regex on string — mirrors email-checker exactly)
    html = _apply_link_fixes(html)

    # 8. Iterable height fix (regex on string)
    html = _fix_iterable_heights(html)

    return html


def _apply_link_fixes(html: str) -> str:
    """
    For every <a href> in the HTML:
      - Ensure it has font-size, color, and text-decoration inline styles.
      - Wrap its content in a <span> with those same styles.

    This is the Gmail iOS workaround: Gmail iOS strips all inline styles from
    <a> tags but respects styles on child elements, so the span preserves the
    appearance.  Mirrors the email-checker link fix exactly.
    """
    def fix_link(m):
        attrs, content = m.group(1), m.group(2)

        # Skip anchors without href
        if not re.search(r'\bhref\s*=', attrs, re.I):
            return m.group(0)

        style_m = re.search(r'\bstyle\s*=\s*"([^"]*)"', attrs, re.I)
        cur_style = style_m.group(1) if style_m else ''

        has_color    = bool(re.search(r'\bcolor\s*:', cur_style, re.I))
        has_text_dec = bool(re.search(r'\btext-decoration\s*:', cur_style, re.I))
        has_font_sz  = bool(re.search(r'\bfont-size\s*:', cur_style, re.I))
        already_fixed = bool(re.match(r'^\s*<span\b[^>]*\bstyle\s*=', content, re.I))

        # Already complete — don't double-process
        if has_color and has_text_dec and has_font_sz and already_fixed:
            return m.group(0)

        # Build the styles missing from the <a> tag
        add_parts = []
        if not has_font_sz:
            add_parts.append('font-size:inherit')
        if not has_color:
            add_parts.append('color:#000000')
        if not has_text_dec:
            add_parts.append('text-decoration:underline')
        add_str = (';'.join(add_parts) + ';') if add_parts else ''

        # Update the <a> tag's style attribute
        if add_str:
            if style_m:
                new_attrs = attrs[:style_m.start()] + f'style="{add_str}{cur_style}"' + attrs[style_m.end():]
            else:
                new_attrs = f' style="{add_str}"' + attrs
        else:
            new_attrs = attrs

        # Derive the span's style from the now-merged <a> style
        merged = add_str + cur_style
        fz_m  = re.search(r'font-size\s*:\s*([^;]+)',       merged, re.I)
        c_m   = re.search(r'\bcolor\s*:\s*([^;]+)',          merged, re.I)
        td_m  = re.search(r'text-decoration\s*:\s*([^;]+)',  merged, re.I)
        span_style = (
            f"font-size:{fz_m.group(1).strip() if fz_m else 'inherit'};"
            f"color:{c_m.group(1).strip() if c_m else '#000000'};"
            f"text-decoration:{td_m.group(1).strip() if td_m else 'underline'};"
        )

        new_content = content if already_fixed else f'<span style="{span_style}">{content}</span>'
        return f'<a{new_attrs}>{new_content}</a>'

    return re.sub(r'<a\b([^>]*)>([\s\S]*?)</a>', fix_link, html, flags=re.IGNORECASE)


def _fix_iterable_heights(html: str) -> str:
    """
    Replace Iterable-editor-injected heights on <table>, <tr>, <td> with
    height:auto.  Targets fractional pixel values (e.g. 81.23px, 1886.73px)
    and large round integers ≥300px that represent section heights.
    Small intentional heights under 300px are left untouched.
    Mirrors the email-checker height fix exactly.
    """
    pattern = re.compile(
        r'(<(?:table|tr|td)\b[^>]*\bstyle\s*=\s*")([^"]*)(")',
        re.IGNORECASE,
    )
    height_re = re.compile(
        r'\bheight\s*:\s*(?:\d+\.\d+|[3-9]\d{2}|\d{4,})px',
        re.IGNORECASE,
    )

    def replace_heights(m):
        pre, style, post = m.group(1), m.group(2), m.group(3)
        if height_re.search(style):
            style = height_re.sub('height:auto', style)
        return pre + style + post

    return pattern.sub(replace_heights, html)
