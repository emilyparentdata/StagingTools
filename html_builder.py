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
    "font-size: 18px; line-height: 32px; color: #000000;"
)

# ── Shared mobile CSS (injected at build time into every template) ───────────

SHARED_MOBILE_CSS = (
    "@media only screen and (max-width:480px){\n"
    ".email-container{width:100%!important;min-width:100%!important}\n"
    ".fluid{max-width:100%!important;height:auto!important;margin-left:auto!important;margin-right:auto!important}\n"
    ".stack-column,.stack-column-center{display:block!important;width:100%!important;max-width:100%!important;direction:ltr!important;padding-left:0!important;padding-right:0!important}\n"
    ".center-on-mobile{text-align:center!important}\n"
    ".welcome-message{font-size:14px!important;line-height:20px!important;padding:8px 12px!important}\n"
    ".welcome-message a,.welcome-message a span{font-size:14px!important;line-height:20px!important}\n"
    ".sub-text{font-size:16px!important}\n"
    ".mobile-padding{padding:12px 0px!important}\n"
    ".mobile-hide{display:none!important}\n"
    ".mobile-show{display:block!important;max-height:none!important}\n"
    ".headline-mobile{font-size:32px!important;line-height:36px!important;letter-spacing:-1.6px!important;padding:0px 12px!important}\n"
    ".upgrade-headline-mobile{font-size:30px!important;line-height:36px!important;letter-spacing:-1.5px!important}\n"
    ".logo-mobile{width:123px!important;height:36px!important}\n"
    ".button-mobile{width:250px!important;padding:19px 27px!important}\n"
    ".subscribe-btn-mobile a{padding:20px 24px!important;font-size:20px!important}\n"
    ".continue-reading-btn a{padding:16px!important;font-size:18px!important}\n"
    ".box-pad{padding:0px!important}\n"
    ".table-box-mobile{padding:24px 20px!important}\n"
    ".top-box-header-m{font-size:16px!important;line-height:22px!important}\n"
    ".no-top-pad{padding-top:0px!important}\n"
    "body{width:100%!important;min-width:100%!important}\n"
    "table[class=email-container]{width:100%!important}\n"
    "img{max-width:100%!important;height:auto!important}\n"
    ".news-top-link,.news-top-link a,.news-top-link span,.news-top-link span a{font-size:14px!important;padding:0 4px!important;letter-spacing:0!important}\n"
    ".price-image{width:100%!important;max-width:300px!important;height:auto!important}\n"
    ".pricing-container{width:100%!important;max-width:100%!important}\n"
    ".pricing-row{display:block!important;width:100%!important}\n"
    ".pricing-old,.pricing-new{display:block!important;width:100%!important;max-width:100%!important;text-align:center!important;padding:0 20px!important}\n"
    ".pricing-old{padding-bottom:16px!important}\n"
    ".pricing-new table{width:100%!important;max-width:100%!important}\n"
    ".pricing-new td{display:block!important;width:100%!important}\n"
    ".brush-bg{max-width:280px!important;width:100%!important;height:auto!important}\n"
    "}\n"
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
    elif template_type in ('paid_digest', 'free_digest'):
        _inject_paid_digest(soup, fields)
    elif template_type == 'pregnant_article':
        _inject_pregnant_article(soup, fields)
    elif template_type == 'pregnant_qa':
        _inject_pregnant_qa(soup, fields)
    elif template_type == 'latest_teaser':
        _inject_latest_teaser(soup, fields)
    elif template_type == 'toddler_article':
        _inject_toddler_article(soup, fields)
    elif template_type == 'toddler_qa':
        _inject_toddler_qa(soup, fields)
    elif template_type == 'toddler_digest':
        _inject_toddler_digest(soup, fields)
    elif template_type == 'simple':
        _inject_simple(soup, fields)
    elif template_type == 'marketing_flex':
        _inject_marketing_flex(soup, fields)
    elif template_type == 'baby_send_a':
        _inject_baby_send_a(soup, fields)
    elif template_type == 'baby_send_b':
        _inject_baby_send_b(soup, fields)
    elif template_type == 'baby_article':
        _inject_baby_article(soup, fields)
    elif template_type == 'baby_qa':
        _inject_baby_qa(soup, fields)
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

        # Add extra spacing before the author block
        style = article_tds[1].get('style', '')
        style = style.replace('padding: 0px 40px 20px', 'padding: 0px 40px 40px')
        article_tds[1]['style'] = style


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
<h3 class="h3-heading" style="margin: 0 0 8px 0; font-family: 'Lora', Georgia, serif; font-weight: bold; font-size: 18px; line-height: 24px; color: #000000;"><a href="{url}" style="color: #000000; text-decoration: none;">{title}</a></h3>
<p style="margin: 0; font-family: 'DM Sans', Arial, Helvetica, sans-serif; font-weight: 400; font-size: 16px; line-height: 24px; color: #000000;">{description}</p>
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


# ── Latest Teaser default intro ──────────────────────────────────────────────

_LATEST_TEASER_DEFAULT_INTRO = (
    '<p style="padding-bottom: 24px; margin: 0; '
    "font-family: 'DM Sans', Arial, Helvetica, sans-serif; "
    'font-weight: 400; font-style: italic; font-size: 16px; line-height: 24px; color: #000000;">'
    'Welcome to <strong>The Latest</strong>, where I break down current research and headlines '
    'in pregnancy, parenting, and personal health. If you\u2019ve seen a recent headline '
    '(parenting or otherwise) that you\u2019d like me to cover here, let me know by '
    '<a href="https://parentdata.typeform.com/to/NHBsKJHv" style="color: #000000; text-decoration: underline;">'
    'sharing your questions</a>.</p>\n'
    '<p style="padding-bottom: 24px; margin: 0; '
    "font-family: 'DM Sans', Arial, Helvetica, sans-serif; "
    'font-weight: 400; font-style: italic; font-size: 16px; line-height: 24px; color: #000000;">'
    'Did you know that ParentData offers customized weekly newsletters tailored to your exact '
    'life stage \u2014 from trying to conceive through toddlerhood? That means the data and '
    'guidance you\u2019re getting is always relevant to where you are right now.</p>'
)

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

        # If no intro_text provided, use the hardcoded default (raw HTML with link)
        if not intro_text.strip():
            for el in BeautifulSoup(_LATEST_TEASER_DEFAULT_INTRO, 'html.parser').find_all('p'):
                section4_td.append(el)
        else:
            # Italic intro — split on blank lines to support multiple paragraphs
            intro_style = (
                "padding-bottom: 24px; margin: 0; "
                "font-family: 'DM Sans', Arial, Helvetica, sans-serif; "
                "font-weight: 400; font-style: italic; font-size: 16px; line-height: 24px; color: #000000;"
            )
            intro_paras = [p.strip() for p in intro_text.split('\n\n') if p.strip()]
            if not intro_paras and intro_text.strip():
                intro_paras = [intro_text.strip()]
            for para in intro_paras:
                # Boldface "The Latest" wherever it appears in the intro
                para = re.sub(
                    r'\bThe Latest\b',
                    r'<strong>The Latest</strong>',
                    para,
                )
                # Link "sharing your questions" to the Typeform
                para = para.replace(
                    'sharing your questions',
                    '<a href="https://parentdata.typeform.com/to/NHBsKJHv"'
                    ' style="color: #000000; text-decoration: underline;">'
                    'sharing your questions</a>',
                )
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

        # Strip bottom margin from the last block so the section 4 td
        # padding-bottom alone controls the gap before the faded section.
        last_block = section4_td.find_all(True, recursive=False)
        if last_block:
            last = last_block[-1]
            style = last.get('style', '')
            if style:
                last['style'] = re.sub(r'margin:\s*0\s+0\s+24px\s+0', 'margin: 0', style)

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
    base = ("font-family: 'DM Sans', Arial, Helvetica, sans-serif; "
            "font-size: 18px; letter-spacing: 0; -webkit-text-size-adjust: 100%;")
    banner_p['style'] = f"margin: 0; color: #000000; {base} padding: 0 15px;"
    banner_p.clear()
    new_html = (
        f'<span style="color: #000000; {base}">Are you starting fertility treatment or no longer TTC? </span>'
        f'<a href="https://parentdata.org/account/#newsletter-settings-section"'
        f' style="color: #000000; {base} font-style: italic; text-decoration: underline;">'
        f'Update&nbsp;your&nbsp;newsletters.</a>'
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


def _update_bottom_line_by_color(soup, fields, color_match: str):
    """
    Replace the <ul> inside a colored bottom line box with the new content.

    color_match is a substring to find in the td's style attribute
    (e.g. 'a9b4ff' or 'rgb(208, 214, 252)').
    """
    bottom_line_html = fields.get('bottom_line_html', '')
    if not bottom_line_html:
        return

    target_td = None
    for td in soup.find_all('td'):
        if color_match in td.get('style', ''):
            target_td = td
            break
    if not target_td:
        return

    ul = target_td.find('ul')
    if ul:
        new_ul = BeautifulSoup(bottom_line_html, 'html.parser')
        ul.replace_with(new_ul)


def _update_fertility_bottom_line(soup, fields):
    """Replace the <ul> inside the purple (#a9b4ff) bottom line box."""
    _update_bottom_line_by_color(soup, fields, 'a9b4ff')


# ── Pregnant Article template injection ──────────────────────────────────────

def _inject_pregnant_article(soup, fields):
    """Inject all fields into the pregnancy article template."""
    _update_title(soup, fields)
    _update_pregnant_banner(soup, fields)
    _update_headline(soup, fields)
    _update_fertility_subtitle_author(soup, fields)
    _replace_fertility_body(soup, fields)
    _update_pregnant_bottom_line(soup, fields)
    _update_pregnant_comment_button(soup, fields)
    _update_copyright(soup)


def _update_pregnant_banner(soup, fields):
    """Set the week number in the 'You are X weeks pregnant!' banner."""
    banner_p = soup.find('p', class_='news-top-link')
    if not banner_p:
        return
    weeks = fields.get('weeks_pregnant', '')
    if not weeks:
        return
    base = ("font-family: 'DM Sans', Arial, Helvetica, sans-serif; "
            "font-size: 18px; letter-spacing: 0; -webkit-text-size-adjust: 100%;")
    banner_p['style'] = f"margin: 0; color: #000000; {base} padding: 0 15px;"
    banner_p.clear()
    new_html = (
        f'<span style="font-weight: bold; color: #000000; {base}">You are {weeks} weeks pregnant!</span> '
        f'<a href="https://parentdata.org/account/" style="color: #000000; {base} '
        f'font-style: italic; text-decoration: underline; font-weight: normal;" '
        f'title="Change Age">Change&nbsp;due&nbsp;date.</a>'
    )
    banner_p.append(BeautifulSoup(new_html, 'html.parser'))


def _update_pregnant_bottom_line(soup, fields):
    """
    Replace the <ul> inside the blue bottom line box.

    The pregnancy template has two tds with rgb(208, 214, 252): the top
    banner and the bottom line box.  The bottom line box has class
    'table-box-mobile', so we find by both color and class.
    """
    bottom_line_html = fields.get('bottom_line_html', '')
    if not bottom_line_html:
        return

    target_td = None
    for td in soup.find_all('td'):
        classes = td.get('class', [])
        if ('table-box-mobile' in classes
                and 'rgb(208, 214, 252)' in td.get('style', '')):
            target_td = td
            break
    if not target_td:
        return

    ul = target_td.find('ul')
    if ul:
        new_ul = BeautifulSoup(bottom_line_html, 'html.parser')
        ul.replace_with(new_ul)


def _update_pregnant_comment_button(soup, fields):
    """Set the LEAVE A COMMENT button href to article_url/#leave-comment."""
    article_url = fields.get('article_url', '')
    if not article_url:
        return
    comment_url = article_url.rstrip('/') + '/#leave-comment'
    for a in soup.find_all('a'):
        if 'LEAVE A COMMENT' in (a.get_text() or '').upper():
            a['href'] = comment_url
            break


# ── Pregnant Q&A template injection ───────────────────────────────────────────

def _inject_pregnant_qa(soup, fields):
    """Inject all fields into the pregnancy Q&A template."""
    _update_pregnant_banner(soup, fields)
    _update_qa_intro(soup, fields)
    _remove_unused_qa_pairs(soup, fields)
    _update_qa_pairs(soup, fields)
    _update_copyright(soup)


# ── Toddler Article template injection ───────────────────────────────────────

def _inject_toddler_article(soup, fields):
    """Inject all fields into the ToddlerData article template."""
    _update_title(soup, fields)
    _update_toddler_banner(soup, fields)
    _update_headline(soup, fields)
    _update_fertility_subtitle_author(soup, fields)
    _replace_fertility_body(soup, fields)
    _update_toddler_bottom_line(soup, fields)
    _update_discussion_questions(soup, fields)
    _update_copyright(soup)


# ── Toddler Q&A template injection ──────────────────────────────────────────

def _inject_toddler_qa(soup, fields):
    """Inject all fields into the ToddlerData Q&A template."""
    _update_toddler_banner(soup, fields)
    _update_qa_intro(soup, fields)
    _remove_unused_qa_pairs(soup, fields)
    _update_qa_pairs(soup, fields)
    _update_copyright(soup)


# ── Toddler Digest template injection ───────────────────────────────────────

def _inject_toddler_digest(soup, fields):
    """Inject all fields into the ToddlerData digest template."""
    _update_title(soup, fields)
    _update_toddler_banner(soup, fields)
    _update_headline(soup, fields)
    _update_digest_intro(soup, fields)
    _update_digest_cards(soup, fields)
    _update_win_of_week(soup, fields)
    _update_copyright(soup)


def _update_toddler_banner(soup, fields):
    """Set the months old in the 'Your child is X months old!' banner."""
    banner_p = soup.find('p', class_='news-top-link')
    if not banner_p:
        return
    months = fields.get('months_old', '')
    if not months:
        return
    # Ensure consistent margin on the <p>
    base = ("font-family: 'DM Sans', Arial, Helvetica, sans-serif; "
            "font-size: 18px; letter-spacing: 0; -webkit-text-size-adjust: 100%;")
    banner_p['style'] = f"margin: 0; color: #000000; {base} padding: 0 15px;"
    banner_p.clear()
    new_html = (
        f'<span style="font-weight: bold; color: #000000; {base}">Your child is {months} months old!</span> '
        f'<a href="https://parentdata.org/account/" style="color: #000000; {base} '
        f'font-style: italic; text-decoration: underline; font-weight: normal;" '
        f'title="Change Age">Change&nbsp;age?</a>'
    )
    banner_p.append(BeautifulSoup(new_html, 'html.parser'))


def _update_toddler_bottom_line(soup, fields):
    """Replace the <ul> inside the pink (#e0a9ca) bottom line box."""
    bottom_line_html = fields.get('bottom_line_html', '')
    if not bottom_line_html:
        return

    target_td = None
    for td in soup.find_all('td'):
        classes = td.get('class', [])
        if ('table-box-mobile' in classes
                and 'e0a9ca' in td.get('style', '')):
            target_td = td
            break
    if not target_td:
        return

    ul = target_td.find('ul')
    if ul:
        new_ul = BeautifulSoup(bottom_line_html, 'html.parser')
        ul.replace_with(new_ul)


def _update_discussion_questions(soup, fields):
    """
    Replace the discussion questions in the pink card.

    Finds the section by img[alt="Discussion Questions"], then locates the
    pink card table (background-color: #edc0db; border-radius: 20px) and
    replaces its <p> tags with the actual questions.
    """
    questions = fields.get('discussion_questions', [])
    if not questions:
        return

    dq_img = soup.find('img', attrs={'alt': 'Discussion Questions'})
    if not dq_img:
        return

    # The pink card is a sibling or nearby table with #edc0db background
    dq_section = dq_img.find_parent('table', role='presentation')
    if not dq_section:
        return

    # Find the pink card table within the section
    pink_card = None
    for table in dq_section.find_all('table'):
        style = table.get('style', '')
        if '#edc0db' in style and 'border-radius' in style:
            pink_card = table
            break
    if not pink_card:
        return

    # Find the td containing the question <p> tags
    question_td = pink_card.find('td')
    if not question_td:
        return

    # Clear existing questions
    question_td.clear()

    # Insert numbered questions
    for i, q in enumerate(questions):
        is_last = i == len(questions) - 1
        margin = '0' if is_last else '0 0 4px 0'
        q_text = _smart_quotes(_escape_attr(q))
        new_p = BeautifulSoup(
            f'<p style="margin: {margin}; font-family: \'DM Sans\', Arial, Helvetica, sans-serif; '
            f'font-weight: normal; font-size: 16px; line-height: 24px; text-align: left; color: #000000;">'
            f'{i + 1}. {q_text}</p>',
            'html.parser',
        )
        question_td.append(new_p)


def _remove_unused_qa_pairs(soup, fields):
    """
    Remove the 3rd Question/Answer pair if only 2 Q&As are provided.

    Uses _outer_email_tr() on the 3rd Question and 3rd Answer img tags
    to locate and decompose their outer <tr> rows.
    """
    qa3 = fields.get('qa3', {})
    if qa3 and (qa3.get('question_text') or qa3.get('answer_html')):
        return  # qa3 has content — keep all 3 pairs

    question_imgs = soup.find_all('img', attrs={'alt': 'Question'})
    answer_imgs = soup.find_all('img', attrs={'alt': 'Answer'})

    # Remove 3rd question row
    if len(question_imgs) >= 3:
        outer_tr = _outer_email_tr(question_imgs[2], soup)
        if outer_tr:
            outer_tr.decompose()

    # Remove 3rd answer row
    if len(answer_imgs) >= 3:
        outer_tr = _outer_email_tr(answer_imgs[2], soup)
        if outer_tr:
            outer_tr.decompose()


def _update_win_of_week(soup, fields):
    """
    Update the Win of the Month quote and attribution.

    The quote lives in td.win-quote-cell (two <p> tags: quote + attribution).
    """
    win_text = fields.get('win_text', '')
    win_attribution = fields.get('win_attribution', '')

    quote_td = soup.find('td', class_='win-quote-cell')
    if not quote_td:
        return

    paragraphs = quote_td.find_all('p')
    if paragraphs and win_text:
        paragraphs[0].clear()
        paragraphs[0].append(NavigableString(f'\u201c{win_text}\u201d'))

    if len(paragraphs) >= 2 and win_attribution:
        paragraphs[1].clear()
        paragraphs[1].append(NavigableString(f'\u2014{win_attribution}'))


# ── Baby template injection ─────────────────────────────────────────────────

def _update_baby_banner(soup, fields):
    """Set the age in the 'Your baby is X.' banner."""
    banner_p = soup.find('p', class_='news-top-link')
    if not banner_p:
        return
    age_text = fields.get('age_text', '')
    if not age_text:
        return
    age_text_lower = age_text.lower()
    base = ("font-family: 'DM Sans', Arial, Helvetica, sans-serif; "
            "font-size: 18px; letter-spacing: 0; -webkit-text-size-adjust: 100%;")
    banner_p['style'] = f"margin: 0; color: #000000; {base} padding: 0 15px;"
    banner_p.clear()
    new_html = (
        f'<span style="font-weight: bold; color: #000000; {base}">Your baby is {age_text_lower}!</span> '
        f'<a href="https://parentdata.org/account/" style="color: #000000; {base} '
        f'font-style: italic; text-decoration: underline; font-weight: normal;" '
        f'title="Change Age">Change&nbsp;age?</a>'
    )
    banner_p.append(BeautifulSoup(new_html, 'html.parser'))


# ── Baby Send A ─────────────────────────────────────────────────────────────

def _inject_baby_send_a(soup, fields):
    """Inject all fields into the BabyData Send A template."""
    _update_title(soup, fields)
    _update_baby_banner(soup, fields)
    _update_headline(soup, fields)
    _inject_baby_send_a_intro(soup, fields)
    _inject_baby_send_a_sections(soup, fields)
    _update_copyright(soup)


def _inject_baby_send_a_intro(soup, fields):
    """Replace the intro text (p.sub-text elements) in Baby Send A."""
    intro_text = fields.get('intro_text', '')
    if not intro_text:
        return
    # Find p.sub-text elements (the intro paragraphs below headline)
    sub_texts = soup.find_all('p', class_='sub-text')
    if not sub_texts:
        return
    paragraphs = [p.strip() for p in intro_text.split('\n\n') if p.strip()]
    # Replace first p.sub-text with new content, remove extras
    base_style = sub_texts[0].get('style', '')
    parent = sub_texts[0].parent
    for st in sub_texts:
        st.decompose()
    for para_text in paragraphs:
        new_p = soup.new_tag('p', **{'class': 'sub-text', 'style': base_style})
        # Check for bold wrapping like **text**
        if para_text.startswith('**') and para_text.endswith('**'):
            strong = soup.new_tag('strong')
            strong.append(NavigableString(para_text[2:-2]))
            new_p.append(strong)
        else:
            new_p.append(NavigableString(para_text))
        parent.append(new_p)


def _inject_baby_send_a_sections(soup, fields):
    """Populate the variable content sections of Baby Send A."""
    # Q&A bubble pair
    qa_pairs = fields.get('qa_pairs', [])
    if qa_pairs:
        # Find the cream section with bubble divs
        for td in soup.find_all('td', class_='table-box-mobile'):
            if '#fffcee' in (td.get('style') or ''):
                # Find question bubble (border-radius: 50px 0px)
                q_div = td.find('div', style=re.compile(r'50px 0px 50px 50px'))
                if q_div:
                    q_p = q_div.find('p')
                    if q_p and qa_pairs:
                        q_p.clear()
                        q_p.append(NavigableString(qa_pairs[0].get('question', '')))
                # Find answer bubble (border-radius: 0px 50px)
                a_div = td.find('div', style=re.compile(r'0px 50px 50px 50px'))
                if a_div:
                    a_p = a_div.find('p')
                    if a_p and qa_pairs:
                        a_p.clear()
                        a_p.append(NavigableString(qa_pairs[0].get('answer', '')))
                break

    # Petey CTA URL (the "Ask Petey" button in the #a9ddf3 section)
    petey_url = fields.get('petey_cta_url', '')
    if petey_url:
        for td in soup.find_all('td', class_='table-box-mobile'):
            if '#a9ddf3' in (td.get('style') or ''):
                ask_a = td.find('a', string=re.compile(r'PETEY', re.I))
                if ask_a:
                    ask_a['href'] = petey_url
                break

    # Fact or Fiction
    fof = fields.get('fact_or_fiction', {})
    if fof:
        for td in soup.find_all('td', class_='table-box-mobile'):
            style = td.get('style') or ''
            if '#ffffff' in style or 'rgb(255, 255, 255)' in style:
                fof_img = td.find('img', alt=re.compile(r'fact', re.I))
                if fof_img:
                    h3 = td.find('h3')
                    if h3:
                        strong = h3.find('strong')
                        target = strong if strong else h3
                        target.clear()
                        target.append(NavigableString(fof.get('title', '')))
                    # Answer paragraph (after h3)
                    desc_p = None
                    for p in td.find_all('p'):
                        p_style = p.get('style') or ''
                        if 'font-size: 16px' in p_style:
                            desc_p = p
                            break
                    if desc_p:
                        desc_p.clear()
                        desc_p.append(NavigableString(fof.get('answer', '')))
                    # READ MORE button URL
                    btn_div = td.find('div', style=re.compile(r'border-radius.*15px'))
                    if btn_div:
                        a = btn_div.find('a')
                        if a:
                            a['href'] = fof.get('url', '#')
                    break

    # Article card (the section with h2 uppercase header)
    card = fields.get('article_card', {})
    if card:
        for td in soup.find_all('td', class_='table-box-mobile'):
            h2 = td.find('h2')
            if h2 and h2.get_text().strip().isupper():
                # Update uppercase section header (e.g. "YOUR POSTPARTUM RECOVERY")
                section_title = card.get('title', '')
                if section_title:
                    h2.clear()
                    h2.append(NavigableString(section_title.upper()))
                # Image
                img = td.find('img')
                if img and card.get('image_url'):
                    img['src'] = card['image_url']
                    img['alt'] = card.get('subtitle', '') or card.get('title', '')
                # Subtitle (h3 below the image)
                h3 = td.find('h3')
                if h3:
                    h3.clear()
                    h3.append(NavigableString(card.get('subtitle', '')))
                # Description
                for p in td.find_all('p'):
                    if 'font-size: 16px' in (p.get('style') or ''):
                        p.clear()
                        p.append(NavigableString(card.get('description', '')))
                        break
                # Button URL
                btn_div = td.find('div', style=re.compile(r'border-radius.*15px'))
                if btn_div:
                    a = btn_div.find('a')
                    if a:
                        a['href'] = card.get('url', '#')
                break

    # Video card (side-by-side on desktop, stacks on mobile via .stack-column)
    video = fields.get('video_card', {})
    if video:
        for tr in soup.find_all('tr'):
            stack_tds = [td for td in tr.find_all('td', recursive=False)
                        if 'stack-column' in (td.get('class') or [])]
            if len(stack_tds) >= 2:
                # Left column: thumbnail
                left_td = stack_tds[0]
                thumb_img = left_td.find('img')
                if thumb_img and video.get('thumbnail_url'):
                    thumb_img['src'] = video['thumbnail_url']
                thumb_a = left_td.find('a')
                if thumb_a:
                    thumb_a['href'] = video.get('url', '#')
                # Right column: title + WATCH NOW
                right_td = stack_tds[1]
                h3 = right_td.find('h3')
                if h3:
                    h3.clear()
                    h3.append(NavigableString(video.get('title', '')))
                watch_a = right_td.find('a', string=re.compile(r'WATCH', re.I))
                if watch_a:
                    watch_a['href'] = video.get('url', '#')
                break


# ── Baby Send B ─────────────────────────────────────────────────────────────

def _inject_baby_send_b(soup, fields):
    """Inject all fields into the BabyData Send B template."""
    _update_title(soup, fields)
    _update_baby_banner(soup, fields)
    # Map intro_text → subtitle_lines for the shared subtitle helper
    if fields.get('intro_text') and not fields.get('subtitle_lines'):
        fields['subtitle_lines'] = [fields['intro_text']]
    _update_subtitle(soup, fields)
    _inject_baby_send_b_cards(soup, fields)
    _inject_baby_send_b_real_talk(soup, fields)
    _update_copyright(soup)


def _inject_baby_send_b_cards(soup, fields):
    """Update the 3 article cards in Baby Send B."""
    articles = fields.get('articles', [])
    # Find card rows by cream bg + h3
    card_tds = []
    for td in soup.find_all('td', class_='table-box-mobile'):
        if '#fffcee' in (td.get('style') or '') and td.find('h3'):
            card_tds.append(td)

    _desc_style = (
        "margin: 0; font-family: 'DM Sans', Arial, Helvetica, sans-serif; "
        "font-weight: 400; font-size: 16px; line-height: 24px; color: #000000;"
    )

    for td, article in zip(card_tds[:3], articles[:3]):
        # Image
        img = td.find('img')
        if img and article.get('image_url'):
            img['src'] = article['image_url']
            img['alt'] = _escape_attr(article.get('image_alt') or article.get('title', ''))
        # Title
        h3 = td.find('h3')
        if h3:
            h3.clear()
            h3.append(NavigableString(article.get('title', '')))
        # Description — replace the td that holds the bottom-line text
        # This td contains either a <p> or <p> + <ul>; replace all content
        # with a single styled <p> containing the description.
        desc_td = None
        for inner_td in td.find_all('td', style=re.compile(r'padding-bottom:\s*24px')):
            if inner_td.find('p', style=re.compile(r'font-size:\s*16px')):
                desc_td = inner_td
                break
        if desc_td:
            desc_td.clear()
            bullets = article.get('description_bullets', [])
            if bullets:
                # Render as "The bottom line:" label + bullet list
                label_p = BeautifulSoup(
                    f'<p style="{_desc_style}"><span style="font-weight:bold;">The bottom line:</span></p>',
                    'html.parser',
                )
                desc_td.append(label_p)
                li_html = ''.join(
                    f'<li style="{_desc_style}">{b}</li>' for b in bullets
                )
                ul = BeautifulSoup(f'<ul>{li_html}</ul>', 'html.parser')
                desc_td.append(ul)
            else:
                desc_text = article.get('description', '')
                new_p = BeautifulSoup(
                    f'<p style="{_desc_style}"><span style="font-weight:bold;">The bottom line: </span>{desc_text}</p>',
                    'html.parser',
                )
                desc_td.append(new_p)
        # Button URL
        for div in td.find_all('div', style=re.compile(r'border-radius.*15px')):
            a = div.find('a')
            if a:
                a['href'] = article.get('url', '#')
                break


def _inject_baby_send_b_real_talk(soup, fields):
    """Update the Real Talk section in Baby Send B.

    The template has two <p> tags inside the Real Talk td: a prompt
    paragraph and an italic quote paragraph.  We replace the prompt
    text and the italic quote separately.
    """
    prompt = fields.get('real_talk_prompt', '')
    quote = fields.get('real_talk_quote', '')
    if not prompt and not quote:
        return
    # Find the Real Talk section (blue bg with h3 "Real Talk")
    for td in soup.find_all('td', class_='table-box-mobile'):
        h3 = td.find('h3')
        if h3 and 'Real Talk' in h3.get_text():
            paragraphs = [
                p for p in td.find_all('p')
                if 'font-size: 18px' in (p.get('style') or '')
            ]
            if not paragraphs:
                break
            # First <p>: the prompt
            if prompt:
                paragraphs[0].clear()
                paragraphs[0].append(
                    BeautifulSoup(prompt, 'html.parser'),
                )
            # Second <p>: the italic quote
            if len(paragraphs) > 1 and quote:
                paragraphs[1].clear()
                # Wrap in <em> with a leading <br> to match template style
                paragraphs[1].append(
                    BeautifulSoup(
                        f'<em><br>{quote}</em>', 'html.parser',
                    ),
                )
            break


# ── Baby Article ────────────────────────────────────────────────────────────

def _inject_baby_article(soup, fields):
    """Inject all fields into the BabyData article template."""
    _update_title(soup, fields)
    _update_baby_banner(soup, fields)
    _update_headline(soup, fields)
    _update_baby_subtitle_author(soup, fields)
    _update_baby_bottom_line(soup, fields)
    _replace_baby_article_body(soup, fields)
    _update_copyright(soup)


def _update_baby_subtitle_author(soup, fields):
    """
    Update the subtitle and author line in the baby article template.

    The baby article template uses h3.subtext-mobile for the subtitle
    and p.subtext-mobile for the author name (not p.sub-text / top-box-header-m
    like the fertility template).
    """
    subtext_els = soup.find_all(class_='subtext-mobile')
    if not subtext_els:
        return

    # First subtext-mobile element: subtitle (h3)
    subtitle_lines = fields.get('subtitle_lines', [])
    subtitle_text = subtitle_lines[0] if subtitle_lines else ''
    if subtext_els:
        subtext_els[0].clear()
        subtext_els[0].append(NavigableString(subtitle_text))

    # Second subtext-mobile element: author name (p)
    if len(subtext_els) >= 2:
        author_name = fields.get('author_name', '')
        author_title = fields.get('author_title', '')
        author_line = f'{author_name}, {author_title}' if author_title else author_name
        subtext_els[1].clear()
        subtext_els[1].append(NavigableString(author_line))


def _update_baby_bottom_line(soup, fields):
    """Replace the <ul> inside the blue (#a9ddf3) bottom line box."""
    bottom_line_html = fields.get('bottom_line_html', '')
    if not bottom_line_html:
        return
    _LI_STYLE = (
        "font-family: 'DM Sans', Arial, Helvetica, sans-serif; "
        "font-weight: normal; font-size: 16px; line-height: 26px; "
        "color: rgb(0, 0, 0);"
    )
    # Find td with #a9ddf3 background that contains a <ul>
    for td in soup.find_all('td', class_='table-box-mobile'):
        style = td.get('style') or ''
        if 'a9ddf3' in style or 'rgb(169, 221, 243)' in style:
            ul = td.find('ul')
            if ul:
                new_ul = BeautifulSoup(bottom_line_html, 'html.parser')
                # Ensure every <li> is italic-styled
                for li in new_ul.find_all('li'):
                    li['style'] = _LI_STYLE
                ul.replace_with(new_ul)
                break


def _replace_baby_article_body(soup, fields):
    """Replace the article body content in the white body section."""
    body_html = fields.get('article_body_html', '')
    if not body_html:
        return
    # The article body is in td.table-box-mobile with white bg after the bottom line
    target_td = None
    for td in soup.find_all('td', class_='table-box-mobile'):
        style = td.get('style') or ''
        classes = td.get('class', [])
        if ('no-top-pad' in classes
                and ('#ffffff' in style or 'rgb(255,255,255)' in style.replace(' ', ''))):
            target_td = td
            break
    if not target_td:
        return
    target_td.clear()
    target_td.append(BeautifulSoup(body_html, 'html.parser'))


# ── Baby Q&A ────────────────────────────────────────────────────────────────

def _inject_baby_qa(soup, fields):
    """Inject all fields into the BabyData Q&A template."""
    _update_title(soup, fields)
    _update_baby_banner(soup, fields)
    _update_qa_intro(soup, fields)
    _update_baby_qa_pairs(soup, fields)
    _update_copyright(soup)


def _update_baby_qa_pairs(soup, fields):
    """Populate Q&A pairs in the baby Q&A template."""
    # Convert qa1/qa2 format to qa_pairs list
    qa_pairs = []
    for key in ('qa1', 'qa2'):
        qa = fields.get(key, {})
        if qa and (qa.get('question_text') or qa.get('answer_html')):
            qa_pairs.append({
                'question': qa.get('question_text', ''),
                'question_author': qa.get('question_author', ''),
                'answer_html': qa.get('answer_html', ''),
            })
    qa_author_line = fields.get('qa_author_line', '')

    question_imgs = soup.find_all('img', attrs={'alt': 'Question'})
    answer_imgs = soup.find_all('img', attrs={'alt': 'Answer'})

    # Remove excess Q&A pairs from template if fewer provided
    for i in range(len(qa_pairs), len(question_imgs)):
        outer_tr = _outer_email_tr(question_imgs[i], soup)
        if outer_tr:
            outer_tr.decompose()
    for i in range(len(qa_pairs), len(answer_imgs)):
        outer_tr = _outer_email_tr(answer_imgs[i], soup)
        if outer_tr:
            outer_tr.decompose()

    # Re-find after potential decomposition
    question_imgs = soup.find_all('img', attrs={'alt': 'Question'})
    answer_imgs = soup.find_all('img', attrs={'alt': 'Answer'})

    for i, pair in enumerate(qa_pairs):
        # Update question text
        if i < len(question_imgs):
            q_td = question_imgs[i].find_parent('td')
            if q_td:
                q_table = q_td.find_parent('table')
                if q_table:
                    # The question text is in a p after the image td
                    for td in q_table.find_all('td'):
                        p = td.find('p', style=re.compile(r'font-style.*italic'))
                        if p:
                            question_text = _escape_attr(pair.get('question', ''))
                            author = _escape_attr(pair.get('question_author', ''))
                            content = f'<span style="white-space: pre-wrap;">{question_text}</span>'
                            if author:
                                content += f'<br><br><span style="white-space: pre-wrap;">\u2014{author}</span>'
                            p.clear()
                            p.append(BeautifulSoup(content, 'html.parser'))
                            break

        # Update answer content
        if i < len(answer_imgs):
            a_img = answer_imgs[i]
            a_outer_td = a_img.find_parent('td', class_='table-box-mobile')
            if a_outer_td:
                answer_table = a_outer_td.find('table')
                if answer_table:
                    # Find the answer content td (contains multiple <p> tags)
                    for td in answer_table.find_all('td'):
                        paragraphs = td.find_all('p')
                        if len(paragraphs) >= 2:
                            # Clear all content after the Answer image
                            answer_html = pair.get('answer_html', '')
                            td.clear()
                            td.append(BeautifulSoup(answer_html, 'html.parser'))
                            break

    # Update attribution line in the last answer section
    if qa_author_line:
        # Find the last answer td and add/update attribution
        if answer_imgs:
            last_answer_td = answer_imgs[-1].find_parent('td', class_='table-box-mobile')
            if last_answer_td:
                # Look for existing attribution paragraph
                for p in last_answer_td.find_all('p'):
                    if "today" in p.get_text().lower() and "answers" in p.get_text().lower():
                        p.clear()
                        p.append(BeautifulSoup(f'<em>{qa_author_line}</em>', 'html.parser'))
                        return
                # If no existing attribution, add one
                answer_table = last_answer_td.find('table')
                if answer_table:
                    last_td = answer_table.find_all('td')[-1] if answer_table.find_all('td') else None
                    if last_td:
                        attr_p = BeautifulSoup(
                            f'<p style="font-family: \'DM Sans\', Arial, Helvetica, sans-serif; '
                            f'font-weight: normal; font-size: 16px; line-height: 24px; color: #000000;">'
                            f'<em>{qa_author_line}</em></p>',
                            'html.parser',
                        )
                        last_td.append(attr_p)


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
            else:
                title_p.clear()
                title_p.append(NavigableString(article.get('title', '')))

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
            name = sections[i].get('name', '')
            # Sentence case: "Big Kids" → "Big kids"
            if name:
                words = name.split()
                name = ' '.join(
                    [words[0].capitalize()] + [w.lower() for w in words[1:]]
                )
            h2.append(NavigableString(name))

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

        # The question text lives in italic <p> tag(s) inside a <td>.
        # Some templates split the question across multiple <p> + <br> elements,
        # so we clear the entire parent <td> and rebuild with a single <p>.
        italic_p = outer_tr.find('p', style=lambda s: 'italic' in (s or ''))
        if italic_p:
            question_td = italic_p.find_parent('td')
            if question_td:
                question_text = _escape_attr(qa.get('question_text', ''))
                author = _escape_attr(qa.get('question_author', ''))
                content = f'<span style="white-space: pre-wrap;">{question_text}</span>'
                if author:
                    content += f'<br><br><span style="white-space: pre-wrap;">\u2014{author}</span>'
                question_td.clear()
                new_p = BeautifulSoup(
                    f'<p style="margin: 0; font-family: \'DM Sans\', Arial, Helvetica, sans-serif; '
                    f'font-weight: normal; font-size: 18px; line-height: 24px; '
                    f'color: #000000; font-style: italic;">'
                    f'{content}</p>',
                    'html.parser',
                )
                question_td.append(new_p)

    qa_author_line = fields.get('qa_author_line', '').strip()

    for i, a_img in enumerate(answer_imgs):
        qa = fields.get(f'qa{i + 1}', {})
        outer_tr = _outer_email_tr(a_img, soup)
        if not outer_tr:
            continue

        tablebox_td = outer_tr.find('td', class_='tablebox')
        if tablebox_td:
            # Remove ALL divs (answer content + any hardcoded attribution)
            for old_div in tablebox_td.find_all('div'):
                old_div.decompose()
            answer_html = qa.get('answer_html', '')
            new_div = BeautifulSoup(f'<div>{answer_html}</div>', 'html.parser')
            tablebox_td.append(new_div)

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
    # Body replacement must run BEFORE pricing removal — it uses the
    # "UPGRADE NOW" link as an anchor to locate the body rows.
    _replace_marketing_body(soup, fields)
    _update_marketing_pricing(soup, fields)
    _update_marketing_author(soup, fields)
    _update_copyright(soup)


def _update_marketing_banner(soup, fields):
    """Update the blue pill bar text (p.welcome-message)."""
    p = soup.find('p', class_='welcome-message')
    if not p:
        return

    if fields.get('no_banner'):
        # Remove the entire banner row
        outer_tr = _outer_email_tr(p, soup)
        if outer_tr:
            outer_tr.decompose()
        return

    if fields.get('sponsor') == 'lemonade':
        # Replace with Lemonade sponsor ad — three <p> tags inside the same <td>
        td = p.parent
        td.clear()
        lemonade_html = (
            '<p class="welcome-message" style="margin: 0; font-family: \'DM Sans\', Arial, Helvetica, sans-serif; font-weight: 300; font-style: italic; font-size: 18px; line-height: 32px; letter-spacing: -0.9px; color: #000000;">'
            "Today's newsletter is free in full, thanks to:</p>"
            '<p class="welcome-message" style="margin: 0; font-family: \'DM Sans\', Arial, Helvetica, sans-serif; font-weight: 300; font-style: italic; font-size: 18px; line-height: 32px; letter-spacing: -0.9px; color: #000000;">'
            '<a href="https://go.lemonade.com/visit/?bta=39304&amp;brand=pet" style="color: #000000; text-decoration: underline; display: block;" title="Image link">'
            '<img alt="Lemonade" class="fluid" height="150" '
            'src="https://library.iterable.com/3244/21559/a7895fde09ea49398700709fce8e51a2-logo_dark_2.png" '
            'style="width: 192px; max-width: 330px; height: 43px; display: block; border-radius: 12px; margin-left: auto; margin-right: auto;" width="330">'
            '</a></p>'
            '<p class="welcome-message" style="margin: 0; font-family: \'DM Sans\', Arial, Helvetica, sans-serif; font-weight: 300; font-style: italic; font-size: 18px; line-height: 32px; letter-spacing: -0.9px; color: #000000;">'
            '&nbsp;Everyone in your family deserves protection &ndash; pets included. '
            '<span style="color: rgb(0, 0, 0);">Pet insurance from $10/month</span>.<br>'
            '<a href="https://go.lemonade.com/visit/?bta=39304&amp;brand=pet" style="color: #000000; text-decoration: underline; font-size: 18px; font-weight: 300; font-style: italic; font-family: \'DM Sans\', Arial, Helvetica, sans-serif;">'
            '<span style="font-size: 18px; color: #000000; text-decoration: underline; font-weight: 300; font-style: italic;">Get your free quote today!</span></a></p>'
        )
        td.append(BeautifulSoup(lemonade_html, 'html.parser'))
        return

    p.clear()
    p.append(NavigableString(fields.get('banner_text', "It's the final day of your trial!")))


def _update_marketing_intro(soup, fields):
    """Replace the intro tablebox paragraphs with CSV-sourced text and discount link."""
    intro_td = soup.find('td', class_='tablebox')
    if not intro_td:
        return

    if fields.get('no_intro'):
        # Remove the entire intro section (outer <tr> containing the tablebox)
        intro_tr = intro_td.find_parent('tr', style=re.compile(r'height:\s*auto'))
        if intro_tr:
            intro_tr.decompose()
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

    # When the banner is hidden, add a separator line after the intro
    if fields.get('no_banner'):
        hr_html = '<hr style="border: none; border-top: 1px solid #e0e0e0; margin: 8px 0 24px 0;"/>'
        intro_td.append(BeautifulSoup(hr_html, 'html.parser'))


def _update_marketing_pricing(soup, fields):
    """Update the old (strikethrough) price, new price, and UPGRADE NOW button href."""
    if fields.get('no_discount'):
        # Remove the entire cream-background upgrade section
        old_price_td = soup.find('td', class_='pricing-old')
        if old_price_td:
            upgrade_tr = old_price_td.find_parent('tr', style=re.compile(r'height:\s*auto'))
            if upgrade_tr:
                upgrade_tr.decompose()
        return

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
    return inner_html[:html_pos], inner_html[html_pos:].lstrip()


def _escape_attr(value: str) -> str:
    """Escape a string for safe use in an HTML attribute value."""
    return value.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')


def _smart_quotes(text: str) -> str:
    """Convert straight quotes to curly/smart quotes for email HTML.

    Expects text that has already been HTML-escaped (& → &amp;, etc.)
    so straight quotes are the only remaining quote characters.
    """
    LDQUO = '\u201c'  # "
    RDQUO = '\u201d'  # "
    LSQUO = '\u2018'  # '
    RSQUO = '\u2019'  # '

    # Double quotes: &quot; from _escape_attr
    text = re.sub(r'&quot;(\S)', lambda m: LDQUO + m.group(1), text)
    text = re.sub(r'(\S)&quot;', lambda m: m.group(1) + RDQUO, text)
    text = text.replace('&quot;', RDQUO)

    # Apostrophes (it's, don't, they're)
    text = re.sub(r"(\w)'(\w)", lambda m: m.group(1) + RSQUO + m.group(2), text)
    # Single quotes
    text = re.sub(r"'(\S)", lambda m: LSQUO + m.group(1), text)
    text = re.sub(r"(\S)'", lambda m: m.group(1) + RSQUO, text)
    text = text.replace("'", RSQUO)

    return text


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
            f' style="width: 100%; max-width: 552px; height: auto; display: block;">'
            f'</div>'
        )

    return re.sub(r'\[\[GRAPH_(\d+)\]\]', replace_graph, html)


# ── Simple email injection ─────────────────────────────────────────────────────

_SIMPLE_P_STYLE = (
    "font-family: 'DM Sans', Arial, Helvetica, sans-serif; font-weight: normal; "
    "font-size: 16px; line-height: 22px; color: #000000;"
)

_SIMPLE_A_STYLE = (
    "color: #054f8b; text-decoration: underline; "
    "font-family: 'DM Sans', Arial, Helvetica, sans-serif;"
)


def _inject_simple(soup, fields):
    """Inject content into the simple email template."""
    # Update <title>
    if soup.title:
        soup.title.string = 'Simple Email - ParentData'

    # Pre-button content
    pre_td = soup.find('td', class_='simple-pre-button')
    if pre_td:
        pre_html = fields.get('pre_button_html', '')
        if pre_html:
            pre_td.clear()
            pre_td.append(BeautifulSoup(pre_html, 'html.parser'))

    # Post-button content
    post_td = soup.find('td', class_='simple-post-button')
    if post_td:
        post_html = fields.get('post_button_html', '')
        if post_html:
            post_td.clear()
            post_td.append(BeautifulSoup(post_html, 'html.parser'))

    # Mammoth outputs bare <p> and <a> tags — apply standard email inline styles
    for td in [pre_td, post_td]:
        if not td:
            continue
        for p in td.find_all('p'):
            if not p.get('style'):
                p['style'] = _SIMPLE_P_STYLE
        for a in td.find_all('a'):
            if not a.get('style'):
                a['style'] = _SIMPLE_A_STYLE

    # Button text and URL
    btn_div = soup.find('div', class_='simple-button')
    if btn_div:
        btn_text = fields.get('button_text', '').strip()
        btn_url = fields.get('button_url', '').strip()
        a_tag = btn_div.find('a')
        if a_tag:
            if btn_url:
                a_tag['href'] = btn_url
            span = a_tag.find('span')
            if span and btn_text:
                span.string = btn_text.upper()

    # Copyright year
    copyright_p = soup.find('p', class_='simple-copyright')
    if copyright_p:
        year = datetime.now().year
        copyright_p.string = f'\u00a9 {year} ParentData. All rights reserved.'


# ── Marketing Flex template ───────────────────────────────────────────────────

_MFLEX_P_STYLE = (
    "font-family: 'DM Sans', Arial, Helvetica, sans-serif; "
    "font-weight: normal; font-size: 16px; line-height: 24px; "
    "color: #000000; margin-bottom: 16px;"
)
_MFLEX_A_STYLE = "color: #054f8b; text-decoration: underline; font-family: 'DM Sans', Arial, Helvetica, sans-serif;"


def _inject_marketing_flex(soup, fields):
    """Inject content into the marketing flex template."""
    # Title tag
    if soup.title:
        title = fields.get('title', '').strip() or 'ParentData'
        soup.title.string = f'{title} - ParentData'

    # Body text
    body_td = soup.find('td', class_='mflex-body')
    if body_td:
        body_html = fields.get('pre_button_html', '') or fields.get('article_body_html', '')
        if body_html:
            body_td.clear()
            body_td.append(BeautifulSoup(body_html, 'html.parser'))
        # Apply standard email inline styles to bare tags from mammoth
        for p in body_td.find_all('p'):
            if not p.get('style'):
                p['style'] = _MFLEX_P_STYLE
        for a in body_td.find_all('a'):
            if not a.get('style'):
                a['style'] = _MFLEX_A_STYLE

    # CTA Buttons
    _update_mflex_buttons(soup, fields)

    # Pricing section (pass soup for _outer_email_tr)
    _update_mflex_pricing(soup, fields)

    # Copyright year
    copyright_p = soup.find('p', class_='mflex-copyright')
    if copyright_p:
        year = datetime.now().year
        copyright_p.string = f'Copyright \u00a9 {year} ParentData, All rights reserved.'


def _update_mflex_buttons(soup, fields):
    """Build 1-3 CTA buttons from fields['buttons'] list."""
    buttons_td = soup.find('td', class_='mflex-buttons')
    if not buttons_td:
        return

    buttons = fields.get('buttons', [])
    if not buttons:
        # No buttons configured — remove the entire row
        tr = _outer_email_tr(buttons_td, soup)
        if tr:
            tr.decompose()
        return

    # Clear placeholder content
    buttons_td.clear()

    for btn in buttons:
        label = btn.get('label', 'LEARN MORE').strip()
        url = btn.get('url', '#').strip()
        style = btn.get('style', 'pill')  # 'pill' or 'minimal'
        color = btn.get('color', 'yellow')  # 'yellow' or 'white'

        bg = '#fceea9' if color == 'yellow' else '#ffffff'
        if style == 'pill':
            radius = '15px'
            shadow = '0px 4px 4px 0px rgba(0,0,0,0.25)'
        else:
            radius = '3px'
            shadow = 'none'

        btn_html = f'''<table align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="max-width: 400px; width: 100%;">
<tbody><tr><td align="center" style="padding: 8px 0px;">
<div class="subscribe-btn-mobile" style="display: inline-block; mso-hide: all; width: auto; border-radius: {radius}; background-color: {bg}; border: 2px solid #000000; box-shadow: {shadow};">
<a href="{url}" rel="noopener" style="display: block; padding: 16px 24px; font-family: 'DM Sans', Arial, Helvetica, sans-serif; font-weight: 800; font-size: 20px; line-height: 20px; letter-spacing: 0.24px; color: #000000; text-decoration: none; text-transform: uppercase; text-align: center; white-space: nowrap;" target="_blank"><span style="font-family: 'DM Sans', Arial, Helvetica, sans-serif; font-size: 20px; color: #000000; text-decoration: none;">{label.upper()}</span></a>
</div></td></tr></tbody></table>'''
        buttons_td.append(BeautifulSoup(btn_html, 'html.parser'))


def _update_mflex_pricing(soup, fields):
    """Handle the optional pricing section: remove it or populate cards."""
    pricing_td = soup.find('td', class_='mflex-pricing')
    if not pricing_td:
        return

    if not fields.get('show_pricing'):
        # Remove the entire pricing row
        tr = _outer_email_tr(pricing_td, soup)
        if tr:
            tr.decompose()
        return

    cards = fields.get('pricing_cards', [])
    mode = fields.get('pricing_mode', 'dual')

    # Card 1
    if cards and len(cards) >= 1:
        _populate_mflex_card(soup, 'mflex-card-1', cards[0])

    # Card 2 — remove if single mode
    card2_td = soup.find('td', class_='mflex-card-2')
    spacer_td = soup.find('td', class_='mflex-pricing-spacer')
    if mode == 'single':
        if card2_td:
            card2_td.decompose()
        if spacer_td:
            spacer_td.decompose()
        # Make card 1 full width
        card1_td = soup.find('td', class_='mflex-card-1')
        if card1_td:
            style = card1_td.get('style', '')
            style = re.sub(r'width\s*:\s*48%', 'width: 100%', style)
            style = re.sub(r'padding-right\s*:\s*2%', 'padding-right: 0', style)
            card1_td['style'] = style
    elif cards and len(cards) >= 2:
        _populate_mflex_card(soup, 'mflex-card-2', cards[1])


def _populate_mflex_card(soup, card_class, card_data):
    """Fill a pricing card's fields from card_data dict."""
    card_td = soup.find('td', class_=card_class)
    if not card_td:
        return

    plan_name = card_data.get('plan_name', '')
    old_price = card_data.get('old_price', '')
    new_price = card_data.get('new_price', '')
    badge = card_data.get('badge', '')
    cta_url = card_data.get('cta_url', '#')
    cta_text = card_data.get('cta_text', 'Subscribe')

    name_p = card_td.find('p', class_='mflex-plan-name')
    if name_p and plan_name:
        name_p.string = plan_name

    old_p = card_td.find('p', class_='mflex-old-price')
    if old_p:
        if old_price:
            old_p.string = old_price
        else:
            old_p.decompose()

    new_p = card_td.find('p', class_='mflex-new-price')
    if new_p and new_price:
        new_p.string = new_price

    per_unit_p = card_td.find('p', class_='mflex-per-unit')
    if per_unit_p:
        per_unit = card_data.get('per_unit', '')
        if per_unit:
            per_unit_p.string = per_unit
        else:
            per_unit_p.decompose()

    badge_div = card_td.find('div', class_='mflex-badge')
    if badge_div:
        if badge:
            badge_p = badge_div.find('p')
            if badge_p:
                badge_p.string = badge
        else:
            badge_div.decompose()

    cta_a = card_td.find('a', class_='mflex-card-cta')
    if cta_a:
        cta_a['href'] = cta_url
        span = cta_a.find('span')
        if span and cta_text:
            span.string = cta_text.upper()


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
     10. Strip white-space-collapse from inline styles
     11. Ensure <p> tags have bottom margin for paragraph spacing
     12. Replace empty <div></div> with visible spacers
    """
    soup = BeautifulSoup(html, 'html.parser')

    # 1–3. Semantic tags → inline-styled spans
    # Old iOS Mail doesn't inherit font-family through <span>, so we must set
    # it explicitly. Walk up to the nearest parent with a font-family, or
    # default to DM Sans.
    import re as _re_fix

    def _parent_font_family(tag):
        """Find font-family from the nearest ancestor's inline style."""
        for parent in tag.parents:
            ps = parent.get('style', '') if hasattr(parent, 'get') else ''
            m = _re_fix.search(r'font-family\s*:\s*([^;]+)', ps)
            if m:
                return m.group(1).strip()
        return "'DM Sans',Arial,Helvetica,sans-serif"

    def _parent_font_size(tag):
        """Find font-size from the nearest ancestor's inline style."""
        for parent in tag.parents:
            ps = parent.get('style', '') if hasattr(parent, 'get') else ''
            m = _re_fix.search(r'font-size\s*:\s*([^;]+)', ps)
            if m:
                return m.group(1).strip()
        return '16px'

    for tag in soup.find_all(['strong', 'b']):
        ff = _parent_font_family(tag)
        fz = _parent_font_size(tag)
        tag.name = 'span'
        tag['style'] = f'font-weight:bold;font-family:{ff};font-size:{fz};' + (tag.get('style') or '')

    for tag in soup.find_all(['em', 'i']):
        ff = _parent_font_family(tag)
        fz = _parent_font_size(tag)
        tag.name = 'span'
        tag['style'] = f'font-style:italic;font-family:{ff};font-size:{fz};' + (tag.get('style') or '')

    for tag in soup.find_all('u'):
        ff = _parent_font_family(tag)
        fz = _parent_font_size(tag)
        tag.name = 'span'
        tag['style'] = f'text-decoration:underline;font-family:{ff};font-size:{fz};' + (tag.get('style') or '')

    # 4–5. <img> fixes
    for img in soup.find_all('img'):
        style = img.get('style', '')
        if 'display' not in style.lower():
            # Some images should stay left-aligned (parent td has text-align:left)
            alt_lower = (img.get('alt') or '').lower()
            if alt_lower in ('footer logo', 'question', 'answer'):
                img['style'] = 'display:block;' + style
            else:
                img['style'] = 'display:block;margin:0 auto;' + style
        if not img.has_attr('alt'):
            img['alt'] = ''

    # 6. Remove <script> and <iframe>
    for tag in soup.find_all(['script', 'iframe']):
        tag.decompose()

    # 6a. Strip white-space-collapse from inline styles (unsupported in most
    #     email clients; causes missing paragraph breaks in some)
    for tag in soup.find_all(style=re.compile(r'white-space-collapse', re.I)):
        tag['style'] = re.sub(
            r'\s*white-space-collapse\s*:\s*[^;]+;?\s*', '', tag['style']
        )

    # 6b. Ensure <p> tags inside body content have a bottom margin so
    #     paragraphs don't collapse together in clients that strip defaults.
    #     Only targets <p> tags with an explicit inline style but no effective
    #     bottom spacing from margin shorthand, margin-bottom, or padding-bottom.
    for p in soup.find_all('p', style=True):
        # Skip header-area elements (subtitle, author line, welcome banner)
        p_classes = p.get('class', [])
        if 'sub-text' in p_classes or 'welcome-message' in p_classes or 'news-top-link' in p_classes:
            continue
        style = p.get('style', '')
        if re.search(r'\bpadding-bottom\s*:', style, re.I):
            continue
        if re.search(r'\bmargin-bottom\s*:', style, re.I):
            continue
        # Check margin shorthand — extract bottom value
        ms = re.search(r'\bmargin\s*:\s*([^;]+)', style, re.I)
        if ms:
            parts = ms.group(1).strip().split()
            # CSS margin: 1 val=all, 2=vert horiz, 3=top horiz bottom, 4=T R B L
            bottom = (
                parts[0] if len(parts) == 1 else
                parts[0] if len(parts) == 2 else  # vert = top & bottom
                parts[2] if len(parts) >= 3 else
                parts[0]
            )
            if bottom not in ('0', '0px', '0em'):
                continue  # has nonzero bottom margin already
            # Explicit margin:0 means spacing is intentional — don't override
            # (e.g. footer paragraphs where parent <td> handles spacing)
            continue
        p['style'] = style.rstrip('; ') + '; margin-bottom: 16px;'

    # 6c. Replace empty <div></div> spacers with a visible spacer
    for div in soup.find_all('div'):
        if not div.get_text(strip=True) and not div.find(True) and not div.get('style'):
            div['style'] = 'height:16px;line-height:16px;font-size:1px;'
            div.string = '\u00a0'

    # 9. no-top-pad class
    for td in soup.find_all('td'):
        classes = td.get('class', [])
        if 'table-box-mobile' not in classes or 'no-top-pad' in classes:
            continue
        style = td.get('style', '')
        if (re.search(r'\bpadding-top\s*:\s*0', style, re.I) or
                re.search(r'\bpadding\s*:\s*0px?\b', style, re.I)):
            td['class'] = classes + ['no-top-pad']

    # 10. Propagate parent font-size and font-family onto <a> tags that
    #     lack them.  This ensures _apply_link_fixes can create span
    #     wrappers with the correct px size, and also fixes non-Gmail
    #     clients (especially older iOS Mail) where the <a> tag's own
    #     inline font-size/family takes precedence.
    #     Skip links inside .news-top-link (responsive: 18px desktop,
    #     14px mobile) where locking in desktop size prevents mobile CSS
    #     from overriding on older iOS devices.
    for a_tag in soup.find_all('a', href=True):
        a_style = a_tag.get('style', '')
        if re.search(r'\bfont-size\s*:', a_style, re.I):
            continue  # already has font-size
        # Skip links inside .news-top-link (responsive size: 18px desktop, 14px mobile)
        if a_tag.find_parent(class_='news-top-link'):
            continue
        # Walk up ancestors looking for explicit inline font-size + font-family
        parent_size = None
        parent_family = None
        for parent in a_tag.parents:
            p_style = parent.get('style', '') if hasattr(parent, 'get') else ''
            if parent_size is None:
                fz_m = re.search(r'font-size\s*:\s*(\d+)px', p_style, re.I)
                if fz_m:
                    parent_size = int(fz_m.group(1))
            if parent_family is None:
                ff_m = re.search(r'font-family\s*:\s*([^;]+)', p_style, re.I)
                if ff_m:
                    parent_family = ff_m.group(1).strip()
            if parent_size is not None and parent_family is not None:
                break
        add_parts = []
        if parent_family is not None:
            add_parts.append(f"font-family:{parent_family};")
        if parent_size is not None:
            add_parts.append(f"font-size:{parent_size}px;")
        if add_parts:
            a_tag['style'] = ''.join(add_parts) + a_style

    html = str(soup)

    # 7. Gmail iOS link fix (regex on string — mirrors email-checker exactly)
    html = _apply_link_fixes(html)

    # 7a. Shared mobile CSS injection
    html = _inject_shared_mobile_css(html)

    # 7b. Gmail iOS u+#body CSS injection — belt-and-suspenders for link spans
    html = _inject_gmail_ios_css(html)

    # 8. Iterable height fix (regex on string)
    html = _fix_iterable_heights(html)

    # 9. Strip letter-spacing: -0.8px from all inline styles
    html = fix_letter_spacing(html)

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

        # Skip links inside .news-top-link — the banner link must stay
        # span-free so the underline doesn't break on mobile wrapping.
        preceding = html[:m.start()]
        # Find last opening <p or <td with news-top-link vs last closing </p> or </td>
        last_open = max(
            preceding.rfind('news-top-link'),
            -1
        )
        if last_open != -1:
            last_close_p = preceding.rfind('</p>', last_open)
            last_close_td = preceding.rfind('</td>', last_open)
            if last_close_p == -1 and last_close_td == -1:
                # Still inside the news-top-link element
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
        _has_span_color = bool(_span_style and re.search(r'\bcolor\s*:', _span_style, re.I))
        _has_span_fz    = bool(_span_style and re.search(r'\bfont-size\s*:', _span_style, re.I))
        _has_span_ff    = bool(_span_style and re.search(r'\bfont-family\s*:', _span_style, re.I))
        already_fixed = _has_span_color and _has_span_fz and _has_span_ff

        # Already complete — don't double-process
        if has_color and has_text_dec and already_fixed:
            return m.group(0)

        # Partial fix: span has color+font-size but missing font-family.
        # Patch font-family into the existing span instead of re-wrapping.
        if _has_span_color and _has_span_fz and not _has_span_ff:
            preceding_ff = re.findall(
                r'font-family\s*:\s*([^;]+)', html[:m.start()], re.I
            )
            patch_ff = preceding_ff[-1].strip() if preceding_ff else "'DM Sans',Arial,Helvetica,sans-serif"
            patched_content = re.sub(
                r'(<span\b[^>]*\bstyle\s*=\s*")',
                rf'\1font-family:{patch_ff};',
                content, count=1, flags=re.I
            )
            return f'<a{attrs}>{patched_content}</a>'

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

        # Determine font-family for the span — inherit from the <a> tag's
        # own style or from step 10's propagation; fall back to DM Sans.
        ff_m = re.search(r'font-family\s*:\s*([^;]+)', merged, re.I)
        if ff_m:
            span_ff = ff_m.group(1).strip()
        else:
            preceding_ff = re.findall(
                r'font-family\s*:\s*([^;]+)', html[:m.start()], re.I
            )
            span_ff = preceding_ff[-1].strip() if preceding_ff else "'DM Sans',Arial,Helvetica,sans-serif"

        span_parts = [
            f"font-size:{span_fz}",
            f"font-family:{span_ff}",
            f"color:{c_m.group(1).strip() if c_m else '#000000'}",
            f"text-decoration:{td_m.group(1).strip() if td_m else 'underline'}",
        ]
        span_style = ';'.join(span_parts) + ';'

        new_content = content if already_fixed else f'<span style="{span_style}">{content}</span>'
        return f'<a{new_attrs}>{new_content}</a>'

    return re.sub(r'<a\b([^>]*)>([\s\S]*?)</a>', fix_link, html, flags=re.IGNORECASE)


def _inject_shared_mobile_css(html: str) -> str:
    """
    Inject SHARED_MOBILE_CSS at the beginning of the first <style> block.

    Shared rules come BEFORE any template-specific @media rules, so
    template overrides win (later rule with same specificity + !important).
    Skips injection if the shared CSS is already present (idempotent).
    """
    # Detect by a unique rule that only appears in the shared block
    if '.price-image{width:100%' in html:
        return html
    return re.sub(
        r'(<style[^>]*>)',
        r'\1\n' + SHARED_MOBILE_CSS,
        html,
        count=1,
    )


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

    Also targets paid-digest .newsletter-card elements (h3, p, a) and
    h2.section-title headings to lock their font-size/family.
    """
    gmail_css = (
        "\n/* Gmail iOS: fix font-size/family on body text + article card spans */\n"
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
        "/* Gmail iOS: fix paid-digest article card fonts */\n"
        "u + #body .newsletter-card h3{"
        "font-size:20px!important;"
        "font-family:'Lora',Georgia,serif!important"
        "}\n"
        "u + #body .newsletter-card p{"
        "font-size:16px!important;"
        "font-family:'DM Sans',Arial,Helvetica,sans-serif!important"
        "}\n"
        "u + #body .newsletter-card p span{"
        "font-size:16px!important;"
        "font-family:'DM Sans',Arial,Helvetica,sans-serif!important"
        "}\n"
        "u + #body .newsletter-card a{"
        "font-size:13px!important;"
        "font-family:'DM Sans',Arial,Helvetica,sans-serif!important"
        "}\n"
        "u + #body .newsletter-card a span{"
        "font-size:13px!important;"
        "font-family:'DM Sans',Arial,Helvetica,sans-serif!important"
        "}\n"
        "u + #body h2.section-title{"
        "font-size:25px!important;"
        "font-family:'Lora',Georgia,serif!important"
        "}\n"
        "u + #body p.sub-text{"
        "font-size:18px!important;"
        "font-family:'DM Sans',Arial,Helvetica,sans-serif!important"
        "}\n"
        "u + #body p.sub-text.author-line{"
        "font-size:16px!important;"
        "font-family:'DM Sans',Arial,Helvetica,sans-serif!important"
        "}\n"
        "/* Gmail iOS: fix link sizes in welcome banner, headings + footer */\n"
        "u + #body .welcome-message a,"
        "u + #body .welcome-message a span{"
        "font-size:18px!important;"
        "font-family:'DM Sans',Arial,Helvetica,sans-serif!important"
        "}\n"
        "u + #body .h3-heading a,"
        "u + #body .h3-heading a span{"
        "font-size:18px!important;"
        "font-family:'Lora',Georgia,serif!important"
        "}\n"
        "/* Mobile: lock author font for iOS Mail */\n"
        "@media only screen and (max-width:480px){\n"
        "p.author-line{"
        "font-family:'DM Sans',Arial,Helvetica,sans-serif!important"
        "}\n"
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
    # Append CSS inside the first <style> block (skip if already present)
    if 'u + #body .tablebox a' in html:
        return html
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
