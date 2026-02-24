import os
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import quote
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time

from google import genai
from google.genai import types

# --- CONFIGURARE CREDENTIALE ---
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

def fetch_news(query, num_articles=1):
    # Căutăm fără restricție de timp pentru a avea mereu date
    rss_url = f"https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"
    feed = feedparser.parse(rss_url)
    
    if not feed.entries:
        rss_url = f"https://news.google.com/rss/search?q={quote('finance market')}?hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(rss_url)
        
    news_items = feed.entries[:num_articles]
    articles = []
    for item in news_items:
        source_name = item.source.title if hasattr(item, 'source') and hasattr(item.source, 'title') else "Bloomberg/Reuters"
        soup = BeautifulSoup(item.summary, 'html.parser') if hasattr(item, 'summary') else None
        summary_text = soup.get_text(separator=" ").strip() if soup else ""
        articles.append({
            "title": item.title, "link": item.link, "published": item.published,
            "query": query, "source": source_name, "original_summary": summary_text
        })
    return articles

def extract_section(text, start_marker, end_marker):
    try:
        if start_marker in text:
            start = text.find(start_marker) + len(start_marker)
            if end_marker in text[start:]:
                end = text.find(end_marker, start)
                return text[start:end].strip().replace('*', '')
            return text[start:].strip().replace('*', '')
    except: pass
    return "Analiză în curs de actualizare..."

def analyze_with_ai(title, summary, source, query):
    prompt = f"Ești un trader senior. Analizează știrea pentru '{query}': {title}. Răspunde STRICT în acest format: #SENTIMENT# [Pozitiv/Negativ/Neutru] #EMAIL# [Rezumat scurt] #WEB_EXPLICATIE# [Analiză macro] #PUNCTE_FORTE# [Oportunități] #PUNCTE_SLABE# [Riscuri] #INDRUMARE# [Direcția de urmărit] #FINAL#"
    try:
        response = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
        text = response.text
        return (
            extract_section(text, "#SENTIMENT#", "#EMAIL#"),
            extract_section(text, "#EMAIL#", "#WEB_EXPLICATIE#"),
            extract_section(text, "#WEB_EXPLICATIE#", "#PUNCTE_FORTE#"),
            extract_section(text, "#PUNCTE_FORTE#", "#PUNCTE_SLABE#"),
            extract_section(text, "#PUNCTE_SLABE#", "#INDRUMARE#"),
            extract_section(text, "#INDRUMARE#", "#FINAL#")
        )
    except:
        return "Neutru", "N/A", "Analiză indisponibilă momentan.", "-", "-", "Monitorizare niveluri tehnice."

def send_email(articles):
    if not SENDER_EMAIL or not RECEIVER_EMAIL: return
    
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 Raport Trading: {datetime.now().strftime('%d-%m-%Y')}"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECEIVER_EMAIL
    
    body = "<h2>Rezumat de Dimineață</h2><ul>"
    for a in articles:
        body += f"<li><strong>{a['query']}:</strong> {a['email_take']}</li>"
    body += "</ul><p>Vezi terminalul complet aici: <a href='https://naicatheone.github.io/Trading-Terminal/'>Terminal Pro</a></p>"
    
    msg.attach(MIMEText(body, "html"))
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        server.quit()
        print("Email trimis cu succes!")
    except Exception as e: print(f"Eroare email: {e}")

