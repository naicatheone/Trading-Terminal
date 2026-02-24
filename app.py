import feedparser
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import quote
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time

from google import genai
from google.genai import types

# --- CONFIGURARE CREDENTIALE DIN SEIF (SECRETS) ---
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
RECEIVER_EMAIL = os.environ.get("RECEIVER_EMAIL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)

def fetch_news(query, num_articles=1):
    rss_url = f"https://news.google.com/rss/search?q={quote(query)}"
    feed = feedparser.parse(rss_url)
    news_items = feed.entries[:num_articles]
    articles = []
    for item in news_items:
        source_name = item.source.title if hasattr(item, 'source') and hasattr(item.source, 'title') else "Sursă"
        soup = BeautifulSoup(item.summary, 'html.parser') if hasattr(item, 'summary') else None
        summary_text = soup.get_text(separator=" ").strip() if soup else ""
        articles.append({
            "title": item.title, "link": item.link, "published": item.published,
            "query": query, "source": source_name, "original_summary": summary_text
        })
    return articles

def extract_section(text, start_marker, end_marker):
    start = text.find(start_marker)
    if start == -1: return "Informație indisponibilă."
    start += len(start_marker)
    end = text.find(end_marker, start)
    if end == -1: return text[start:].strip()
    return text[start:end].strip()

def analyze_with_ai(title, summary, source, query):
    prompt = f"""
    Ești un trader senior. Analizează știrea '{query}': {title}. Sursa: {source}. Detalii: {summary}
    Fii concis, clar și folosește un limbaj profesional, structurat.
    
    Răspunde STRICT folosind aceste etichete:
    #SENTIMENT# [Pozitiv/Negativ/Neutru]
    #EMAIL# [Rezumat scurt de maxim 2 propoziții]
    #WEB_EXPLICATIE# [Analiză macro: 2-3 propoziții clare despre context]
    #PUNCTE_FORTE# [Scrie 1-2 idei scurte, tip listă cu liniuță, despre oportunități/bullish]
    #PUNCTE_SLABE# [Scrie 1-2 idei scurte, tip listă cu liniuță, despre riscuri/bearish]
    #INDRUMARE# [O frază clară cu direcția sau nivelurile la care să fim atenți]
    #FINAL#
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                safety_settings=[
                    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
                ]
            )
        )
        text = response.text
        return (
            extract_section(text, "#SENTIMENT#", "#EMAIL#").replace('*', '').strip(),
            extract_section(text, "#EMAIL#", "#WEB_EXPLICATIE#"),
            extract_section(text, "#WEB_EXPLICATIE#", "#PUNCTE_FORTE#"),
            extract_section(text, "#PUNCTE_FORTE#", "#PUNCTE_SLABE#"),
            extract_section(text, "#PUNCTE_SLABE#", "#INDRUMARE#"),
            extract_section(text, "#INDRUMARE#", "#FINAL#")
        )
    except Exception as e:
        print(f"\n  [!] EROARE LA GEMINI API PENTRU '{query}': {e}\n")
        return "Neutru", "Eroare AI", "Nu am putut analiza din cauza unei erori la serverul AI.", "-", "-", "-"

def generate_email_html(articles):
    date_str = datetime.now().strftime("%d-%m-%Y")
    html = f"""
    <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #f4f6f9; color: #333; padding: 20px;">
        <div style="max-width: 650px; margin: auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; overflow:hidden;">
            <div style="padding: 20px; background-color: #1a202c; border-bottom: 4px solid #2962ff; text-align: center;">
                <h2 style="margin:0; color: #ffffff; letter-spacing: 1px; font-size: 20px;">📊 TRADING BRIEFING</h2>
                <p style="margin: 5px 0 0 0; color: #a0aec0; font-size: 12px;">Sinteza matinală • {date_str}</p>
            </div>
            <div style="padding: 25px;">
    """
    for art in articles:
        html += f"""
                <div style="margin-bottom: 25px; padding-bottom: 20px; border-bottom: 1px dashed #e2e8f0;">
                    <span style="font-size: 11px; font-weight: bold; color: #2962ff; text-transform: uppercase; letter-spacing: 1px;">{art['query']}</span>
                    <a href='{art['link']}' style='display: block; color: #1a202c; font-size: 16px; font-weight: bold; text-decoration: none; margin: 8px 0; line-height: 1.4;'>{art['title']}</a>
                    <p style='color: #4a5568; font-size: 14px; margin: 0; line-height: 1.6;'>{art['email_take']}</p>
                </div>
        """
    html += "</div></div></body>"
    return html

def generate_web_html(articles):
    date_str = datetime.now().strftime("%d-%m-%Y")
    html = f"""
    <!DOCTYPE html>
    <html lang="ro" data-theme="dark">
    <head>
        <meta charset="utf-8">
        <title>Pro Trading Terminal</title>
        <style>
            :root[data-theme="dark"] {{
                --bg: #0b0e11; --card: #181a20; --text: #b7bdc6; --text-bold: #ffffff; --text-muted: #848e9c; 
                --border: #2b3139; --accent: #2962ff; --accent-bg: rgba(41, 98, 255, 0.1);
            }}
            :root[data-theme="light"] {{
                --bg: #f0f2f5; --card: #ffffff; --text: #4a5568; --text-bold: #1a202c; --text-muted: #718096; 
                --border: #e2e8f0; --accent: #2962ff; --accent-bg: rgba(41, 98, 255, 0.05);
            }}
            body {{ background-color: var(--bg); color: var(--text); font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; transition: all 0.3s ease; }}
            
            /* HEADER */
            header {{ background-color: var(--card); border-bottom: 1px solid var(--border); padding: 15px 40px; display: flex; justify-content: space-between; align-items: center; position: sticky; top:0; z-index: 100; }}
            
            /* TOGGLE BUTTON */
            .theme-toggle-container {{ display: flex; align-items: center; gap: 12px; cursor: pointer; user-select: none; }}
            .theme-icon {{ width: 20px; height: 20px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; color: var(--text-bold); }}
            .theme-label {{ font-size: 14px; color: var(--text-bold); font-weight: 500; }}
            .toggle-pill {{ width: 44px; height: 24px; border-radius: 12px; background-color: #cbd5e1; position: relative; transition: 0.3s; display: flex; align-items: center; }}
            .toggle-circle {{ width: 18px; height: 18px; background-color: #ffffff; border-radius: 50%; position: absolute; left: 3px; transition: transform 0.3s cubic-bezier(0.4, 0.0, 0.2, 1); box-shadow: 0 1px 3px rgba(0,0,0,0.2); }}
            
            [data-theme="dark"] .toggle-pill {{ background-color: #3b82f6; }}
            [data-theme="dark"] .toggle-circle {{ background-color: #ffffff; transform: translateX(20px); }}

            /* GRID & CARDS */
            .container {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 25px; padding: 40px; max-width: 1600px; margin: auto; }}
            .card {{ background-color: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 30px; transition: transform 0.2s, border-color 0.2s; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }}
            .card:hover {{ border-color: var(--accent); transform: translateY(-3px); box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1); }}
            
            /* LABELS & TITLES */
            .card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }}
            .market-tag {{ font-size: 12px; color: var(--text-muted); font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }}
            .badge {{ padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 800; color: white; text-transform: uppercase; letter-spacing: 0.5px; }}
            .title {{ color: var(--text-bold); font-size: 18px; text-decoration: none; font-weight: 700; display: block; margin-bottom: 25px; line-height: 1.4; transition: color 0.2s; }}
            .title:hover {{ color: var(--accent); }}
            
            /* SECTION STRUCTURING */
            .section-title {{ font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1.5px; font-weight: 800; margin: 25px 0 10px 0; border-bottom: 1px solid var(--border); padding-bottom: 6px; display: flex; align-items: center; gap: 8px; }}
            .text-content {{ font-size: 14px; line-height: 1.7; color: var(--text); margin-top: 0; }}
            
            /* PROS / CONS BOXES */
            .pros-cons-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 15px; }}
            .box {{ padding: 15px; border-radius: 8px; font-size: 13.5px; line-height: 1.6; color: var(--text); }}
            .box strong {{ display: block; margin-bottom: 8px; font-size: 12px; letter-spacing: 0.5px; }}
            .pro {{ background: rgba(38, 166, 154, 0.05); border-left: 3px solid #26a69a; }}
            .pro strong {{ color: #26a69a; }}
            .con {{ background: rgba(239, 83, 80, 0.05); border-left: 3px solid #ef5350; }}
            .con strong {{ color: #ef5350; }}
            
            /* ACTION BOX */
            .action-box {{ margin-top: 25px; padding: 18px; background: var(--accent-bg); border-left: 4px solid var(--accent); border-radius: 0 8px 8px 0; font-size: 14.5px; font-weight: 500; color: var(--text-bold); line-height: 1.6; display: flex; gap: 12px; }}
        </style>
    </head>
    <body>
        <header>
            <div style="font-weight: 800; color: var(--text-bold); font-size: 20px; letter-spacing: 1px;">
                <span style="color: var(--accent);">⬡</span> TERMINAL PRO
            </div>
            <div style="display:flex; align-items:center; gap:30px;">
                <span style="font-size:13px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 1px;">Actualizat: {date_str}</span>
                <div class="theme-toggle-container" onclick="toggleTheme()">
                    <svg id="theme-icon" class="theme-icon" viewBox="0 0 24 24">
                        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
                    </svg>
                    <span class="theme-label" id="theme-text">Dark theme</span>
                    <div class="toggle-pill"><div class="toggle-circle"></div></div>
                </div>
            </div>
        </header>
        <div class="container">
    """
    for art in articles:
        badge_color = "#26a69a" if "Pozitiv" in art['sentiment'] else ("#ef5350" if "Negativ" in art['sentiment'] else "#787b86")
        
        # Curățăm formatarea cu asteriscuri lăsată uneori de AI pentru a păstra aspectul curat
        puncte_forte_curat = art['puncte_forte'].replace('*', '')
        puncte_slabe_curat = art['puncte_slabe'].replace('*', '')

        html += f"""
            <div class="card">
                <div class="card-header">
                    <span class="market-tag">{art['query']}</span>
                    <span class="badge" style="background:{badge_color};">{art['sentiment']}</span>
                </div>
                
                <a href="{art['link']}" class="title" target="_blank">{art['title']}</a>
                
                <div class="section-title">📊 CONTEXT MACRO</div>
                <p class="text-content">{art['web_exp']}</p>
                
                <div class="section-title">⚖️ ARGUMENTE PIAȚĂ</div>
                <div class="pros-cons-grid">
                    <div class="box pro">
                        <strong>BULLISH FACTORS</strong>
                        {puncte_forte_curat}
                    </div>
                    <div class="box con">
                        <strong>BEARISH RISKS</strong>
                        {puncte_slabe_curat}
                    </div>
                </div>
                
                <div class="action-box">
                    <span style="font-size: 18px;">🎯</span> 
                    <div>{art['indrumare']}</div>
                </div>
            </div>
        """
    html += """
        </div>
        <script>
            function toggleTheme() {
                const html = document.documentElement;
                const text = document.getElementById('theme-text');
                const icon = document.getElementById('theme-icon');
                
                if (html.getAttribute('data-theme') === 'dark') {
                    html.setAttribute('data-theme', 'light');
                    localStorage.setItem('pref-theme', 'light');
                    text.innerText = 'Light theme';
                    icon.innerHTML = '<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>';
                } else {
                    html.setAttribute('data-theme', 'dark');
                    localStorage.setItem('pref-theme', 'dark');
                    text.innerText = 'Dark theme';
                    icon.innerHTML = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>';
                }
            }
            const saved = localStorage.getItem('pref-theme') || 'dark';
            if (saved === 'light') toggleTheme(); 
        </script>
    </body>
    </html>
    """
    return html

def send_email(html_content):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"📊 Analiză Piață: {datetime.now().strftime('%d-%m-%Y')}"
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECEIVER_EMAIL
        msg.attach(MIMEText(html_content, "html"))
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        server.quit()
        print("\n✅ Email-ul a fost trimis cu succes!")
    except Exception as e:
        print(f"\n❌ Eroare la trimiterea emailului: {e}")

def main():
    queries = ["Gold market", "WTI Oil", "EURUSD", "GBPUSD", "USDJPY", "Bitcoin", "S&P 500", "Nasdaq 100", "Apple stock", "Tesla stock", "Nvidia stock"]
    all_articles = []
    print("🤖 Se pornește analiza terminalului...")
    for q in queries:
        print(f"-> Caut știri: {q}")
        articles = fetch_news(q, 1)
        for a in articles:
            s, e, w, pf, ps, i = analyze_with_ai(a['title'], a['original_summary'], a['source'], q)
            a.update({'sentiment': s, 'email_take': e, 'web_exp': w, 'puncte_forte': pf, 'puncte_slabe': ps, 'indrumare': i})
            all_articles.append(a)
            time.sleep(6) # Pauza ca sa evitam limitarile API
            
    print("\nGenerăm interfețele...")
    with open("index.html", "w", encoding="utf-8") as f: 
        f.write(generate_web_html(all_articles))
    
    send_email(generate_email_html(all_articles))
    print("🎉 Gata! Deschide index.html pentru terminal și verifică-ți emailul.")

if __name__ == "__main__":
    main()
