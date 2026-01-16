import os
import re
import unicodedata
import feedparser
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import parseaddr, formataddr
from datetime import datetime, timedelta

# --- Unicode hygiene helpers -------------------------------------------------

INVISIBLE_CATEGORIES = {"Cf", "Cc"}  # format & control (e.g., ZWSP, BOM)
# Common non-breaking / special spaces to normalize
SPECIAL_SPACES = {
    "\u00A0",  # NBSP
    "\u202F",  # narrow NBSP
    "\u2007",  # figure space
    "\u2009",  # thin space
}

def strip_invisibles(s: str) -> str:
    """Normalize, replace special spaces with normal spaces, drop invisible/control chars, trim."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = "".join((" " if (ch in SPECIAL_SPACES or unicodedata.category(ch) == "Zs") else ch) for ch in s)
    s = "".join(ch for ch in s if unicodedata.category(ch) not in INVISIBLE_CATEGORIES)
    return s.strip()

def clean_addr(raw: str) -> str:
    """
    Clean an email address for SMTP envelope:
    - remove exotic spaces/invisibles
    - parse name<addr>, keep addr
    - IDNA-encode domain to ASCII
    - verify ASCII-only
    """
    s = strip_invisibles(raw or "")
    name, addr = parseaddr(s)
    addr = strip_invisibles(addr)
    addr = addr.replace(" ", "")
    if "@" in addr:
        local, domain = addr.split("@", 1)
        # IDNA/punycode for domain
        try:
            domain_ascii = domain.encode("idna").decode("ascii")
        except Exception:
            domain_ascii = domain  # fallback; we'll catch non-ascii below
        addr = f"{local}@{domain_ascii}"
    # Final guard: force ASCII or raise helpful error
    try:
        addr.encode("ascii")
    except UnicodeEncodeError as e:
        raise ValueError(f"Envelope address still not ASCII after cleaning: {repr(addr)}") from e
    return addr

def safe_text(s: str) -> str:
    """Normalize feed text for safe UTF-8 usage in MIME bodies/headers."""
    return strip_invisibles(s or "").encode("utf-8", "ignore").decode("utf-8").strip()

def feed_source_title(parsed_feed) -> str:
    try:
        return safe_text(getattr(parsed_feed, "feed", {}).get("title", "Unknown Source"))
    except Exception:
        return "Unknown Source"

# --- Config from environment --------------------------------------------------

SENDER_EMAIL_RAW   = os.environ.get("SENDER_EMAIL")   or ""
RECEIVER_EMAIL_RAW = os.environ.get("RECEIVER_EMAIL") or ""
EMAIL_PASSWORD_RAW = os.environ.get("EMAIL_PASSWORD") or ""

# Clean password too (in case of pasted NBSP/ZWSP)
EMAIL_PASSWORD = strip_invisibles(EMAIL_PASSWORD_RAW)

# RSS feeds / keywords ---------------------------------------------------------

RSS_FEEDS = [
    # DACH
    "https://fintechnews.ch/feed",
    "https://www.finma.ch/en/rss/news",
    "https://www.ecb.europa.eu/home/html/rss.en.html",
    "https://www.dnb.nl/en/rss/",
    "https://www.fma.gv.at/en/feed",
    # MENA
    "https://www.arabfinance.com/RSS/RSSList/en",
    "https://www.meed.com/rss-feeds",
    "https://fintechnews.ae/feed",
    # Crypto / general finance
    "https://cointelegraph.com/rss-feeds",
    "https://invezz.com/feeds",
    "https://thefintechtimes.com/feed", 
    # OTHER 
    "https://www.americanbanker.com/feed/technology",
    "https://thefinancialbrand.com/feed/",
    "https://www.bankingdive.com/feeds/news/",
    "https://www.bankingdive.com/feeds/topic/technology/",
    "https://www.fintechfutures.com/feed/",
    "https://techcrunch.com/category/fintech/feed/",
    "https://ibsintelligence.com/feed/",
    "https://www.finextra.com/rss/headlines.aspx",
    "https://bankautomationnews.com/feed/",
    "https://www.paymentsdive.com/feeds/news/",
    "https://finovate.com/feed/",
    "https://www.mercatoradvisorygroup.com/feed/",
    "https://www.bis.org/doclist/rss_all_categories.rss",
    "https://www.federalreserve.gov/feeds/press_all.xml",
    "https://www.ecb.europa.eu/rss/paym.xml",
    "https://sifted.eu/feed",
    "https://www.paymentsdive.com/feeds/news/",
    "https://paymentsjournal.com/feed",
    "https://paymentsnext.com/feed",
    "https://www.mobilepaymentstoday.com/rss/",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://www.ledgerinsights.com/feed/",
    "https://www.ababankingjournal.com/feed/",
    "https://www.bankdirector.com/feed/",
    "https://www.bankingexchange.com/index.php?format=feed&type=rss ",
    "https://www.forrester.com/blogs/category/banking-finance/feed/",
    "https://www.celent.com/insights/banking/rss",   
    
]

KEYWORDS = [
    "banking","finance","crypto","bitcoin","blockchain","fintech",
    "payment","mena","dach","saudi","dubai","germany","austria","switzerland",
    "megatrend"
]

# --- Core logic ---------------------------------------------------------------

def get_articles():
    all_articles = []
    cutoff = datetime.now() - timedelta(days=1)

    for url in RSS_FEEDS:
        print(f"Fetching articles from {url}...")
        try:
            feed = feedparser.parse(url)
            source = feed_source_title(feed)

            for entry in feed.entries:
                pub_dt = None
                if getattr(entry, "published_parsed", None):
                    pub_dt = datetime(*entry.published_parsed[:6])
                elif getattr(entry, "updated_parsed", None):
                    pub_dt = datetime(*entry.updated_parsed[:6])
                if pub_dt and pub_dt < cutoff:
                    continue

                title = safe_text(entry.get("title", ""))
                summary = safe_text(entry.get("summary", ""))
                link = safe_text(entry.get("link", "")) or "No link available"

                text_to_search = f"{title}\n{summary}".lower()
                if any(k.lower() in text_to_search for k in KEYWORDS):
                    all_articles.append({"title": title or "(no title)", "link": link, "source": source})
        except Exception as e:
            print(f"Error fetching feed from {url}: {e}")
            continue

    return all_articles

def create_email_body(articles):
    parts = [
        '<html>',
        '<body style="font-family: sans-serif; background-color: #f4f4f4; padding: 20px;">',
        '<div style="max-width:600px;margin:auto;background:#ffffff;padding:20px;border-radius:10px;box-shadow:0 4px 8px rgba(0,0,0,0.1);">',
        '<h1 style="color:#333;text-align:center;">Daily Finance &amp; Crypto Digest</h1>',
        '<p style="color:#666;text-align:center;">Here are today\'s top articles on banking, finance, and crypto from the DACH and MENA regions.</p>',
        '<hr style="border:0;height:1px;background:#ddd;margin:20px 0;">'
    ]
    if not articles:
        parts.append("<p style='text-align:center;color:#888;'>No new articles found today. Check back tomorrow!</p>")
    else:
        for a in articles:
            parts.append(
                f'''<div style="border-bottom:1px solid #eee;padding:15px 0;">
                        <h2 style="font-size:18px;color:#007bff;">
                            <a href="{a['link']}" style="text-decoration:none;color:#007bff;">{a['title']}</a>
                        </h2>
                        <p style="font-size:14px;color:#555;"><strong>Source:</strong> {a['source']}</p>
                    </div>'''
            )
    parts.extend(['</div>', '</body>', '</html>'])
    return "\n".join(parts)

def send_email(subject: str, body_html: str):
    # Clean & validate envelope addresses
    from_addr = clean_addr(SENDER_EMAIL_RAW)
    to_addr   = clean_addr(RECEIVER_EMAIL_RAW)

    # Build message
    msg = MIMEMultipart("alternative", _charset="utf-8")
    msg["Subject"] = Header(strip_invisibles(subject), "utf-8")
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    # SMTP send
    context = ssl.create_default_context()
    print("Envelope From:", repr(from_addr))
    print("Envelope To  :", repr(to_addr))
    print("Connecting to SMTP server...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        # server.set_debuglevel(1)  # uncomment for SMTP conversation debug
        try:
            print("Logging in…")
            server.login(from_addr, EMAIL_PASSWORD)
            print("Sending email…")
            server.send_message(msg, from_addr=from_addr, to_addrs=[to_addr])
            print("Email sent successfully!")
        except Exception as e:
            raise  # bubble up so caller prints our context

# --- Entrypoint ---------------------------------------------------------------

if __name__ == "__main__":
    print("Starting news agent...")
    try:
        articles = get_articles()
        if articles:
            subject = f"Daily Finance & Crypto Digest - {datetime.now().strftime('%Y-%m-%d')}"
            body = create_email_body(articles)
            send_email(subject, body)
        else:
            print("No articles to send. Skipping email.")
    except Exception as e:
        # Show raw & cleaned values to pinpoint where the bad char lives
        print(f"Failed to send email. Error: {e}")
        print("Raw From (repr):", repr(SENDER_EMAIL_RAW))
        print("Raw To   (repr):", repr(RECEIVER_EMAIL_RAW))
        try:
            print("Clean From (repr):", repr(clean_addr(SENDER_EMAIL_RAW)))
        except Exception as ce:
            print("Clean From failed:", ce)
        try:
            print("Clean To   (repr):", repr(clean_addr(RECEIVER_EMAIL_RAW)))
        except Exception as ce:
            print("Clean To failed:", ce)
        # Also show if password contains exotic characters (masked length only)
        if any(ch in SPECIAL_SPACES or unicodedata.category(ch) in INVISIBLE_CATEGORIES or unicodedata.category(ch) == "Zs"
               for ch in EMAIL_PASSWORD_RAW):
            print("Note: EMAIL_PASSWORD contains unusual whitespace/control characters. Recreate your App Password.")
