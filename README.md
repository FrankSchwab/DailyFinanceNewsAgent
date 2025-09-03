# Daily Finance & Crypto Digest — README

A small Python script that pulls fresh articles from selected RSS feeds (DACH & MENA focus), filters them by keywords, renders a simple HTML digest, and emails it to you via Gmail SMTP. It’s designed to be resilient against “invisible” Unicode characters that often break email sending.

---

## Features

* Fetches from a curated list of RSS feeds (finance/fintech/crypto).
* Filters by configurable keywords.
* Sends a styled HTML email (“Daily Finance & Crypto Digest”).
* Robust Unicode hygiene (normalizes/removes NBSP, ZWSP, control chars).
* Helpful debug logging when email sending fails.

---

## Requirements

* **Python**: 3.10+ recommended
* **Packages**:

  * `feedparser`
  * (standard library: `smtplib`, `ssl`, `email`, `unicodedata`, etc.)

Create a `requirements.txt`:

```txt
feedparser>=6.0.11
```

Install:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Configuration (Environment Variables)

Set these **environment variables** (ASCII-only for the envelope addresses):

* `SENDER_EMAIL` — your Gmail address (e.g., `you@gmail.com`)
* `RECEIVER_EMAIL` — recipient address
* `EMAIL_PASSWORD` — a **Gmail App Password** (not your normal password)

> **Gmail App Password:** In your Google Account → Security → **2-Step Verification** → **App passwords** → generate a 16-char password for “Mail”. Paste that value into `EMAIL_PASSWORD`.

Example using a `.env` (if you prefer exporting manually, skip this):

```bash
export SENDER_EMAIL="you@gmail.com"
export RECEIVER_EMAIL="you@example.com"
export EMAIL_PASSWORD="abcd efgh ijkl mnop"  # 16 chars; spaces ok
```

> The script **cleans invisible characters** from all inputs and IDNA-encodes the **domain** if needed, but the final SMTP envelope must be ASCII. If you still see ASCII/Unicode errors, recreate the App Password and retype the emails (avoid copy/paste from rich text).

---

## Running Locally

```bash
python your_script_name.py
```

* On success you’ll see:

  * `Starting news agent…`
  * `Fetching articles from …`
  * `Connecting to SMTP server…`
  * `Email sent successfully!`
* If **no new articles** matched in the last 24h, it prints:
  `No articles to send. Skipping email.`

---

## How It Works

1. **Fetch & Filter**

   * Pulls entries from `RSS_FEEDS`.
   * Uses each entry’s `published_parsed`/`updated_parsed` to keep only the **last 24 hours**.
   * Filters by `KEYWORDS` (case-insensitive) across title + summary.

2. **Email Build & Send**

   * Creates a compact HTML list (`title`, `source`, link).
   * Sends via Gmail over **SMTP SSL (465)** with `send_message()` to avoid encoding pitfalls.

3. **Unicode Hygiene**

   * Normalizes text (NFKC), replaces special spaces (NBSP, thin, figure), removes control/format characters.
   * Cleans envelope addresses and IDNA-encodes domains where relevant.

---

## Customization

* **Feeds**: Edit `RSS_FEEDS` to add/remove sources.
* **Keywords**: Update `KEYWORDS`.

  > Tip: The sample shows duplicates; keep a clean, unique list like:

  ```python
  KEYWORDS = [
      "banking", "finance", "crypto", "bitcoin", "blockchain", "fintech",
      "payment", "mena", "dach", "saudi", "dubai", "germany", "austria", "switzerland"
  ]
  ```
* **Look & Feel**: Tweak the inline CSS in `create_email_body()`.

---

## Scheduling

### macOS/Linux (cron)

```bash
crontab -e
# run daily at 07:30
30 7 * * * /path/to/project/.venv/bin/python /path/to/project/your_script_name.py >> /path/to/project/digest.log 2>&1
```

### Windows (Task Scheduler)

Create a daily task that runs:

```
C:\path\to\python.exe C:\path\to\project\your_script_name.py
```

---

## Troubleshooting

* **`'ascii' codec can't encode character ...`**

  * The script prints **raw** and **cleaned** versions of `SENDER_EMAIL`, `RECEIVER_EMAIL`, and flags unusual whitespace in `EMAIL_PASSWORD`.
  * Re-type emails/passwords in a **plain-text editor**. Avoid copying from formatted docs.
  * Ensure `SENDER_EMAIL` and `RECEIVER_EMAIL` are ASCII in the **envelope** (display names aren’t used in headers here).

* **Authentication fails**

  * Confirm 2-Step Verification is **enabled** and you’re using an **App Password**.
  * Double-check you’re on **SMTP SSL 465** (the script uses `SMTP_SSL`).

* **No articles**

  * Check the last 24h window.
  * Add more feeds or broaden `KEYWORDS`.

---

## Security Notes

* Never commit real credentials. Use environment variables or a local `.env` outside version control.
* App Passwords can be revoked anytime from your Google Account.
* This script uses read-only public RSS feeds and sends an email; no data is stored server-side.

---

## File Pointers (if you split files)

* `main.py` — the provided script.
* `requirements.txt` — package list.
* `README.md` — this file.

That’s it—happy digesting!
