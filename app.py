import os
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import quote
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time
import json

from google import genai
from google.genai import types

# --- CONFIGURARE CREDENTIALE ---
# Acestea vor fi citite din GitHub Secrets
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

# Lista de active pentru monitorizare
QUERIES = [
    "S&P 500", "Nasdaq 100", "Apple stock", "Tesla stock", "Nvidia stock", 
    "EURUSD", "GBPUSD", "USDJPY", "Gold market", "WTI Oil", "Bitcoin"
]

def fetch_news(query):
    """Caută cea mai recentă știre (ultimele 24h) pentru un query specific."""
    rss_url = f"https://news.google.com/rss/search?q={quote(query)}+when:1d&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(rss_url)
    
    if not feed.entries:
        return None
        
    item = feed.entries[0]
    source_name = item.source.title if hasattr(item, 'source') else "Market Source"
    
    return {
        "title": item.title,
        "link": item.link,
        "published": item.published,
        "query": query,
        "source": source_name
    }

def analyze_with_ai(title, query):
    """Analizează știrea folosind Gemini și returnează date structurate JSON."""
    prompt = f"""
    Ești un trader senior. Analizează știrea pentru '{query}': {title}. 
    Răspunde STRICT în format JSON valid cu următoarele chei:
    "sentiment": (Pozitiv/Negativ/Neutru),
    "email_take": (un rezumat de o frază),
    "web_exp": (analiză macro scurtă),
    "indrumare": (direcția de urmărit).
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        data = json.loads(response.text)
        return data
    except Exception as e:
        print(f"Eroare AI pentru {query}: {e}")
        return {
            "sentiment": "Neutru",
            "email_take": "Analiză indisponibilă momentan.",
            "web_exp": "Verificați sursele oficiale.",
            "indrumare": "Monitorizare niveluri tehnice."
        }

def send_email(articles):
    """Trimite raportul prin email."""
    if not SENDER_EMAIL or not RECEIVER_EMAIL: 
        print("Eroare: Credențiale email lipsă!")
        return
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 Raport Trading: {datetime.now().strftime('%d-%m-%Y')}"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    
    body = "<h2>Rezumat de Dimineață - Terminal Pro</h2><ul>"
    for a in articles:
        body += f"<li><strong>{a['query']}:</strong> {a.get('email_take', 'Fără rezumat')}</li>"
    body += "</ul><p>Vezi terminalul complet aici: <a href='https://naicatheone.github.io/Trading-Terminal/'>Terminal Pro</a></p>"
    
    msg.attach(MIMEText(body, "html"))
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        server.quit()
        print("Email trimis cu succes!")
    except Exception as e: 
        print(f"Eroare trimitere email: {e}")

def generate_web_html(articles):
    """Generează codul HTML pentru GitHub Pages."""
    date_str = datetime.now().strftime("%d-%m-%Y %H:%M")
    
    html = f"""
    <!DOCTYPE html>
    <html lang="ro" data-theme="dark">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Terminal Pro AI</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;700;800&display=swap" rel="stylesheet">
        <style>
            :root {{ --bg: #0b0e11; --card: #181a20; --text: #b7bdc6; --text-bold: #ffffff; --border: #2b3139; --accent: #2962ff; }}
            body {{ background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; margin: 0; padding-bottom: 50px; }}
            header {{ background: var(--card); border-bottom: 1px solid var(--border); padding: 15px 40px; display: flex; align-items: center; justify-content: space-between; position: sticky; top: 0; z-index: 1000; }}
            .logo {{ font-weight: 800; font-size: 20px; color: var(--text-bold); }}
            #live-clock {{ font-family: monospace; font-weight: bold; color: var(--accent); font-size: 16px; }}
            .main-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 20px; padding: 20px 40px; }}
            .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }}
            .badge {{ float: right; padding: 4px 8px; border-radius: 4px; font-size: 10px; font-weight: bold; color: white; }}
            .market-label {{ font-size: 11px; font-weight: 800; color: var(--accent); text-transform: uppercase; }}
            .card-title {{ display: block; margin: 10px 0; color: var(--text-bold); text-decoration: none; font-weight: 700; line-height: 1.4; }}
            .section-label {{ font-size: 10px; font-weight: 800; color: var(--accent); text-transform: uppercase; margin-top: 15px; border-bottom: 1px solid var(--border); padding-bottom: 4px; }}
            .content-text {{ font-size: 13px; line-height: 1.5; margin-top: 8px; }}
        </style>
    </head>
    <body>
        <header>
            <div class="logo">⬡ TERMINAL PRO AI</div>
            <div style="text-align: right;">
                <div id="live-clock">00:00:00</div>
                <div style="font-size: 10px;">Ultima actualizare: {date_str} (RO)</div>
            </div>
        </header>
        <div class="main-grid">
    """

    for art in articles:
        sent = art.get('sentiment', 'Neutru')
        b_color = "#26a69a" if "Pozitiv" in sent else ("#ef5350" if "Negativ" in sent else "#787b86")
        
        html += f"""
            <div class="card">
                <span class="badge" style="background:{b_color}">{sent}</span>
                <div class="market-label">{art['query']}</div>
                <a href="{art['link']}" class="card-title" target="_blank">{art['title']}</a>
                <div class="section-label">Analiză Macro</div>
                <div class="content-text">{art.get('web_exp', '')}</div>
                <div class="section-label">Strategie</div>
                <div class="content-text" style="color:white; font-weight:600;">{art.get('indrumare', '')}</div>
            </div>
        """

    html += """
        </div>
        <script>
            function updateClock() {
                document.getElementById('live-clock').innerText = new Date().toLocaleTimeString('ro-RO');
            }
            setInterval(updateClock, 1000); updateClock();
        </script>
    </body></html>
    """
    return html

def main():
    print(f"--- START RULARE: {datetime.now()} ---")
    all_articles = []
    
    for q in QUERIES:
        print(f"Preluare știri pentru: {q}")
        article_data = fetch_news(q)
        if article_data:
            # Analiza AI
            analysis = analyze_with_ai(article_data['title'], q)
            article_data.update(analysis)
            all_articles.append(article_data)
        time.sleep(4) # Prevenire rate-limit

    # 1. Actualizare site (se întâmplă la fiecare rulare - de 4 ori pe zi)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(generate_web_html(all_articles))
    print("Pagina index.html a fost generată.")

    # 2. Logica Email (Doar la 08:30 RO, adică 06:30 UTC)
    # GitHub rulează pe ora UTC
    now_utc = datetime.utcnow()
    if now_utc.hour == 6:
        print("Este fereastra de dimineață. Trimit email...")
        send_email(all_articles)
    else:
        print(f"Ora UTC curentă: {now_utc.hour}. Salt peste trimitere email.")

if __name__ == "__main__":
    main()

