# ParentData Email Staging Tool — User Guide

This tool turns a Word document, Google Doc, or published ParentData article into a finished, email-ready HTML file that can be imported directly into Iterable.

---

## Part 1: Getting Set Up (one-time only)

### Step 1 — Install Python

Python is the programming language the tool runs on. You only need to do this once.

**On a Mac:**

1. Open **Terminal** (press ⌘ Space, type "Terminal", hit Enter).
2. Paste this command and press Enter:
   ```
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
   This installs a package manager called Homebrew. Follow any prompts on screen (you may need to enter your Mac password).
3. Once Homebrew is installed, paste this and press Enter:
   ```
   brew install python
   ```
4. Verify it worked by typing `python3 --version` — you should see something like `Python 3.12.x`.

**On Windows:**

1. Go to [python.org/downloads](https://www.python.org/downloads/) in your browser.
2. Click the big yellow **Download Python** button.
3. Run the installer. **Important:** on the first screen of the installer, check the box that says **"Add Python to PATH"** before clicking Install.
4. Once installed, open **Command Prompt** (press the Windows key, type "cmd", hit Enter) and type `python --version`. You should see a version number.

---

### Step 2 — Get the tool files

If you don't already have the tool files on your computer, download them from GitHub:

1. Go to the repository in your browser.
2. Click the green **Code** button → **Download ZIP**.
3. Unzip the folder somewhere easy to find, like your Desktop or Documents.

---

### Step 3 — Get your API keys

The tool needs two sets of credentials to work:

**Anthropic API key** (powers the AI that reads and formats articles):

1. Go to [console.anthropic.com](https://console.anthropic.com) and sign in.
2. Click **API Keys** in the left sidebar.
3. Click **Create Key**, give it a name like "Staging Tool", and copy the key. It starts with `sk-ant-`.
4. Keep this somewhere safe — you won't be able to see it again after closing the page.

**WordPress credentials** (needed to pull articles from parentdata.org):

1. Log in to [parentdata.org/wp-admin](https://parentdata.org/wp-admin).
2. In the left sidebar, go to **Users → Your Profile**.
3. Scroll all the way down to the **Application Passwords** section.
4. Type any name in the box (e.g., "Staging Tool") and click **Add New Application Password**.
5. Copy the generated password (it looks like `xxxx xxxx xxxx xxxx xxxx xxxx`). You won't be able to see it again.
6. Your WordPress username is the one you use to log in to wp-admin.

---

### Step 4 — Create the `.env` file

The `.env` file is a small text file where you store your credentials so the tool can find them.

1. Inside the `staging-tool` folder, find the file called `.env.example`.
2. Make a copy of it and rename the copy to `.env` (no `.example` at the end).
3. Open `.env` in a text editor (Notepad on Windows, TextEdit on Mac, or any editor you have).
4. Replace the placeholder text with your actual credentials:

```
ANTHROPIC_API_KEY=sk-ant-your-actual-key-here

