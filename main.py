# main.py
import os
import sqlite3
import json
from datetime import datetime, date
from collections import Counter
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from apscheduler.schedulers.background import BackgroundScheduler
import openai

# ── Setup ─────────────────────────────────────────
openai.api_key = os.getenv("OPENAI_API_KEY")
app = FastAPI()
chat_memory = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# ── Database setup ─────────────────────────────────
DB_PATH = "chat_logs.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            question TEXT,
            answer TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

def log_message(session_id: str, question: str, answer: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO messages (session_id, question, answer, timestamp) VALUES (?, ?, ?, ?)",
        (session_id, question, answer, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

init_db()

# ── System prompt ──────────────────────────────────
SYSTEM_PROMPT = """
Je bent de digitale assistent van La Cucina Oisterwijk, een ambachtelijke slagerij en delicatessenzaak.

Je bent:
- vriendelijk en warm
- professioneel
- kort en to-the-point

Je helpt websitebezoekers met vragen over het assortiment, openingstijden, locatie, bestellingen en catering.
Je verzint nooit informatie. Als je iets niet weet, zeg je dat eerlijk en verwijs je naar (013) 521 34 92.
"""

LA_CUCINA_KENNIS = """
La Cucina Oisterwijk — Gemullehoekenweg 5, 5061 MA Oisterwijk
Telefoon: (013) 521 34 92
Email: info@lacucinaoisterwijk.nl

Openingstijden:
- Maandag: 13:00 – 18:30
- Dinsdag t/m Donderdag: 08:00 – 18:30
- Vrijdag: 08:00 – 19:00
- Zaterdag: 08:00 – 17:00
- Zondag: Gesloten

Assortiment:
- Ambachtelijk vlees & slagerij
- Tapas & delicatessen
- Barbecuepakketten
- Verse maaltijden & salades
- Verse broodjes
- Buffetten & catering voor feesten en evenementen

Bestellen: klanten kunnen bellen of langskomen om vooraf te bestellen.
"""

# ── Routes ─────────────────────────────────────────
@app.get("/")
def index():
    return FileResponse("index.html")

@app.get("/chat")
def chat(message: str, session_id: str):
    try:
        if session_id not in chat_memory:
            chat_memory[session_id] = []

        chat_memory[session_id].append({"role": "user", "content": message})

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": LA_CUCINA_KENNIS}
        ] + chat_memory[session_id]

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=200
        )

        answer = response["choices"][0]["message"]["content"]

        chat_memory[session_id].append({"role": "assistant", "content": answer})

        # Sla vraag + antwoord op in database
        log_message(session_id, message, answer)

        return {"response": answer}

    except Exception as e:
        return {"response": "Er ging iets mis: " + str(e)}


# ── Dashboard generatie ────────────────────────────
def get_stats(month: str = None):
    """Haal statistieken op uit de database. month = 'YYYY-MM' of None voor alles."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if month:
        c.execute(
            "SELECT question, timestamp FROM messages WHERE timestamp LIKE ?",
            (f"{month}%",)
        )
    else:
        c.execute("SELECT question, timestamp FROM messages")

    rows = c.fetchall()
    conn.close()

    questions = [r[0] for r in rows]
    timestamps = [r[1] for r in rows]

    # Top vragen
    question_counts = Counter(questions).most_common(10)

    # Per dag
    day_counts = Counter(t[:10] for t in timestamps)

    # Per uur
    hour_counts = Counter(t[11:13] for t in timestamps if len(t) > 13)

    return {
        "total": len(questions),
        "top_questions": question_counts,
        "per_day": dict(sorted(day_counts.items())),
        "per_hour": dict(sorted(hour_counts.items())),
    }


def generate_dashboard(month: str = None):
    """Genereer een HTML dashboard voor de gegeven maand."""
    if not month:
        month = datetime.now().strftime("%Y-%m")

    stats = get_stats(month)
    total = stats["total"]
    top_q = stats["top_questions"]
    per_day = stats["per_day"]
    per_hour = stats["per_hour"]

    # Data voor charts
    q_labels = json.dumps([q[0][:60] + "..." if len(q[0]) > 60 else q[0] for q in top_q])
    q_values = json.dumps([q[1] for q in top_q])
    day_labels = json.dumps(list(per_day.keys()))
    day_values = json.dumps(list(per_day.values()))
    hour_labels = json.dumps([f"{h}:00" for h in per_hour.keys()])
    hour_values = json.dumps(list(per_hour.values()))

    month_label = datetime.strptime(month, "%Y-%m").strftime("%B %Y")

    html = f"""<!DOCTYPE html>
