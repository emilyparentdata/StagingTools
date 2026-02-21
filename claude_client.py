"""
claude_client.py — Claude API calls for field extraction and body formatting.

Sends the full document text + mammoth HTML to Claude and returns a structured
dict with all metadata fields and properly inline-styled HTML for the email body.
"""

import json
import re
import anthropic

client = anthropic.Anthropic()
MODEL = 'claude-sonnet-4-6'

STYLE_GUIDE = """
EMAIL HTML INLINE STYLE REFERENCE
===================================
H1 heading:
  style="margin: 0 0 24px 0; font-family: 'Lora', Georgia, serif; font-weight: bold; font-size: 30px; line-height: 36px; letter-spacing: -1.2px; color: #000000;"

H2 heading:
  style="margin: 0 0 24px 0; font-family: 'Lora', Georgia, serif; font-weight: bold; font-size: 24px; line-height: 28px; letter-spacing: -1.2px; color: #000000;"

Regular paragraph (article body):
  style="margin: 0 0 24px 0; font-family: 'DM Sans', Arial, Helvetica, sans-serif; font-weight: 400; font-size: 16px; line-height: 24px; letter-spacing: -0.8px; color: #000000;"

Bold inline text within paragraph: use <strong> tag inside the <p>

Hyperlink inside article body:
  style="color: #054f8b; text-decoration: underline;"

List item <li>:
  style="font-family: 'DM Sans', Arial, Helvetica, sans-serif; font-weight: 400; font-size: 16px; line-height: 24px; letter-spacing: -0.8px; color: #000000;"

Welcome/intro section paragraphs (Emily's italicized intro text and newsletter announcements):
  style="padding-bottom: 24px; margin: 0; font-family: 'DM Sans', Arial, Helvetica, sans-serif; font-weight: 400; font-size: 16px; line-height: 24px; letter-spacing: -0.8px; color: #000000;"
  - Wrap italic text in <em>
  - Links within italic text: <a href="URL"><em>link text</em></a>

Author bio paragraph (Emily's plain-text intro of the guest author, not italic):
  Same style as welcome paragraphs above, but without <em> wrapper

Signature line "—Emily":
  Same style as welcome paragraphs above
"""


def extract_fields(raw_text: str, mammoth_html: str) -> dict:
    """
    Use Claude to extract all metadata fields and produce styled HTML.

    Returns:
        {
            title: str,
            subtitle_lines: list[str],
            author_name: str,
            author_title: str,
            topic_tags: list[str],
            welcome_html: str,
            article_body_html: str,
        }
    """
    prompt = f"""You are preparing a ParentData newsletter article for email staging.

Below is the raw text and HTML conversion of a Word document containing the article.

## RAW DOCUMENT TEXT:
{raw_text}

## MAMMOTH HTML CONVERSION:
{mammoth_html}

## STYLE GUIDE FOR EMAIL HTML:
{STYLE_GUIDE}

## YOUR TASK:
Extract all fields and produce properly formatted email HTML. Return a single JSON object with EXACTLY these keys:

- "title": The article title as a plain string.

- "subtitle_lines": Array of short subtitle strings. Usually 1–2 lines. Each line is a separate array element (no HTML).

- "author_name": Guest author's full name as a plain string. (If it's an Emily Oster article, use "Emily Oster".)

- "author_title": Guest author's professional title/credentials as a plain string.

- "topic_tags": Array of topic tag strings (e.g. ["Hormones", "Health and Wellness"]).

- "welcome_html": Emily's complete introductory section as HTML. This includes:
  1. Any italic newsletter intro paragraphs ("Welcome to The Latest..." etc.) — use <em> for italic text, and <a href="URL"><em>link text</em></a> for italic links.
  2. Any plain-text author bio paragraph Emily wrote introducing the guest author.
  3. Emily's "—Emily" sign-off paragraph.
  4. A <hr> tag at the very end (after the sign-off).
  Apply the welcome paragraph inline styles from the Style Guide to every <p> in this section.
  If there is no intro section (Emily wrote the whole article herself), return an empty string "".

- "article_body_html": The complete article body as HTML with inline styles from the Style Guide. Include:
  - H1 headings (use <h1> with the H1 style)
  - H2 headings (use <h2> with the H2 style)
  - Regular paragraphs (use <p> with the regular paragraph style)
  - Bold inline text uses <strong> inside <p>
  - Bullet lists as <ul><li style="...">...</li></ul> (apply li style to each li)
  - Hyperlinks with the link inline style
  Do NOT bold the first paragraph unless it was explicitly bold in the source document.
  Preserve ALL hyperlinks from the source document with their original href values.
  Convert special characters to their HTML entities or Unicode equivalents.
  Do NOT include Emily's welcome section here — only the guest author's article content.

GRAPH PLACEHOLDERS:
If the mammoth HTML contains [[GRAPH_1]], [[GRAPH_2]], etc., these are embedded
chart or graph images extracted from the Word document. Keep each placeholder
exactly as-is ([[GRAPH_1]], [[GRAPH_2]], ...) in the article_body_html at its
original position in the text — do not move, rename, or remove them. They will
be replaced with the actual hosted image URLs before the email is sent.

IMPORTANT:
- Return ONLY the raw JSON object. No markdown code fences, no explanation, no extra text.
- All HTML in the JSON values must be valid and properly escaped as a JSON string.
- Preserve special characters like em dashes (—), curly quotes, and non-breaking spaces correctly."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        messages=[{'role': 'user', 'content': prompt}],
    )

    text = response.content[0].text.strip()

    # Strip potential markdown code fences
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*\n?', '', text)
        text = re.sub(r'\n?```\s*$', '', text)

    return json.loads(text)