WP_APP_USERNAME=your-wordpress-username
WP_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
```

Save the file. Make sure there are no extra spaces or quotes around the values.

---

### Step 5 — Install the tool's dependencies

The tool uses several Python libraries. You only need to install them once.

1. Open Terminal (Mac) or Command Prompt (Windows).
2. Navigate to the `staging-tool` folder. Type `cd ` (with a space), then drag the `staging-tool` folder into the window — the path will fill in automatically. Press Enter.
3. Run:
   ```
   python -m pip install -r requirements.txt
   ```
   Wait for it to finish. You'll see a lot of text scroll by — that's normal.

---

### Step 6 — Start the tool

Every time you want to use the tool, you need to start it first.

1. Open Terminal (Mac) or Command Prompt (Windows).
2. Navigate to the `staging-tool` folder (same as Step 5 above).
3. Run:
   ```
   python staging.py
   ```
4. You should see something like:
   ```
    * Running on http://127.0.0.1:5000
   ```
5. Open your browser and go to **http://localhost:5000**. The tool's interface will appear.

Keep the Terminal/Command Prompt window open while you're using the tool — closing it stops the server.

To stop the tool when you're done, click into the Terminal window and press **Ctrl+C**.

---

## Part 2: Using the Tool

The tool has four templates. Pick the right one for your email at the top of the page, then follow the steps that appear.

---

### Template 1: Standard Newsletter

**Use this for:** Emily's regular weekly newsletters — full article with an intro/bio section, author block, and related reading links at the bottom.

**Step 1 — Choose your source**

You can load the article three ways:

- **Upload a .docx file** — drag and drop the Word document onto the upload area, or click "browse" to find it. The article should be formatted in the standard way (Emily's welcome/intro paragraphs at the top, followed by the article body with headings).
- **Google Doc link** — paste the URL of the Google Doc. The doc must be set to "Anyone with the link can view" (use Share → change the access setting).
- **ParentData article URL** — paste the URL of an already-published article on parentdata.org. This requires your WordPress credentials to be set up in `.env`.

Click the upload/fetch button and wait. The tool will use AI to extract all the fields — this usually takes 15–30 seconds.

**Step 2 — Review extracted fields**

Check everything that was pulled out:

- **Title** — the article headline as it should appear in the email.
- **Subtitle** — appears below the headline in the hero section. Each line of text in this box becomes one subtitle line in the email.
- **Welcome Text** — Emily's editorial intro, in HTML. This should end with an `<hr>` tag. Leave this blank if Emily wrote the full article herself (no separate intro).
- **Author Name** — the article author (Emily Oster, or a guest author's name).
- **Author Title / Credential** — e.g., "Endocrinologist" or "CEO, ParentData".
- **Author Page URL** — links the "About [Name]" line in the author block. Defaults to Emily's page.
- **Topic Tags** — comma-separated tags used to suggest related articles. Edit or add tags if they're wrong.

**Step 3 — Featured Image**

- **Image URL** — the Iterable CDN link for the article's featured image (starts with `https://library.iterable.com/`). Upload your image to Iterable first, then paste the URL here.
- **Image Alt Text** — a brief description of the image for accessibility (e.g., "A parent holding a young child outdoors").

**Step 4 — Article Body HTML**

The formatted HTML of the article body is shown here. Click "Show / hide article body" to expand it. You can edit the HTML directly if anything looks wrong, though in most cases you won't need to.

**Step 4b — Inline Graph Images** (only appears if the article has charts)

If the article document contained embedded graphs or charts, placeholder slots will appear here. Paste the Iterable CDN URL for each graph image — they'll be placed in the article body in order.

**Step 5 — Related Reading**

Two article slots appear, pre-filled with suggested articles based on the topic tags. For each slot:

- Use the **Swap with** dropdown to pick a different article from the ParentData archive.
- Paste the **Image URL** for the article card thumbnail (from Iterable CDN).
- Check the **Title** and **Tagline** — edit if needed.

**Step 6 — Generate**

Click **Generate Email HTML**. The tool will build the final email. Two download options appear:

- **Download for Iterable** — the file to upload to Iterable's campaigns tool.
- **Download for preview** — a version you can open in a browser to see roughly how it'll look (some email-specific styles won't render perfectly in a browser, but it's useful for a quick check).

---

### Template 2: Fertility Article

**Use this for:** Articles from guest fertility authors (Nathan Fox, Gillian Goddard, etc.) that use the fertility article layout — subtitle and author in the header, no Emily intro, purple "Bottom Line" box at the end.

**Step 1 — Choose your source**

Same three options as the Standard template: .docx upload, Google Doc link, or ParentData article URL.

**Step 2 — Review extracted fields**

- **Title** and **Subtitle** — same as Standard.
- **Author Name** and **Author Title** — for the guest author (e.g., "Nathan Fox" / "OB-GYN").
- **Topic Tags** — for related article suggestions (if needed).

> **Note:** The Fertility template does not have an Emily welcome intro, author block at the bottom, or related reading. Those sections are not part of this email layout.

**Step 3 — Featured Image**

Same as Standard — paste the Iterable CDN URL and alt text.

**Step 4 — Article Body HTML**

The formatted article body. Expand to review or edit.

**Step 4b — Inline Graph Images** (if present)

Same as Standard.

**Step 4c — Bottom Line**

The purple summary box at the end of the fertility email. The HTML for the bullet list appears here — it should be `<ul>...</ul>` with `<li>` items. Edit the bullet text directly in the box.

