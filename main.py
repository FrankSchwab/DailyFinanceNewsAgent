import os
import feedparser
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

# --- Configuration ---
# Your email details. It is CRITICAL that you store your password as a GitHub Secret.
# In GitHub, go to your repository's Settings > Secrets and variables > Actions
# Click 'New repository secret' and add your email password with the name 'EMAIL_PASSWORD'.
SENDER_EMAIL = os.environ.get("SENDER_EMAIL") # This will be securely loaded from GitHub Secrets
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL") # This will be securely loaded from GitHub Secrets
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD") # This will be securely loaded from GitHub Secrets

# You can add more RSS feeds to this list as you find them.
# I've included a mix of general finance news, and specific feeds for DACH and MENA regions based on my search.
RSS_FEEDS = [
    # DACH Region Feeds (Germany, Austria, Switzerland)
    "https://www.finma.ch/en/rss/news", # Swiss Financial Market Supervisory Authority (FINMA)
    "https://www.ecb.europa.eu/home/html/rss.en.html", # European Central Bank (ECB)
    "https://www.dnb.nl/en/rss/", # De Nederlandsche Bank (Dutch) - covers topics relevant to Europe
    # MENA Region Feeds (Middle East and North Africa)
    "https://www.arabfinance.com/RSS/RSSList/en", # Arab Finance
    "https://www.meed.com/rss-feeds", # MEED (Middle East Economic Digest)
    "https://fintechnews.ae/feed/", # Fintech News Middle East
    # General Crypto Feeds (often cover global and regional news)
    "https://cointelegraph.com/rss-feeds", # Cointelegraph (popular crypto news)
    "https://invezz.com/feeds/" # Invezz (investment news, including crypto)
]

# Keywords to filter articles. You can adjust this list to match your interests.
KEYWORDS = ["banking", "finance", "crypto", "bitcoin", "blockchain", "fintech", "payment", "mena", "dach", "saudi", "dubai", "germany", "austria", "switzerland"]

def get_articles():
    """Fetches and filters articles from a list of RSS feeds."""
    all_articles = []
    today = datetime.now()
    yesterday = today - timedelta(days=1)

    for url in RSS_FEEDS:
        print(f"Fetching articles from {url}...")
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                # Check if the article was published in the last 24 hours.
                # RSS feeds can be inconsistent, so this is a best-effort check.
                if hasattr(entry, 'published_parsed'):
                    published_date = datetime(*entry.published_parsed[:6])
                    if published_date < yesterday:
                        continue # Skip old articles

                # Filter articles by keyword in title or summary.
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                
                # Check for keywords in a case-insensitive manner
                if any(keyword.lower() in title.lower() or keyword.lower() in summary.lower() for keyword in KEYWORDS):
                    all_articles.append({
                        "title": title,
                        "link": entry.get("link", "No link available"),
                        "source": feed.get("feed", {}).get("title", "Unknown Source")
                    })
        except Exception as e:
            print(f"Error fetching feed from {url}: {e}")
            continue

    return all_articles

def create_email_body(articles):
    """Creates an HTML-formatted email body from a list of articles."""
    body = """
    <html>
    <body style="font-family: sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: #ffffff; padding: 20px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
            <h1 style="color: #333; text-align: center;">Daily Finance & Crypto Digest</h1>
            <p style="color: #666; text-align: center;">Here are today's top articles on banking, finance, and crypto from the DACH and MENA regions.</p>
            <hr style="border: 0; height: 1px; background: #ddd; margin: 20px 0;">
    """
    
    if not articles:
        body += "<p style='text-align: center; color: #888;'>No new articles found today. Check back tomorrow!</p>"
    else:
        for article in articles:
            body += f"""
            <div style="border-bottom: 1px solid #eee; padding: 15px 0;">
                <h2 style="font-size: 18px; color: #007bff;"><a href="{article['link']}" style="text-decoration: none; color: #007bff;">{article['title']}</a></h2>
                <p style="font-size: 14px; color: #555;"><strong>Source:</strong> {article['source']}</p>
            </div>
            """
    
    body += """
        </div>
    </body>
    </html>
    """
    return body

def send_email(subject, body):
    """Sends an email using the SMTP protocol."""
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = SENDER_EMAIL
    message["To"] = RECEIVER_EMAIL

    # Attach the email body as HTML
    html_part = MIMEText(body, "html")
    message.attach(html_part)

    # Connect to the SMTP server and send the email
    context = ssl.create_default_context()
    try:
        print("Connecting to SMTP server...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(SENDER_EMAIL, EMAIL_PASSWORD)
            print("Sending email...")
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, message.as_string())
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email. Error: {e}")

if __name__ == "__main__":
    print("Starting news agent...")
    articles = get_articles()
    
    if articles:
        subject = f"Daily Finance & Crypto Digest - {datetime.now().strftime('%Y-%m-%d')}"
        email_body = create_email_body(articles)
        send_email(subject, email_body)
    else:
        print("No articles to send. Skipping email.")
