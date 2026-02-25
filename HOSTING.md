# Hosting the Staging Tool Online

Notes on what it would take to deploy this tool to the web so anyone with a link can use it, without needing Python installed locally.

## Overview

The tool is already a web server (Flask). Hosting it online is mostly a deployment task, not a rewrite. Estimated effort: ~1 hour of work.

---

## What to use

**Railway** (railway.app) is the recommended option:
- Connects directly to the GitHub repo and auto-deploys on every push
- ~$5/month for a small always-on instance
- Simple dashboard for setting environment variables

**Render** (render.com) is a close alternative with similar pricing. Its free tier sleeps after 15 minutes of inactivity (first visit after a gap takes ~30 seconds to wake up), so a paid plan is better for regular use.

---

## Code changes required

### 1. Add gunicorn to `requirements.txt`

Flask's built-in development server is not suitable for production. Gunicorn is the standard production wrapper. Add one line:

```
gunicorn>=21.0.0
```

### 2. Add a `Procfile`

Railway/Render need a one-line file called `Procfile` (no extension) in the `staging-tool` folder to know how to start the app:

```
web: gunicorn staging:app
```

### 3. Add basic authentication

Without a password, anyone who finds the URL could use the tool and burn through the Anthropic API credits. The simplest fix is HTTP Basic Auth — the browser shows a username/password prompt before anyone can reach the page.

Add this to `staging.py` (after the imports, before the routes):

```python
import functools
from flask import request, Response

BASIC_AUTH_USERNAME = os.environ.get('BASIC_AUTH_USERNAME', '')
BASIC_AUTH_PASSWORD = os.environ.get('BASIC_AUTH_PASSWORD', '')

def require_auth(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if BASIC_AUTH_USERNAME and BASIC_AUTH_PASSWORD:
            auth = request.authorization
            if not auth or auth.username != BASIC_AUTH_USERNAME or auth.password != BASIC_AUTH_PASSWORD:
                return Response(
                    'Authentication required.',
                    401,
                    {'WWW-Authenticate': 'Basic realm="Staging Tool"'},
                )
        return f(*args, **kwargs)
    return decorated
```

Then add `@require_auth` as a decorator to each route:

```python
@app.route('/')
@require_auth
def index():
    ...

@app.route('/upload', methods=['POST'])
@require_auth
def upload():
    ...
```

(Apply to all routes: `/`, `/upload`, `/articles`, `/refresh-articles`, `/generate`, `/marketing-config`)

Add two new variables to `.env.example`:
```
BASIC_AUTH_USERNAME=your-chosen-username
BASIC_AUTH_PASSWORD=your-chosen-password
```

### 4. Environment variables (no code change)

The `.env` file stays on the local machine and is never committed or uploaded. On Railway/Render, paste the same variables into the platform's Environment Variables settings page:

```
ANTHROPIC_API_KEY=...
WP_APP_USERNAME=...
WP_APP_PASSWORD=...
BASIC_AUTH_USERNAME=...
BASIC_AUTH_PASSWORD=...
```

---

## Deployment steps (Railway)

1. Create an account at railway.app
2. Click **New Project → Deploy from GitHub repo** and select the StagingTools repo
3. Set the **root directory** to `staging-tool` (since the repo root isn't the app)
4. Add all environment variables in the Railway dashboard under **Variables**
5. Railway will build and deploy automatically — it will provide a public URL

---

## What stays the same

Everything else works identically on a hosted server:
- All template logic, Claude prompts, HTML building
- WordPress article fetching
- The web UI
- DOCX file uploads (Flask handles these fine server-side)

## One thing to know

The article index cache (used for "More from ParentData" suggestions) lives in memory and resets whenever the server restarts. It rebuilds itself automatically on first use, so this is not a problem — just worth knowing.

---

## Cost summary

| Item | Cost |
|---|---|
| Railway hosting | ~$5–7/month |
| Anthropic API | Same as now (usage-based) |
| WP credentials | Already have these |