def generate_web_html(articles):
    date_str = datetime.now().strftime("%d-%m-%Y")
    
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
            .logo {{ font-weight: 800; font-size: 20px; color: var(--text-bold); min-width: 150px; }}
            
            .tabs {{ display: flex; gap: 10px; }}
            .tab-btn {{ background: transparent; border: 1px solid var(--border); color: var(--text); padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 13px; transition: 0.2s; }}
            .tab-btn.active {{ background: var(--accent); color: white; border-color: var(--accent); }}

            .header-right {{ display: flex; align-items: center; gap: 20px; min-width: 150px; justify-content: flex-end; }}
            #live-clock {{ font-family: monospace; font-weight: bold; color: var(--accent); font-size: 16px; }}

            .pulse-container {{ margin: 20px 40px; padding: 20px; background: rgba(41, 98, 255, 0.05); border-left: 4px solid var(--accent); border-radius: 4px; }}
            
            .main-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 20px; padding: 0 40px; }}
            .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 20px; transition: 0.3s; }}
            .card.hidden {{ display: none; }}
            
            .badge {{ float: right; padding: 4px 8px; border-radius: 4px; font-size: 10px; font-weight: bold; color: white; }}
            .market-label {{ font-size: 11px; font-weight: 800; color: var(--accent); text-transform: uppercase; }}
            .card-title {{ display: block; margin: 10px 0; color: var(--text-bold); text-decoration: none; font-weight: 700; line-height: 1.4; font-size: 16px; }}
            
            .section-label {{ font-size: 10px; font-weight: 800; color: var(--accent); text-transform: uppercase; margin-top: 15px; border-bottom: 1px solid var(--border); padding-bottom: 4px; }}
            .content-text {{ font-size: 13px; line-height: 1.5; margin-top: 8px; }}
        </style>
    </head>
    <body>
        <header>
            <div class="logo">⬡ TERMINAL PRO</div>
            <div class="tabs">
                <button class="tab-btn active" onclick="filterMarket('all', this)">TOATE</button>
                <button class="tab-btn" onclick="filterMarket('stocks', this)">INDICI & ACȚIUNI</button>
                <button class="tab-btn" onclick="filterMarket('forex', this)">FOREX</button>
                <button class="tab-btn" onclick="filterMarket('crypto', this)">CRYPTO & MARFURI</button>
            </div>
            <div class="header-right">
                <div id="live-clock">00:00:00</div>
                <div style="font-size: 12px; font-weight: bold;">{date_str}</div>
            </div>
        </header>

        <div style="height:40px; overflow:hidden; border-bottom:1px solid var(--border); background: #131722;">
            <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js" async>
            {{
              "symbols": [
                {{"proName":"FOREXCOM:SPXUSD","title":"S&P 500"}},
                {{"proName":"FX_IDC:EURUSD","title":"EUR/USD"}},
                {{"proName":"BITSTAMP:BTCUSD","title":"Bitcoin"}},
                {{"proName":"OANDA:XAUUSD","title":"Gold"}}
              ],
              "colorTheme": "dark", "isTransparent": true, "displayMode": "adaptive", "locale": "en"
            }}
            </script>
        </div>

        <div class="pulse-container">
            <div style="font-weight:800; color:var(--text-bold); font-size:12px; margin-bottom:5px;">● MARKET PULSE AI</div>
            <div style="font-size: 14px; line-height: 1.6;">
                Analiză algoritmică în timp real. Monitorizăm corelațiile inter-market și sentimentul global pentru a identifica direcția fluxului de capital.
            </div>
        </div>

        <div class="main-grid">
    """

    categories = {
        "S&P 500": "stocks", "Nasdaq 100": "stocks", "Apple stock": "stocks", "Tesla stock": "stocks", "Nvidia stock": "stocks",
        "EURUSD": "forex", "GBPUSD": "forex", "USDJPY": "forex",
        "Gold market": "crypto", "WTI Oil": "crypto", "Bitcoin": "crypto"
    }

    for art in articles:
        cat = categories.get(art['query'], "all")
        b_color = "#26a69a" if "Pozitiv" in art['sentiment'] else ("#ef5350" if "Negativ" in art['sentiment'] else "#787b86")
        html += f"""
            <div class="card" data-category="{cat}">
                <span class="badge" style="background:{b_color}">{art['sentiment']}</span>
                <div class="market-label">{art['query']}</div>
                <a href="{art['link']}" class="card-title" target="_blank">{art['title']}</a>
                <div class="section-label">Analiză Macro</div>
                <div class="content-text">{art['web_exp']}</div>
                <div class="section-label">Strategie</div>
                <div class="content-text" style="color:var(--text-bold); font-weight:600;">{art['indrumare']}</div>
            </div>
        """

    html += """
        </div>
        <script>
            function filterMarket(category, btn) {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                document.querySelectorAll('.card').forEach(card => {
                    card.classList.toggle('hidden', category !== 'all' && card.getAttribute('data-category') !== category);
                });
            }
            function updateClock() {
                document.getElementById('live-clock').innerText = new Date().toLocaleTimeString('en-GB');
            }
            setInterval(updateClock, 1000); updateClock();
        </script>
    </body></html>
    """
    return html

def main():
    queries = ["S&P 500", "Nasdaq 100", "Apple stock", "Tesla stock", "Nvidia stock", "EURUSD", "GBPUSD", "USDJPY", "Gold market", "WTI Oil", "Bitcoin"]
    all_articles = []
    
    for q in queries:
        news = fetch_news(q, 1)
        for n in news:
            s, e, w, pf, ps, i = analyze_with_ai(n['title'], n['original_summary'], n['source'], q)
            n.update({'sentiment': s, 'email_take': e, 'web_exp': w, 'puncte_forte': pf, 'puncte_slabe': ps, 'indrumare': i})
            all_articles.append(n)
            time.sleep(1)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(generate_web_html(all_articles))
    
    # Trimite email la ora 06:00 UTC (08:00 RO)
    if datetime.utcnow().hour == 6:
        send_email(all_articles)

if __name__ == "__main__":
    main()
