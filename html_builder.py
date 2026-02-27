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

Supports two template types:
  'standard'  — standard newsletter with welcome, author block, related reading
  'fertility' — fertility article with subtitle/author in header, bottom line box
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

def build_email_html(template_path: str, fields: dict, template_type: str = 'standard') -> str:
    """
    Build the finished email HTML.

    fields keys (standard):
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

    Additional fields for fertility template:
        bottom_line_html    str   (<ul>...</ul> for the purple bottom line box)

    Returns final HTML string.
    """
    with open(template_path, encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    if template_type == 'qa':
        _inject_qa(soup, fields)
    elif template_type == 'fertility':
        _inject_fertility(soup, fields)
    elif template_type == 'marketing':
        _inject_marketing(soup, fields)
    elif template_type == 'fertility_digest':
        _inject_fertility_digest(soup, fields)
    elif template_type == 'paid_digest':
        _inject_paid_digest(soup, fields)
    elif template_type == 'latest_teaser':
        _inject_latest_teaser(soup, fields)
    else:
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
                f'<div style="position: relative; display: inline-block; width: 100%; margin-bottom: 24px;">'
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


# ── Latest Teaser template injection ─────────────────────────────────────────

def _inject_latest_teaser(soup, fields):
    """Inject all fields into the latest teaser template."""
    _update_title(soup, fields)
    _update_headline(soup, fields)
    _update_subtitle(soup, fields)
    _remove_welcome_banner(soup)
    _inject_teaser_body(soup, fields)
    _update_teaser_continue_link(soup, fields)
    _update_related_articles(soup, fields.get('related_articles', []))
    _update_copyright(soup)


def _update_teaser_continue_link(soup, fields):
    """Update the CONTINUE READING button href."""
    btn = soup.find('div', class_='continue-reading-btn')
    if btn:
        a = btn.find('a')
        if a:
            a['href'] = fields.get('article_url', '#')


def _inject_teaser_body(soup, fields):
    """
    Split article_body_html at fade_from and distribute content across
    sections 4 (article body) and 6 (faded content).

    Section 4: italic intro paragraph(s) + <hr> + all visible blocks,
               with featured image inserted inline before the first <h2>
    Section 5 (two-column row): removed entirely — image is now inline
    Section 6: faded blocks (from fade_from paragraph onwards)
    """
    intro_text = fields.get('intro_text', '')
    fade_from = (fields.get('fade_from') or '').strip().lower()
    article_body_html = fields.get('article_body_html', '')
    img_url = fields.get('featured_image_url', '')
    img_alt = _escape_attr(fields.get('featured_image_alt', ''))

    # Parse article body into top-level block elements
    body_soup = BeautifulSoup(article_body_html, 'html.parser')
    blocks = [el for el in body_soup.children
              if hasattr(el, 'name') and el.name is not None]

    # Find fade split index: first block whose text contains fade_from.
    # Use only the first 60 chars of fade_from (a few words is enough to
    # identify the paragraph) and normalize Unicode punctuation before
    # comparing, since the doc and WP content may encode quotes differently.
    fade_idx = len(blocks)
    if fade_from:
        fade_key = _norm_fade(fade_from[:60])
        for i, el in enumerate(blocks):
            if fade_key and fade_key in _norm_fade(el.get_text()):
                fade_idx = i
                break

    visible_blocks = list(blocks[:fade_idx])
    faded_blocks = blocks[fade_idx:]

    # Strip image-only blocks that appear before the first <h2>.
    # WordPress often places an editorial/secondary image near the top of the
    # article body.  Since we inject the featured image before the H2 ourselves,
    # any existing pre-H2 image would create a duplicate.  Graphs and figures
    # that appear AFTER the H2 are left untouched.
    clean_visible = []
    h2_found = False
    for el in visible_blocks:
        if el.name and el.name.lower() == 'h2':
            h2_found = True
        if not h2_found and _is_image_only_block(el):
            continue
        clean_visible.append(el)
    visible_blocks = clean_visible

    # Insert featured image before the first <h2> in visible blocks; append if none
    if img_url:
        img_el = BeautifulSoup(
            f'<div style="position: relative; display: inline-block; width: 100%; margin-bottom: 24px;">'
            f'<img alt="{img_alt}" class="fluid"'
            f' src="{img_url}"'
            f' style="width: 100%; max-width: 552px; height: auto; display: block; border-radius: 16px;">'
            f'</div>',
            'html.parser',
        ).find('div')
        img_inserted = False
        for i, el in enumerate(visible_blocks):
            if el.name and el.name.lower() == 'h2':
                visible_blocks.insert(i, img_el)
                img_inserted = True
                break
        if not img_inserted:
            visible_blocks.append(img_el)

    # ── Capture DOM targets before any manipulation ───────────────────────────
    intro_p_tmpl = soup.find(
        lambda tag: tag.name == 'p' and 'INTRO TEXT HERE' in (tag.get_text() or '')
    )
    section4_td = intro_p_tmpl.find_parent('td') if intro_p_tmpl else None

    two_col_tr = None
    for tr in soup.find_all('tr'):
        stack_tds = [td for td in tr.find_all('td', recursive=False)
                     if 'stack-column' in (td.get('class') or [])]
        if len(stack_tds) >= 2:
            two_col_tr = tr
            break

    two_col_outer_tr = _outer_email_tr(two_col_tr, soup) if two_col_tr else None

    # Find section 6 content td (navigating inner table structure)
    section6_content_td = None
    if two_col_outer_tr:
        main_table = soup.find('table', class_='email-container')
        if main_table:
            main_tbody = main_table.find('tbody')
            main_rows = list(main_tbody.find_all('tr', recursive=False))
            if two_col_outer_tr in main_rows:
                idx = main_rows.index(two_col_outer_tr)
                if idx + 1 < len(main_rows):
                    section6_outer_tr = main_rows[idx + 1]
                    outer_td = section6_outer_tr.find('td')
                    if outer_td:
                        table = outer_td.find('table')
                        if table:
                            tbody = table.find('tbody')
                            if tbody:
                                inner_tr = tbody.find('tr')
                                if inner_tr:
                                    section6_content_td = inner_tr.find('td')

    # ── Section 4: italic intro + hr + all visible blocks ────────────────────
    if section4_td:
        section4_td.clear()

        # Italic intro — split on blank lines to support multiple paragraphs
        intro_style = (
            "padding-bottom: 16px; margin: 0; "
            "font-family: 'DM Sans', Arial, Helvetica, sans-serif; "
            "font-weight: 400; font-style: italic; font-size: 16px; line-height: 24px; color: #000000;"
        )
        intro_paras = [p.strip() for p in intro_text.split('\n\n') if p.strip()]
        if not intro_paras and intro_text.strip():
            intro_paras = [intro_text.strip()]
        for para in intro_paras:
            new_p = BeautifulSoup(
                f'<p style="{intro_style}">{para}</p>', 'html.parser'
            ).p
            section4_td.append(new_p)

        # Horizontal rule separating intro from article body
        section4_td.append(BeautifulSoup(
            '<hr style="border: none; border-top: 1px solid #e0e0e0; margin: 8px 0 24px 0;">',
            'html.parser',
        ).hr)

        # All visible blocks (image already spliced in before first h2)
        for el in visible_blocks:
            section4_td.append(el)

    # ── Section 6: single faded paragraph, medium → light ────────────────────
    # Only the indicated paragraph is shown — everything after it is discarded.
    # Both halves live inside ONE element so there is no paragraph gap.
    # First half is fade-out-medium (opacity 0.5); second half is fade-out-light
    # (opacity 0.2) so the text grows lighter toward the bottom of the visible
    # content, reinforcing the "more below the paywall" effect.
    if section6_content_td:
        section6_content_td.clear()
        if faded_blocks:
            fade_el = faded_blocks[0]
            tag = fade_el.name or 'p'
            base_style = (fade_el.get('style') or '').rstrip(';')
            base_classes = [c for c in (fade_el.get('class') or [])
                            if c not in ('fade-out-light', 'fade-out-medium')]

            first_html, second_html = _split_fade_paragraph(fade_el)

            parts = []
            if first_html:
                parts.append(f'<span style="opacity:0.5;">{first_html}</span>')
            if second_html:
                parts.append(f'<span style="opacity:0.2;">{second_html}</span>')

            if parts:
                cls_attr = (' class="' + ' '.join(base_classes) + '"') if base_classes else ''
                sty = (base_style + ';') if base_style else ''
                el = BeautifulSoup(
                    f'<{tag}{cls_attr} style="{sty}">{"".join(parts)}</{tag}>',
                    'html.parser',
                ).find(tag)
                if el:
                    section6_content_td.append(el)

    # ── Remove section 5 (two-column row) — image is now inline in section 4 ─
    if two_col_outer_tr:
        two_col_outer_tr.decompose()


# ── Fertility template injection ──────────────────────────────────────────────

def _inject_fertility(soup, fields):
    """Inject all fields into the fertility article template."""
    _handle_fertility_banner(soup, fields.get('include_update_banner', False))
    _update_title(soup, fields)
    _update_headline(soup, fields)
    _update_fertility_subtitle_author(soup, fields)
    _replace_fertility_body(soup, fields)
    _update_fertility_bottom_line(soup, fields)
    _update_copyright(soup)


def _handle_fertility_banner(soup, include_banner: bool):
    """
    Handle the top banner row (p.news-top-link) in fertility templates.

    If include_banner is False (default): remove the row entirely.
    If include_banner is True: replace its content with the newsletter
    update prompt so readers can opt out of fertility sends.
    """
    banner_p = soup.find('p', class_='news-top-link')
    if not banner_p:
        return

    if not include_banner:
        outer_tr = _outer_email_tr(banner_p, soup)
        if outer_tr:
            outer_tr.decompose()
        return

    # Update with new text, preserving the same <p> element and its styling
    banner_p.clear()
    new_html = (
        'Are you starting fertility treatment or no longer TTC? '
        '<span style="text-decoration: underline; font-style: italic;">'
        '<a href="https://parentdata.org/account/#newsletter-settings-section"'
        ' style="color: #000000; font-size: 18px;">Update your newsletters.</a>'
        '</span>'
    )
    banner_p.append(BeautifulSoup(new_html, 'html.parser'))


def _update_fertility_subtitle_author(soup, fields):
    """
    Update the subtitle and author line in the fertility template header.

    The fertility template has a <td class="table-box-mobile top-box-header-m no-top-pad">
    containing two <p class="sub-text"> elements:
      1st p: subtitle (font-weight: 600)
      2nd p: author name + title (font-weight: 300)
    """
    subtitle_td = None
    for td in soup.find_all('td'):
        classes = td.get('class', [])
        if 'table-box-mobile' in classes and 'top-box-header-m' in classes:
            subtitle_td = td
            break
    if not subtitle_td:
        return

    sub_paras = subtitle_td.find_all('p', class_='sub-text')

    # First p: subtitle
    subtitle_lines = fields.get('subtitle_lines', [])
    subtitle_text = subtitle_lines[0] if subtitle_lines else ''
    if sub_paras:
        sub_paras[0].clear()
        sub_paras[0].append(NavigableString(subtitle_text))

    # Second p: author name (+ title if present)
    author_name = fields.get('author_name', '')
    author_title = fields.get('author_title', '')
    author_line = f'{author_name}, {author_title}' if author_title else author_name
    if len(sub_paras) >= 2:
        sub_paras[1].clear()
        sub_paras[1].append(NavigableString(author_line))


def _replace_fertility_body(soup, fields):
    """
    Inject article body and featured image into the fertility template.

    Layout in the template:
      Row 4 (nested table):
        - td.tablebox  → intro content (before first H2)
        - td            → featured image (img[alt="Article Image"])
      Row 5 (direct td.tablebox.table-box-mobile.no-top-pad):
        → main body (from first H2 onward)

    If the article has no section headings, split after the 2nd paragraph
    so the featured image lands between paragraphs 2 and 3 rather than at
    the end of all the content.
    """
    body_html = fields.get('article_body_html', '')
    intro_html, main_html = _split_at_first_heading(body_html)
    if not main_html:
        # No headings — split after 2nd paragraph so image has a natural position
        intro_html, main_html = _split_after_nth_paragraph(body_html, n=2)

    # --- Intro body td (first td.tablebox that is NOT also table-box-mobile) ---
    intro_td = None
    for td in soup.find_all('td'):
        classes = td.get('class', [])
        if 'tablebox' in classes and 'table-box-mobile' not in classes:
            intro_td = td
            break
    if intro_td:
        intro_td.clear()
        if intro_html:
            intro_td.append(BeautifulSoup(intro_html, 'html.parser'))

    # --- Featured image ---
    img_url = fields.get('featured_image_url', '')
    img_alt = _escape_attr(fields.get('featured_image_alt', ''))
    img = soup.find('img', attrs={'alt': 'Article Image'})
    if img and img_url:
        img['src'] = img_url
        img['alt'] = img_alt

    # --- Main body td (td.tablebox.table-box-mobile.no-top-pad, Row 5) ---
    main_td = None
    for td in soup.find_all('td'):
        classes = td.get('class', [])
        if 'tablebox' in classes and 'table-box-mobile' in classes and 'no-top-pad' in classes:
            main_td = td
            break
    if main_td:
        main_td.clear()
        if main_html:
            main_td.append(BeautifulSoup(main_html, 'html.parser'))


def _update_fertility_bottom_line(soup, fields):
    """
    Replace the <ul> inside the purple bottom line box with the new content.

    The purple box has background-color: #a9b4ff in its style attribute.
    Inside is a nested table with an h3 heading row and a ul row.
    """
    bottom_line_html = fields.get('bottom_line_html', '')
    if not bottom_line_html:
        return

    # Find the purple bottom line td
    purple_td = None
    for td in soup.find_all('td'):
        if 'a9b4ff' in td.get('style', ''):
            purple_td = td
            break
    if not purple_td:
        return

    # Replace the existing <ul>
    ul = purple_td.find('ul')
    if ul:
        new_ul = BeautifulSoup(bottom_line_html, 'html.parser')
        ul.replace_with(new_ul)


# ── Fertility Digest template injection ──────────────────────────────────────

def _inject_fertility_digest(soup, fields):
    """Inject all fields into the fertility digest template."""
    _update_title(soup, fields)
    _update_headline(soup, fields)
    _update_digest_intro(soup, fields)
    _update_digest_cards(soup, fields)
    _update_copyright(soup)


def _update_digest_intro(soup, fields):
    """Update the editorial intro paragraph (p.sub-text inside td.top-box-header-m)."""
    subtitle_td = soup.find('td', class_='top-box-header-m')
    if not subtitle_td:
        return
    p = subtitle_td.find('p', class_='sub-text')
    if p:
        p.clear()
        p.append(NavigableString(fields.get('intro_text', '')))


def _update_digest_cards(soup, fields):
    """
    Update the 5 article card rows in the fertility digest template.

    Each card row is identified by containing a div.read-more-btn.
    Updates: image src/alt, article title (strong inside Lora p),
    description (DM Sans p), and READ MORE button href.
    """
    articles = fields.get('articles', [])
    # Each card is a nested-table structure: an outer <tr> contains both the
    # article-card-img AND the read-more-btn (via inner tables).  Inner <tr>
    # rows also contain the button but not the image, so filtering by both
    # gives us exactly the 5 outer card rows.
    card_rows = [tr for tr in soup.find_all('tr')
                 if tr.find('div', class_='read-more-btn')
                 and tr.find('img', class_='article-card-img')]
    for tr, article in zip(card_rows, articles):
        img = tr.find('img', class_='article-card-img')
        if img:
            img['src'] = article.get('image_url', '')
            img['alt'] = _escape_attr(article.get('image_alt') or article.get('title', ''))

        title_p = tr.find('p', style=re.compile(r'Lora', re.I))
        if title_p:
            strong = title_p.find('strong')
            if strong:
                strong.clear()
                strong.append(NavigableString(article.get('title', '')))

        desc_p = tr.find('p', style=re.compile(r'DM Sans', re.I))
        if desc_p:
            desc_p.clear()
            desc_p.append(NavigableString(article.get('description', '')))

        btn_div = tr.find('div', class_='read-more-btn')
        if btn_div:
            a = btn_div.find('a')
            if a:
                a['href'] = article.get('url', '#')


# ── Paid Digest template injection ────────────────────────────────────────────

def _inject_paid_digest(soup, fields):
    """Inject section names and article data into the paid digest template."""
    _update_paid_digest_cards(soup, fields)
    _update_copyright(soup)


def _update_paid_digest_cards(soup, fields):
    """
    Update the 5 section headings and 6 article cards in the paid digest template.

    The template has h2.section-title elements (5) and table.newsletter-card
    elements (6) in DOM order. Sections map 1:1 to headings. Articles are
    assigned to cards in flattened order across all sections.
    """
    sections = fields.get('sections', [])

    # Update section headings (h2.section-title)
    section_headings = soup.find_all('h2', class_='section-title')
    for i, h2 in enumerate(section_headings):
        if i < len(sections):
            h2.clear()
            h2.append(NavigableString(sections[i].get('name', '')))

    # Flatten all articles across sections into a single ordered list
    all_articles = []
    for section in sections:
        for article in section.get('articles', []):
            all_articles.append(article)

    # Update article cards (table.newsletter-card)
    card_tables = soup.find_all('table', class_='newsletter-card')
    for i, card in enumerate(card_tables):
        if i >= len(all_articles):
            break
        article = all_articles[i]

        title = article.get('title', '')
        subtitle = article.get('subtitle', '')
        url = article.get('url', '#')
        image_url = article.get('image_url', '')
        image_alt = _escape_attr(article.get('image_alt', '') or title)

        # Update all img tags in the card (mobile + desktop variants)
        for img in card.find_all('img'):
            if image_url:
                img['src'] = image_url
            img['alt'] = image_alt

        # Update h3 title
        h3 = card.find('h3')
        if h3:
            h3.clear()
            h3.append(NavigableString(title))

        # Update subtitle <p> (the p after h3 with DM Sans font)
        subtitle_p = card.find('p', style=re.compile(r'DM Sans', re.I))
        if subtitle_p:
            subtitle_p.clear()
            subtitle_p.append(NavigableString(subtitle))

        # Update Read more link href
        for a in card.find_all('a'):
            if 'read more' in (a.get_text() or '').lower().strip():
                a['href'] = url
                break


# ── Q&A template injection ───────────────────────────────────────────────────

def _inject_qa(soup, fields):
    """Inject all fields into the Q&A template."""
    _handle_fertility_banner(soup, fields.get('include_update_banner', False))
    _update_qa_intro(soup, fields)
    _update_qa_pairs(soup, fields)
    _update_copyright(soup)


def _update_qa_intro(soup, fields):
    """Update the subtitle/intro sentence (p.sub-text) with the editable intro text."""
    intro_text = fields.get('intro_text', '')
    sub_p = soup.find('p', class_='sub-text')
    if sub_p and intro_text:
        sub_p.clear()
        sub_p.append(BeautifulSoup(
            f'<span style="white-space: pre-wrap;">{_escape_attr(intro_text)}</span>',
            'html.parser',
        ))


def _update_qa_pairs(soup, fields):
    """
    Inject both Q&A pairs.

    Locates each Question/Answer block by the decorative img[alt="Question"] and
    img[alt="Answer"] images, then:
      - Replaces the italic <p> in the question block with the reader's question text.
      - Replaces the <div> inside td.tablebox in the answer block with the answer HTML.
    """
    question_imgs = soup.find_all('img', attrs={'alt': 'Question'})
    answer_imgs = soup.find_all('img', attrs={'alt': 'Answer'})

    for i, q_img in enumerate(question_imgs):
        qa = fields.get(f'qa{i + 1}', {})
        outer_tr = _outer_email_tr(q_img, soup)
        if not outer_tr:
            continue

        # The italic <p> holds the question text and author sign-off
        italic_p = outer_tr.find('p', style=lambda s: 'italic' in (s or ''))
        if italic_p:
            question_text = _escape_attr(qa.get('question_text', ''))
            author = _escape_attr(qa.get('question_author', ''))
            content = f'<span style="white-space: pre-wrap;">{question_text}</span>'
            if author:
                content += f'<br><br><span style="white-space: pre-wrap;">\u2014{author}</span>'
            italic_p.clear()
            italic_p.append(BeautifulSoup(content, 'html.parser'))

    qa_author_line = fields.get('qa_author_line', '').strip()

    for i, a_img in enumerate(answer_imgs):
        qa = fields.get(f'qa{i + 1}', {})
        outer_tr = _outer_email_tr(a_img, soup)
        if not outer_tr:
            continue

        tablebox_td = outer_tr.find('td', class_='tablebox')
        if tablebox_td:
            div = tablebox_td.find('div')
            if div:
                div.clear()
                answer_html = qa.get('answer_html', '')
                if answer_html:
                    div.append(BeautifulSoup(answer_html, 'html.parser'))

            # Add the author attribution line after the last answer
            if i == len(answer_imgs) - 1 and qa_author_line:
                author_line_html = (
                    '<div><p style="white-space-collapse: preserve; '
                    "font-family: 'DM Sans', Arial, Helvetica, sans-serif; "
                    'font-weight: normal; font-size: 16px; line-height: 24px; color: #000000;">'
                    '<span class="g-italic-fnt" style="font-style: italic; font-size: 16px; '
                    "font-family: 'DM Sans', Arial, Helvetica, sans-serif;\">"
                    f"{_escape_attr(qa_author_line)}"
                    '</span></p></div>'
                )
                tablebox_td.append(BeautifulSoup(author_line_html, 'html.parser'))


# ── Marketing template injection ─────────────────────────────────────────────

_STYLE_P_MKT_INTRO = (
    "font-family: 'DM Sans', Arial, Helvetica, sans-serif; font-weight: normal; "
    "font-size: 16px; line-height: 24px; color: #000000; font-style: italic;"
)


def _inject_marketing(soup, fields):
    """Inject all fields into the marketing article template."""
    _update_title(soup, fields)
    _update_marketing_banner(soup, fields)
    _update_marketing_intro(soup, fields)
    _update_marketing_pricing(soup, fields)
    _replace_marketing_body(soup, fields)
    _update_marketing_author(soup, fields)
    _update_copyright(soup)


def _update_marketing_banner(soup, fields):
    """Update the blue pill bar text (p.welcome-message)."""
    p = soup.find('p', class_='welcome-message')
    if not p:
        return
    p.clear()
    p.append(NavigableString(fields.get('banner_text', "It's the final day of your trial!")))


def _update_marketing_intro(soup, fields):
    """Replace the intro tablebox paragraphs with CSV-sourced text and discount link."""
    intro_td = soup.find('td', class_='tablebox')
    if not intro_td:
        return

    text = fields.get('intro_option_text', '')
    discount_url = _escape_attr(fields.get('discount_url', '#'))

    if '👉' in text:
        para1 = text.split('👉')[0].strip()
        para2 = '👉 ' + text.split('👉')[1].strip()
    else:
        para1 = text
        para2 = ''

    intro_td.clear()

    p1_html = f'<p style="{_STYLE_P_MKT_INTRO}">{_escape_attr(para1)}</p>'
    intro_td.append(BeautifulSoup(p1_html, 'html.parser'))

    if para2:
        p2_html = (
            f'<p style="{_STYLE_P_MKT_INTRO}">'
            f'<a href="{discount_url}" style="color:#054f8b;text-decoration:underline;">'
            f'{_escape_attr(para2)}</a></p>'
        )
        intro_td.append(BeautifulSoup(p2_html, 'html.parser'))


def _update_marketing_pricing(soup, fields):
    """Update the old (strikethrough) price, new price, and UPGRADE NOW button href."""
    old_price_td = soup.find('td', class_='pricing-old')
    if old_price_td:
        p = old_price_td.find('p')
        if p:
            p.clear()
            p.append(NavigableString(fields.get('old_price', '$120')))

    pricing_td = soup.find('td', class_='pricing-new')
    if pricing_td:
        p = pricing_td.find('p')
        if p:
            p.clear()
            p.append(NavigableString(fields.get('discount_price', '$84/year')))

    upgrade_link = soup.find('a', string=re.compile(r'UPGRADE\s+NOW', re.I))
    if upgrade_link:
        upgrade_link['href'] = fields.get('discount_url', 'https://parentdata.org/register/plus-yearly/?coupon=allaccess30')


def _replace_marketing_body(soup, fields):
    """
    Delete all rows between the upgrade section and author block, then insert:
      [intro paragraphs row →] featured image row → main body row → leave-a-comment row

    The article body is split at the first heading so the image sits between the
    opening paragraphs and the first section heading.  If the body starts directly
    with a heading (no intro text), the image row comes first.
    """
    upgrade_link = soup.find('a', string=re.compile(r'UPGRADE\s+NOW', re.I))
    upgrade_row = _outer_email_tr(upgrade_link, soup)

    author_td = _find_marketing_author_td(soup)
    author_row = _outer_email_tr(author_td, soup) if author_td else None

    if not upgrade_row or not author_row:
        return

    main_tbody = soup.find('table', class_='email-container').find('tbody')
    rows = list(main_tbody.find_all('tr', recursive=False))
    start_i = rows.index(upgrade_row)
    end_i = rows.index(author_row)
    for row in rows[start_i + 1:end_i]:
        row.decompose()

    featured_image_url = _escape_attr(fields.get('featured_image_url', ''))
    featured_image_alt = _escape_attr(fields.get('featured_image_alt', ''))
    article_body_html = fields.get('article_body_html', '')
    article_url = _escape_attr(fields.get('article_url', '#'))

    # Scale down font sizes for marketing context (slightly smaller than standard body)
    article_body_html = _scale_marketing_body_fonts(article_body_html)

    # Split body at first heading so image goes between intro text and first section
    intro_html, main_html = _split_at_first_heading(article_body_html)

    def _body_row(content_html):
        return (
            f'<tr><td class="table-box-mobile no-top-pad" style="background-color:#fff;padding:0 48px;">'
            f'<table border="0" cellpadding="0" cellspacing="0" role="presentation" width="100%">'
            f'<tbody><tr><td class="tablebox" style="padding-bottom:0;">'
            f'{content_html}'
            f'</td></tr></tbody></table></td></tr>'
        )

    featured_image_row_html = (
        f'<tr><td class="table-box-mobile no-top-pad" style="background-color:#fff;padding:0 48px;">'
        f'<table border="0" cellpadding="0" cellspacing="0" role="presentation" width="100%">'
        f'<tbody><tr><td style="text-align:center;">'
        f'<img src="{featured_image_url}" alt="{featured_image_alt}"'
        f' style="display:block;width:100%;max-width:520px;height:auto;border-radius:20px;margin:0 auto;"'
        f' class="fluid">'
        f'</td></tr></tbody></table></td></tr>'
    )

    leave_comment_row_html = (
        f'<tr><td class="table-box-mobile no-top-pad" style="background-color:#fff;padding:0 48px 40px;">'
        f'<table align="center" border="0" cellpadding="0" cellspacing="0" role="presentation"'
        f' style="max-width:288px;width:100%;">'
        f'<tbody><tr><td align="center" style="padding:0;">'
        f'<div style="display:inline-block;border-radius:15px;background-color:#fceea9;'
        f'border:2px solid #000;box-shadow:0 4px 4px rgba(0,0,0,0.25);">'
        f'<a href="{article_url}" rel="noopener" target="_blank"'
        f' style="display:block;padding:16px 24px;font-family:\'DM Sans\',Arial,sans-serif;'
        f'font-weight:800;font-size:20px;color:#000;text-decoration:none;text-transform:uppercase;">'
        f'LEAVE A COMMENT</a></div>'
        f'</td></tr></tbody></table></td></tr>'
    )

    def _parsed_tr(html):
        return BeautifulSoup(html, 'html.parser').find('tr')

    # Insert in reverse order so the final document order is correct
    upgrade_row.insert_after(_parsed_tr(leave_comment_row_html))
    upgrade_row.insert_after(_parsed_tr(_body_row(main_html)))
    upgrade_row.insert_after(_parsed_tr(featured_image_row_html))
    if intro_html:
        upgrade_row.insert_after(_parsed_tr(_body_row(intro_html)))


def _update_marketing_author(soup, fields):
    """Update author name, title, and About link in the marketing author block."""
    author_td = _find_marketing_author_td(soup)
    if not author_td:
        return

    author_name = fields.get('author_name', '')
    author_title = fields.get('author_title', '')
    author_url = fields.get('author_url', '#')
    first_name = author_name.split()[0] if author_name else 'Author'

    author_p = author_td.find('p', style=re.compile(r'Lora.*font-size:\s*22px', re.I))
    if author_p:
        author_p.clear()
        author_p.append(NavigableString(author_name))

        title_p = author_p.find_next_sibling('p')
        if title_p:
            title_p.clear()
            title_p.append(NavigableString(author_title))

        link = author_p.find_next('a')
        if link:
            link['href'] = author_url
            link.clear()
            link.append(NavigableString(f'About {first_name}'))


# ── Utilities ────────────────────────────────────────────────────────────────

def _scale_marketing_body_fonts(html: str) -> str:
    """
    Scale down inline font sizes in marketing article body HTML so the body
    feels like a preview rather than the full newsletter layout.

    22px Lora section headings → 18px
    16px DM Sans body text / list items → 14px
    """
    if not html:
        return html
    html = re.sub(r'\bfont-size:\s*22px', 'font-size:18px', html)
    html = re.sub(r'\bfont-size:\s*16px', 'font-size:14px', html)
    return html


def _find_marketing_author_td(soup):
    """
    Find the marketing template author block td.

    The author block has both 'tablebox' and 'table-box-mobile' classes AND a
    cream background (rgb(255, 252, 238)), which distinguishes it from the
    article body sections that also have both classes but no background color.
    """
    for td in soup.find_all('td'):
        classes = td.get('class', [])
        if 'tablebox' in classes and 'table-box-mobile' in classes:
            if '255, 252, 238' in td.get('style', ''):
                return td
    return None


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


def _split_after_nth_paragraph(html: str, n: int = 2):
    """
    Split HTML immediately after the nth closing </p> tag.
    Returns (first_n_paragraphs_html, remaining_html).
    If there are fewer than n paragraphs, returns (html, '').
    """
    if not html:
        return '', ''
    count = 0
    pos = 0
    while count < n:
        m = re.search(r'</p>', html[pos:], re.IGNORECASE)
        if not m:
            return html, ''
        pos += m.end()
        count += 1
    return html[:pos], html[pos:]


def _is_image_only_block(el) -> bool:
    """Return True if el is a block element containing an image but no visible text."""
    if not hasattr(el, 'name') or not el.name:
        return False
    return bool(el.find('img')) and not el.get_text(strip=True)


def _norm_fade(s: str) -> str:
    """
    Lowercase and normalise Unicode punctuation so fade_from matching is
    robust to apostrophe/quote encoding differences between the Google Doc
    (which may produce \ufffd replacement chars) and the WP article body.
    """
    return (
        s.lower()
        .replace('\u2018', "'").replace('\u2019', "'")   # curly single quotes
        .replace('\u201c', '"').replace('\u201d', '"')   # curly double quotes
        .replace('\u2013', '-').replace('\u2014', '-')   # en/em dashes
        .replace('\ufffd', "'")                          # replacement char
    )


def _text_pos_to_html_pos(html: str, text_target: int) -> int:
    """
    Map a plain-text character position to the corresponding index in an HTML
    string.  Tags are zero-width; HTML entities count as one character.
    """
    text_count = 0
    i = 0
    while i < len(html) and text_count < text_target:
        if html[i] == '<':
            close = html.find('>', i)
            i = close + 1 if close >= 0 else len(html)
        elif html[i] == '&':
            semi = html.find(';', i)
            i = semi + 1 if semi >= 0 else i + 1
            text_count += 1
        else:
            text_count += 1
            i += 1
    return i


def _split_fade_paragraph(el):
    """
    Split a BeautifulSoup block element at the sentence boundary closest to
    50 % of its plain text, for the light → medium fade effect.

    Returns (first_half_inner_html, second_half_inner_html).
    Falls back to the nearest word boundary if no sentence boundary exists.
    """
    inner_html = el.decode_contents()
    plain_text = el.get_text()
    if not plain_text.strip():
        return inner_html, ''

    mid = len(plain_text) // 2

    # Prefer sentence-ending punctuation followed by whitespace or end-of-string
    sentence_ends = [m.end() for m in re.finditer(r'[.!?](?:\s|$)', plain_text)]
    if sentence_ends:
        split_pos = min(sentence_ends, key=lambda p: abs(p - mid))
    else:
        # Fall back to word boundary (end of a whitespace run)
        word_ends = [m.end() for m in re.finditer(r'\S+\s*', plain_text)]
        if word_ends:
            split_pos = min(word_ends, key=lambda p: abs(p - mid))
        else:
            split_pos = mid

    html_pos = _text_pos_to_html_pos(inner_html, split_pos)
    return inner_html[:html_pos].rstrip(), inner_html[html_pos:].lstrip()


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


# ── Letter-spacing fix ────────────────────────────────────────────────────────

def fix_letter_spacing(html: str) -> str:
    """Remove letter-spacing: -0.8px from all inline styles and CSS rules."""
    # Inline styles: " letter-spacing: -0.8px;" or "letter-spacing:-0.8px;"
    html = re.sub(r'\s*letter-spacing\s*:\s*-0\.8px\s*;?', '', html)
    return html


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

    # 7b. Gmail iOS u+#body CSS injection — belt-and-suspenders for link spans
    html = _inject_gmail_ios_css(html)

    # 8. Iterable height fix (regex on string)
    html = _fix_iterable_heights(html)

    return html


def _apply_link_fixes(html: str) -> str:
    """
    For every <a href> in the HTML:
      - Ensure it has color and text-decoration inline styles.
      - Wrap its content in a <span> with those same styles.

    This is the Gmail iOS workaround: Gmail iOS strips all inline styles from
    <a> tags but respects styles on child elements, so the span preserves the
    appearance.

    We intentionally do NOT add font-size:inherit to <a> tags: on older iOS
    Mail, explicit 'inherit' on an <a> tag can resolve to a system default
    small size rather than the parent paragraph's computed size.  Natural CSS
    inheritance (no declaration) is more reliable, and the email templates
    already have .tablebox a { font-size:16px !important } as a backstop for
    Apple Mail.  When a link already has an explicit px font-size we copy it
    onto the span so it survives Gmail's style stripping.

    'already_fixed' only fires when the span wrapper already carries link
    styles (color present), not just any italic/bold span from em→span
    conversion — those spans need the wrapper too.
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

        # Only skip if the content span already carries the actual link styles
        # with an explicit font-size — not just a formatting span (italic/bold)
        # and not a span that has color+text-dec but is missing font-size.
        _span_style_m = re.match(
            r'^\s*<span\b[^>]*\bstyle\s*=\s*"([^"]*)"', content, re.I
        )
        _span_style = _span_style_m.group(1) if _span_style_m else ''
        already_fixed = bool(
            _span_style
            and re.search(r'\bcolor\s*:', _span_style, re.I)
            and re.search(r'\bfont-size\s*:', _span_style, re.I)
        )

        # Already complete — don't double-process
        if has_color and has_text_dec and already_fixed:
            return m.group(0)

        # Build the styles missing from the <a> tag (no font-size:inherit —
        # natural inheritance is more reliable on older iOS Mail)
        add_parts = []
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

        # Build the span's style — copy explicit font-size if present, but do
        # not synthesise font-size:inherit (same reasoning as above).
        merged = add_str + cur_style
        fz_m  = re.search(r'font-size\s*:\s*([^;]+)',       merged, re.I)
        c_m   = re.search(r'\bcolor\s*:\s*([^;]+)',          merged, re.I)
        td_m  = re.search(r'text-decoration\s*:\s*([^;]+)',  merged, re.I)

        # Determine font-size for the span:
        #   1. Use the link's own font-size if it has one
        #   2. Otherwise, look at the nearest parent element's font-size
        #      (scan backwards from the <a> tag for a font-size declaration)
        #   3. Fall back to 16px (article body default)
        if fz_m:
            span_fz = fz_m.group(1).strip()
        else:
            # Scan backwards in the HTML from this <a> tag for the nearest
            # parent's font-size (e.g. the containing <p style="font-size:14px">)
            preceding = html[:m.start()]
            parent_fz_matches = re.findall(
                r'font-size\s*:\s*(\d+px)', preceding, re.I
            )
            if parent_fz_matches:
                span_fz = parent_fz_matches[-1]
            else:
                span_fz = '16px'

        span_parts = [
            f"font-size:{span_fz}",
            f"color:{c_m.group(1).strip() if c_m else '#000000'}",
            f"text-decoration:{td_m.group(1).strip() if td_m else 'underline'}",
        ]
        span_style = ';'.join(span_parts) + ';'

        new_content = content if already_fixed else f'<span style="{span_style}">{content}</span>'
        return f'<a{new_attrs}>{new_content}</a>'

    return re.sub(r'<a\b([^>]*)>([\s\S]*?)</a>', fix_link, html, flags=re.IGNORECASE)


def _inject_gmail_ios_css(html: str) -> str:
    """
    Gmail on iOS injects a bare <u></u> element adjacent to the email body,
    which makes the 'u + #body' CSS selector match ONLY in Gmail iOS — other
    email clients ignore it entirely.

    We use that selector to force font-size and font-family on:
      1. <a> tags inside .tablebox (ensures the anchor itself is 16px)
      2. All <span> tags inside .tablebox <p> and <li> elements — covers
         link-fix spans, bold spans, italic spans, and any other formatted
         inline elements

    This is a belt-and-suspenders fallback for cases where Gmail iOS fails to
    inherit font-size/family through spans (observed in some app versions for
    both link spans and plain bold/italic formatting spans).

    The rules target .tablebox only, so headings (Lora), subtitle lines, and
    article-card title links (outside .tablebox) are not affected.
    """
    gmail_css = (
        "\n/* Gmail iOS: fix font-size/family on all .tablebox / .table-box spans */\n"
        "u + #body .tablebox a,"
        "u + #body .table-box a{font-size:16px!important}\n"
        "u + #body .tablebox li,"
        "u + #body .table-box li{font-size:16px!important}\n"
        "u + #body .tablebox p span,"
        "u + #body .tablebox li span,"
        "u + #body .table-box p span,"
        "u + #body .table-box li span{"
        "font-size:16px!important;"
        "font-family:'DM Sans',Arial,Helvetica,sans-serif!important"
        "}\n"
    )
    # Ensure <body> has id="body" so the selector can match
    html = re.sub(
        r'<body\b(?![^>]*\bid\s*=)([^>]*)>',
        r'<body id="body"\1>',
        html,
        count=1,
        flags=re.IGNORECASE,
    )
    # Append CSS inside the first <style> block
    html = html.replace('</style>', gmail_css + '</style>', 1)
    return html


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
