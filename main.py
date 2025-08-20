import os
import feedparser
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import parseaddr, formataddr
from datetime import datetime, timedelta

# --- Configuration (from environment) ---
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

# RSS feeds
RSS_FEEDS = [
    # DACH
    "https://www.finma.ch/en/rss/news",
    "https://www.ecb.europa.eu/home/html/rss.en.html",
    "https://www.dnb.nl/en/rss/",
    # MENA
    "https://www.arabfinance.com/RSS/RSSList/en",
    "https://www.meed.com/rss-feeds",
    "https://fintechnews.ae/feed/",
    # Crypto / general finance
    "https://cointelegraph.com/rss-feeds",
    "https://invezz.com/feeds/",
]

# Keywords
KEYWORDS = [
    "banking", "finance", "crypto", "bitcoin", "blockchain", "fintech",
    "payment", "mena", "dach", "saudi", "dubai", "germany", "austria", "switzerland"
]

# --- Utilities ---

def clean_addr(s: str) -> str:
    """Strip non-breaking spaces and normalize an email address for SMTP (ASCII only)."""
    if not s:
        return s
    s = s.replace('\u00a0', ' ').strip()
    name, addr = parseaddr(s)
    # remove any stray spaces within the addr part
    addr = (addr or "").replace(' ', '')
    return addr

def safe_text(s: str) -> str:
    """Normalize text from feeds to clean up NBSP and ensure it's valid UTF-8."""
    if not s:
        return ""
    return s.replace('\u00a0', ' ').encode("utf-8", "ignore").decode("utf-8").strip()

def feed_source_title(parsed_feed) -> str:
    try:
        return safe_text(getattr(parsed_feed, "feed", {}).get("title", "Unknown Source"))
    except Exception:
        return "Unknown Source"

# --- Core logic ---

def get_articles():
    """Fetches and filters articles from the RSS feeds within the last 24 hours and matching KEYWORDS."""
    all_articles = []
    now = datetime.now()
    cutoff = now - timedelta(days=1)

    for url in RSS_FEEDS:
        print(f"Fetching articles from {url}...")
        try:
            feed = feedparser.parse(url)
            source = feed_source_title(feed)

            for entry in feed.entries:
                # Date filter (best effort)
                pub_dt = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub_dt = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    pub_dt = datetime(*entry.updated_parsed[:6])

                if pub_dt and pub_dt < cutoff:
                    continue  # older than 24h

                title = safe_text(entry.get("title", ""))
                summary = safe_text(entry.get("summary", ""))
                link = safe_text(entry.get("link", "")) or "No link available"

                text_to_search = f"{title}\n{summary}".lower()
                if any(k in text_to_search for k in (kw.lower() for kw in KEYWORDS)):
                    all_articles.append({
                        "title": title or "(no title)",
                        "link": link,
                        "source": source,
                    })
        except Exception as e:
            print(f"Error fetching feed from {url}: {e}")
            continue

    return all_articles

def create_email_body(articles):
    """Creates an HTML-formatted email body from a list of articles."""
    body = [
        "<html>",
        "<body style=\"font-family: sans-serif; background-color: #f4f4f4; padding: 20px;\">",
        "<div style=\"max-width: 600px; margin: auto; background: #ffffff; padding: 20px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);\">",
        "<h1 style=\"color: #333; text-align: center;\">Daily Finance &amp; Crypto Digest</h1>",
        "<p style=\"color: #666; text-align: center;\">Here are today's top articles on banking, finance, and crypto from the DACH and MENA regions.</p>",
        "<hr style=\"border: 0; height: 1px; background: #ddd; margin: 20px 0;\">"
    ]

    if not articles:
        body.append("<p style='text-align: center; color: #888;'>No new articles found today. Check back tomorrow!</p>")
    else:
        for a in articles:
            body.append(
                f"""
                <div style="border-bottom: 1px solid #eee; padding: 15px 0;">
                    <h2 style="font-size: 18px; color: #007bff;">
                        <a href="{a['link']}" style="text-decoration: none; color: #007bff;">{a['title']}</a>
                    </h2>
                    <p style="font-size: 14px; color: #555;"><strong>Source:</strong> {a['source']}</p>
                </div>
                """.strip()
            )

    body.extend(["</div>", "</body>", "</html>"])
    return "\n".join(body)

def send_email(subject: str, body_html: str):
    """Sends the email via Gmail SMTP with robust UTF-8 handling and clean ASCII-only envelope addresses."""
    from_addr = clean_addr(SENDER_EMAIL)
    to_addr = clean_addr(RECEIVER_EMAIL)

    if not from_addr or not to_addr or not EMAIL_PASSWORD:
        raise RuntimeError("Missing SENDER_EMAIL, RECEIVER_EMAIL, or EMAIL_PASSWORD environment variables.")

    msg = MIMEMultipart("alternative", _charset="utf-8")
    # Subject can contain non-ASCII safely with Header
    msg["Subject"] = Header(subject, "utf-8")

    # If you want a display name:
    # display_name = str(Header("Frank Schwab", "utf-8"))
    # msg["From"] = formataddr((display_name, from_addr))
    # Otherwise, plain address:
    msg["From"] = from_addr
    msg["To"] = to_addr

    html_part = MIMEText(body_html, "html", "utf-8")
    msg.attach(html_part)

    context = ssl.create_default_context()
    print("Connecting to SMTP server...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(from_addr, EMAIL_PASSWORD)
        print("Sending email...")
        # Use send_message to avoid manual encoding issues; envelope addresses must be ASCII-clean
        server.send_message(msg, from_addr=from_addr, to_addrs=[to_addr])
    print("Email sent successfully!")

# --- Entrypoint ---

if __name__ == "__main__":
    print("Starting news agent...")
    articles = get_articles()
    if articles:
        subject = f"Daily Finance & Crypto Digest - {datetime.now().strftime('%Y-%m-%d')}"
        email_body = create_email_body(articles)
        try:
            send_email(subject, email_body)
        except Exception as e:
            print(f"Failed to send email. Error: {e}")
            # Helpful debug to reveal hidden characters in env vars (remove after fixing)
            print("From (repr):", repr(SENDER_EMAIL))
            print("To   (repr):", repr(RECEIVER_EMAIL))
    else:
        print("No articles to send. Skipping email.")