<html lang="nl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>La Cucina — Chatbot Rapport {month_label}</title>
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Lato:wght@300;400;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --cream: #f5f0e8;
            --dark: #1a1208;
            --terracotta: #c0622f;
            --gold: #b8973a;
            --brown: #2d1f0e;
            --mid: #5c3d1e;
            --light: #8b6340;
            --text: #3d2b1a;
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: 'Lato', sans-serif;
            background: var(--cream);
            color: var(--text);
            min-height: 100vh;
        }}

        header {{
            background: var(--brown);
            padding: 32px 48px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid var(--gold);
        }}

        .header-left h1 {{
            font-family: 'Playfair Display', serif;
            font-size: 28px;
            color: #e8d5a3;
            letter-spacing: 1px;
        }}

        .header-left p {{
            color: var(--gold);
            font-size: 13px;
            letter-spacing: 3px;
            text-transform: uppercase;
            margin-top: 4px;
        }}

        .header-badge {{
            background: var(--terracotta);
            color: white;
            padding: 8px 20px;
            border-radius: 4px;
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 1px;
            text-transform: uppercase;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 48px 24px;
        }}

        /* KPI cards */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 24px;
            margin-bottom: 48px;
        }}

        .kpi-card {{
            background: var(--brown);
            border-radius: 8px;
            padding: 32px;
            text-align: center;
            border-bottom: 3px solid var(--gold);
            transition: transform 0.2s;
        }}

        .kpi-card:hover {{ transform: translateY(-4px); }}

        .kpi-number {{
            font-family: 'Playfair Display', serif;
            font-size: 52px;
            color: #e8d5a3;
            line-height: 1;
            margin-bottom: 8px;
        }}

        .kpi-label {{
            font-size: 12px;
            letter-spacing: 3px;
            text-transform: uppercase;
            color: var(--gold);
            font-weight: 700;
        }}

        /* Chart cards */
        .charts-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
            margin-bottom: 48px;
        }}

        .chart-card {{
            background: white;
            border-radius: 8px;
            padding: 32px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.06);
            border: 1px solid rgba(0,0,0,0.05);
        }}

        .chart-card.full {{ grid-column: 1 / -1; }}

        .chart-title {{
            font-family: 'Playfair Display', serif;
            font-size: 18px;
            color: var(--brown);
            margin-bottom: 24px;
            padding-bottom: 12px;
            border-bottom: 2px solid var(--cream);
        }}

        canvas {{ max-height: 300px; }}

        /* Top questions table */
        .table-card {{
            background: white;
            border-radius: 8px;
            padding: 32px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.06);
            border: 1px solid rgba(0,0,0,0.05);
            margin-bottom: 48px;
        }}

        table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}

        th {{
            text-align: left;
            font-size: 11px;
            letter-spacing: 2px;
            text-transform: uppercase;
            color: var(--light);
            padding: 12px 16px;
            border-bottom: 2px solid var(--cream);
        }}

        td {{
            padding: 14px 16px;
            font-size: 14px;
            border-bottom: 1px solid var(--cream);
            color: var(--text);
        }}

        tr:last-child td {{ border-bottom: none; }}
        tr:hover td {{ background: var(--cream); }}

        .rank {{
            font-family: 'Playfair Display', serif;
            font-size: 20px;
            color: var(--terracotta);
            font-weight: 700;
            width: 48px;
        }}

        .count-badge {{
            background: var(--terracotta);
            color: white;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
        }}

        footer {{
            text-align: center;
            padding: 32px;
            color: var(--light);
            font-size: 12px;
            letter-spacing: 1px;
            border-top: 1px solid rgba(0,0,0,0.08);
        }}

        @media (max-width: 768px) {{
            .kpi-grid {{ grid-template-columns: 1fr; }}
            .charts-grid {{ grid-template-columns: 1fr; }}
            .chart-card.full {{ grid-column: auto; }}
            header {{ padding: 24px 20px; flex-direction: column; gap: 16px; text-align: center; }}
        }}
    </style>
</head>
<body>

<header>
    <div class="header-left">
        <h1>La Cucina — Chatbot Rapport</h1>
        <p>{month_label}</p>
    </div>
    <div class="header-badge">Maandrapport</div>
</header>