**Step 5 — Generate**

Click **Generate Email HTML** and download.

---

### Template 3: Fertility Q&A

**Use this for:** The fertility Q&A format — two reader questions, each answered by a doctor, using the Q&A visual layout with decorative question/answer markers.

**Step 1 — Enter the two article URLs and intro text**

The Q&A template always pulls from two published ParentData Q&A articles (WordPress credentials required).

- Paste the URL of the **first article** in the Article 1 URL field.
- Paste the URL of the **second article** in the Article 2 URL field.
- Write the **intro text** — the sentence that appears under the headline at the top of the email (e.g., "It's Q&A day! This week's questions are about prenatal vitamins and sleep."). Type this before clicking Fetch.

Click **Fetch Both Articles**. The tool will pull both articles and format the Q&A pairs — this usually takes 20–40 seconds.

**Step 3 — Question & Answer 1**

- **Question Text** — the reader's question, in plain text. Edit if needed.
- **Sign-off Name** — the reader's name or sign-off as it appears at the end of the question (e.g., "Anne Marie" or "Anxious in Austin").
- **Answer HTML** — the doctor's answer, formatted as HTML. Click "Show / hide answer body" to expand. Edit if needed.

**Step 4 — Question & Answer 2**

Same fields as Q&A 1.

At the bottom of this section:

- **Author attribution line** — auto-filled with "Today's answers come from [Author 1] and [Author 2]." This is fully editable — change the wording, add or remove names, or clear it entirely if you don't want the line.

**Step 5 — Generate**

Click **Generate Email HTML** and download.

---

### Template 4: Marketing Article

**Use this for:** Trial upgrade emails that feature a full article alongside an upgrade CTA and discount pricing.

**Step 1 — Enter the article URL**

Paste a published ParentData article URL. WordPress credentials are required. Click **Use this article** to fetch.

**Step 2 — Review extracted fields**

After fetching, standard article fields appear (title, author, etc.), plus marketing-specific fields:

- **Banner text** — the text in the blue pill bar near the top of the email. Default: "It's the final day of your trial!" Edit to match the campaign.
- **Intro text** — choose from the dropdown. Options are pre-written intro paragraphs tailored for different subscriber segments (e.g., BabyData vs. ToddlerData). The second paragraph of whichever you choose will automatically link to the discount URL.
- **Pricing plan** — choose Yearly or Monthly. This pre-fills the discount price and URL with the standard values for each plan.
- **Discount price** — what the subscriber will pay (e.g., "$84/year"). Edit if running a different offer.
- **Discount URL** — the checkout link with the coupon code applied. Edit if using a different coupon.

**Step 3 — Featured Image**

Same as Standard — paste the Iterable CDN URL and alt text.

**Step 4 — Article Body HTML**

The full article body. Expand to review.

**Step 5 — Generate**

Click **Generate Email HTML** and download.

---

## Part 3: Troubleshooting

**The tool won't start / "python is not recognized"**
Make sure Python was installed with "Add to PATH" checked (Windows). Try restarting Command Prompt after installing Python.

**"Your credit balance is too low"**
The Anthropic API has run out of credits. Go to [console.anthropic.com](https://console.anthropic.com) → Plans & Billing to add credits.

**"Overloaded" error from the API**
The Anthropic API is temporarily busy. Wait a minute and try again.

**Can't fetch a WordPress article**
Make sure your WP credentials are correct in `.env`. Your WordPress username is the login name (not your email address). The application password should be copied exactly as generated, spaces included.

**A specific article can't be fetched from WordPress**
A small number of articles are stored in a non-standard format in WordPress and can't be pulled via the API. Download the article as a Word document from Google Docs instead and use the .docx upload path.

**Google Doc won't import**
The doc must be shared as "Anyone with the link can view." Open the doc in Google Docs, click Share, and change the access setting.

**The article body HTML looks wrong**
Expand the "Article Body HTML" section and edit directly. The AI does its best but occasionally misformats something — a quick manual fix in the text area is the fastest solution.

**The related article images are blank after generating**
The tool can suggest article titles and links automatically, but image URLs must be pasted manually (from Iterable CDN). Each related article slot has an Image URL field — make sure it's filled in.