<div class="container">

    <!-- KPI's -->
    <div class="kpi-grid">
        <div class="kpi-card">
            <div class="kpi-number">{total}</div>
            <div class="kpi-label">Totaal vragen</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-number">{len(per_day)}</div>
            <div class="kpi-label">Actieve dagen</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-number">{round(total / max(len(per_day), 1), 1)}</div>
            <div class="kpi-label">Gem. vragen per dag</div>
        </div>
    </div>

    <!-- Charts -->
    <div class="charts-grid">
        <div class="chart-card full">
            <div class="chart-title">📅 Vragen per dag</div>
            <canvas id="dayChart"></canvas>
        </div>
        <div class="chart-card">
            <div class="chart-title">🕐 Vragen per uur</div>
            <canvas id="hourChart"></canvas>
        </div>
        <div class="chart-card">
            <div class="chart-title">🥩 Top 5 onderwerpen</div>
            <canvas id="topChart"></canvas>
        </div>
    </div>

    <!-- Top vragen tabel -->
    <div class="table-card">
        <div class="chart-title">📋 Meest gestelde vragen</div>
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Vraag</th>
                    <th>Aantal keer gesteld</th>
                </tr>
            </thead>
            <tbody>
                {"".join(f'<tr><td class="rank">{i+1}</td><td>{q[0]}</td><td><span class="count-badge">{q[1]}×</span></td></tr>' for i, q in enumerate(top_q))}
            </tbody>
        </table>
    </div>

</div>

<footer>
    Gegenereerd op {datetime.now().strftime("%d %B %Y om %H:%M")} &nbsp;·&nbsp; La Cucina Chatbot Analytics &nbsp;·&nbsp; Powered by AI-Migo
</footer>

<script>
    const terracotta = '#c0622f';
    const gold = '#b8973a';
    const brown = '#2d1f0e';
    const cream = '#f5f0e8';

    // Vragen per dag
    new Chart(document.getElementById('dayChart'), {{
        type: 'bar',
        data: {{
            labels: {day_labels},
            datasets: [{{
                label: 'Vragen',
                data: {day_values},
                backgroundColor: terracotta,
                borderRadius: 4,
            }}]
        }},
        options: {{
            responsive: true,
            plugins: {{ legend: {{ display: false }} }},
            scales: {{
                y: {{ beginAtZero: true, ticks: {{ stepSize: 1 }} }},
            }}
        }}
    }});

    // Vragen per uur
    new Chart(document.getElementById('hourChart'), {{
        type: 'line',
        data: {{
            labels: {hour_labels},
            datasets: [{{
                label: 'Vragen',
                data: {hour_values},
                borderColor: terracotta,
                backgroundColor: 'rgba(192,98,47,0.1)',
                tension: 0.4,
                fill: true,
                pointBackgroundColor: terracotta,
            }}]
        }},
        options: {{
            responsive: true,
            plugins: {{ legend: {{ display: false }} }},
            scales: {{ y: {{ beginAtZero: true, ticks: {{ stepSize: 1 }} }} }}
        }}
    }});

    // Top 5 onderwerpen (donut)
    new Chart(document.getElementById('topChart'), {{
        type: 'doughnut',
        data: {{
            labels: {q_labels},
            datasets: [{{
                data: {q_values},
                backgroundColor: [terracotta, gold, '#a8451f', '#8b6340', '#5c3d1e'],
                borderWidth: 0,
            }}]
        }},
        options: {{
            responsive: true,
            plugins: {{
                legend: {{
                    position: 'bottom',
                    labels: {{ font: {{ size: 11 }}, padding: 16 }}
                }}
            }}
        }}
    }});
</script>

</body>
</html>"""

    # Sla op als bestand
    filename = f"dashboard_{month}.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[AI-Migo] Dashboard gegenereerd: {filename}")
    return filename


# ── Endpoint om dashboard live te bekijken ─────────
@app.get("/dashboard")
def view_dashboard(month: str = None):
    if not month:
        month = datetime.now().strftime("%Y-%m")
    filename = generate_dashboard(month)
    return FileResponse(filename, media_type="text/html")


# ── Maandelijkse scheduler ─────────────────────────
scheduler = BackgroundScheduler()

def monthly_job():
    """Draait op de 1e van elke maand om 08:00 — genereert rapport van vorige maand."""
    last_month = (datetime.now().replace(day=1) - __import__('timedelta', fromlist=['timedelta'])(days=1))
    month_str = last_month.strftime("%Y-%m")
    generate_dashboard(month_str)
    print(f"[AI-Migo] Maandrapport {month_str} automatisch gegenereerd.")

scheduler.add_job(monthly_job, "cron", day=1, hour=8, minute=0)
scheduler.start()
