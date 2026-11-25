import datetime
import json
import os
import smtplib
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.message import EmailMessage
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

client = OpenAI()
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
MEMORY_FILE = BASE_DIR / "seen_events.json"
DASHBOARD_FILE = BASE_DIR / "dashboard.html"
today_str = datetime.date.today().strftime("%B %d, %Y")

def load_seen_urls():
    if MEMORY_FILE.exists():
        with open(MEMORY_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen_urls(seen_set):
    with open(MEMORY_FILE, "w") as f:
        json.dump(sorted(list(seen_set)), f, indent=2)

seen_urls = load_seen_urls()
new_items = []
newly_discovered_urls = []

# --- SOURCE 1: Live Research Papers (ArXiv cs.HC) ---
print("1. Fetching latest ArXiv HCI/XR/Psychology papers...")
arxiv_query = urllib.parse.quote(
    'cat:cs.HC AND ("virtual reality" OR "adaptive" OR "cognitive load" OR "visual guidance" OR "user experience")'
)
arxiv_url = f"http://export.arxiv.org/api/query?search_query={arxiv_query}&sortBy=submittedDate&sortOrder=descending&max_results=6"

try:
    arxiv_xml = urllib.request.urlopen(arxiv_url, timeout=12).read()
    root = ET.fromstring(arxiv_xml)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for entry in root.findall("atom:entry", ns):
        title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
        summary = entry.find("atom:summary", ns).text.strip().replace("\n", " ")[:350]
        link = entry.find("atom:id", ns).text.strip()
        published = entry.find("atom:published", ns).text[:10]
        if link not in seen_urls and link not in newly_discovered_urls:
            new_items.append(
                f"[PAPER] {title} | Published: {published} | Abstract: {summary}... | Link: {link}"
            )
            newly_discovered_urls.append(link)
except Exception as e:
    print(f"ArXiv skipped: {e}")

# --- SOURCE 2: Live Conferences, Workshops & Journals (WikiCFP) ---
print("2. Fetching live Conferences, Workshops & Journals...")
for kw in ["HCI", "UX", "virtual reality", "psychology"]:
    cfp_url = f"http://www.wikicfp.com/cfp/call?conference={urllib.parse.quote(kw)}"
    try:
        resp = requests.get(cfp_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.find_all("tr")
        for i in range(len(rows) - 1):
            cols = rows[i].find_all("td")
            if len(cols) == 2 and cols[0].find("a"):
                acronym = cols[0].get_text(strip=True)
                full_name = cols[1].get_text(strip=True)
                link = "http://www.wikicfp.com" + cols[0].find("a")["href"]
                next_cols = rows[i + 1].find_all("td")
                if len(next_cols) == 3 and link not in seen_urls and link not in newly_discovered_urls:
                    new_items.append(
                        f"[CONFERENCE - {kw.upper()}] {acronym}: {full_name} "
                        f"| Where: {next_cols[1].get_text(strip=True)} "
                        f"| Deadline: {next_cols[2].get_text(strip=True)} | Link: {link}"
                    )
                    newly_discovered_urls.append(link)
    except Exception as e:
        print(f"WikiCFP '{kw}' skipped: {e}")

# --- SOURCE 3: Fellowships, Grants & XR/Tech Updates ---
print("3. Fetching Fellowships, Grants & XR/Tech updates...")
rss_topics = {
    "FELLOWSHIP": '("PhD fellowship" OR "dissertation grant" OR "doctoral consortium") AND ("HCI" OR "human computer interaction" OR "virtual reality")',
    "XR_TECH": '("WebXR" OR "OpenXR" OR "Meta Quest SDK" OR "spatial computing") AND (update OR release OR patent)',
}

for tag, raw_q in rss_topics.items():
    rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(raw_q)}&hl=en-US&gl=US&ceid=US:en"
    try:
        rss_xml = requests.get(rss_url, timeout=12).content
        root = ET.fromstring(rss_xml)
        for item in root.findall("./channel/item")[:4]:
            title = item.find("title").text
            link = item.find("link").text
            pub_date = item.find("pubDate").text[:16] if item.find("pubDate") is not None else ""
            if link not in seen_urls and link not in newly_discovered_urls:
                new_items.append(f"[{tag}] {title} | Date: {pub_date} | Link: {link}")
                newly_discovered_urls.append(link)
    except Exception as e:
        print(f"RSS '{tag}' skipped: {e}")

if not new_items:
    print("Zero noise: No brand-new items across your 5 pillars today. Skipping email.")
    exit(0)

# --- PART 4: Strict Relevance Gatekeeper (Max 8 High-Signal Items) ---
print(f"4. Filtering {len(new_items)} candidates into 5 focused topic tabs...")
ai_response = client.chat.completions.create(
    model="gpt-4o-mini",
    response_format={"type": "json_object"},
    messages=[
        {
            "role": "system",
            "content": (
                f"You are a senior HCI/XR PhD & UX Strategy research assistant. Today is {today_str}. "
                "Select AT MOST 8 highest-signal, non-expired items from the raw feed below. "
                "Classify each item into ONE of these exact 5 categories:\n"
                "1. 'PAPERS' (ArXiv/academic studies on HCI, UX, adaptive VR training, cognitive load, visual guidance)\n"
                "2. 'CONFERENCES' (CFPs, workshops, posters, journal tracks in HCI, UX, XR, Psychology)\n"
                "3. 'FELLOWSHIPS' (PhD grants, dissertation awards, travel scholarships, doctoral consortia)\n"
                "4. 'XR & TECH' (Major WebXR/OpenXR/Quest SDK releases, spatial UI patterns, or XR patents)\n"
                "5. 'PSYCHOLOGY' (Cognitive/behavioral psychology studies or UX behavioral frameworks)\n\n"
                "Output valid JSON with key 'items', each object containing:\n"
                "- 'category': exact string from the 5 categories above\n"
                "- 'title': crisp, informative title\n"
                "- 'meta': Deadline & Venue (for events) OR Date & Source/Methodology (for papers/news)\n"
                "- 'days_left': integer days remaining until deadline (use 999 for papers/news/rolling)\n"
                "- 'takeaway': 1 sharp, practical sentence explaining why this matters for the user's research or UX work\n"
                "- 'link': exact URL"
            ),
        },
        {"role": "user", "content": "\n".join(new_items[:35])},
    ],
)

cards_data = json.loads(ai_response.choices[0].message.content).get("items", [])

if not cards_data:
    print("Nothing passed the relevance threshold today. Skipping email.")
    exit(0)

TABS_CONFIG = [
    {"id": "tab-papers", "key": "PAPERS", "label": "Papers", "accent": "#0D9488", "soft_bg": "#CCFBF1"},
    {"id": "tab-conferences", "key": "CONFERENCES", "label": "Conferences", "accent": "#4F46E5", "soft_bg": "#EEF2FF"},
    {"id": "tab-fellowships", "key": "FELLOWSHIPS", "label": "Grants", "accent": "#7C3AED", "soft_bg": "#F3E8FF"},
    {"id": "tab-xr", "key": "XR & TECH", "label": "XR & Tech", "accent": "#0284C7", "soft_bg": "#E0F2FE"},
    {"id": "tab-psych", "key": "PSYCHOLOGY", "label": "Psychology", "accent": "#BE185D", "soft_bg": "#FCE7F3"},
]

def group_items(items):
    grouped = {tab["key"]: [] for tab in TABS_CONFIG}
    for item in items:
        cat = item.get("category", "CONFERENCES").upper()
        if cat in grouped:
            grouped[cat].append(item)
        else:
            grouped["CONFERENCES"].append(item)
    return grouped

# --- PART 5A: Gmail HTML Template (Jump-Link Tabs + Folder Sections) ---
def render_email_html(items):
    grouped = group_items(items)

    tab_cells = ""
    for tab in TABS_CONFIG:
        count = len(grouped[tab["key"]])
        opacity = "1.0" if count > 0 else "0.4"
        border_b = f"3px solid {tab['accent']}" if count > 0 else "1px solid #F1F5F9"
        href_attr = f'href="#{tab["id"]}"' if count > 0 else ""

        tab_cells += f"""
        <td style="width:20%; text-align:center; padding:12px 4px; border-bottom:{border_b}; opacity:{opacity};">
          <a {href_attr} style="text-decoration:none; display:block;">
            <div style="font-size:11px; font-weight:700; color:{tab['accent']};">{tab['label']}</div>
            <div style="margin-top:4px; display:inline-block; background:{tab['soft_bg']}; color:{tab['accent']}; font-size:11px; font-weight:800; padding:2px 8px; border-radius:999px;">
              {count}
            </div>
          </a>
        </td>
        """

    sections_html = ""
    for tab in TABS_CONFIG:
        tab_items = grouped[tab["key"]]
        if not tab_items:
            continue

        cards_html = ""
        for idx, item in enumerate(tab_items):
            days = item.get("days_left", 999)
            border_top = "1px solid #F1F5F9" if idx > 0 else "none"
            urgency_badge = ""
            if days <= 30:
                urgency_badge = f"""
                <span style="display:inline-block; background:#FEE2E2; color:#B91C1C; font-size:11px; font-weight:700; padding:2px 8px; border-radius:6px; margin-left:6px;">
                  {days}d left
                </span>"""

            cards_html += f"""
            <div style="padding:16px 20px; border-top:{border_top};">
              <div style="margin-bottom:5px;">
                <span style="font-size:15px; font-weight:700; color:#0F172A; line-height:1.4;">
                  {item.get('title')}
                </span>
                {urgency_badge}
              </div>
              <div style="font-size:12px; color:#64748B; margin-bottom:8px; font-weight:500;">
                {item.get('meta')}
              </div>
              <p style="margin:0 0 12px 0; font-size:14px; line-height:1.55; color:#334155;">
                {item.get('takeaway')}
              </p>
              <a href="{item.get('link')}" style="display:inline-block; background:{tab['soft_bg']}; color:{tab['accent']}; border:1px solid {tab['accent']}33; text-decoration:none; font-size:12px; font-weight:700; padding:6px 13px; border-radius:8px;">
                Open Source &rarr;
              </a>
            </div>
            """

        sections_html += f"""
        <div id="{tab['id']}" style="margin-bottom:22px;">
          <div style="display:inline-block; background:{tab['accent']}; color:#FFFFFF; font-size:11px; font-weight:700; padding:6px 14px; border-radius:9px 9px 0 0; letter-spacing:0.5px;">
            {tab['label'].upper()} &nbsp;({len(tab_items)})
          </div>
          <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-top:3px solid {tab['accent']}; border-radius:0 12px 12px 12px; box-shadow:0 1px 3px rgba(15,23,42,0.04);">
            {cards_html}
          </div>
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <body style="margin:0; padding:0; background-color:#F8FAFC; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
      <div style="max-width:620px; margin:24px auto; padding:0 14px;">
        <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:14px; overflow:hidden; margin-bottom:20px; box-shadow:0 1px 3px rgba(15,23,42,0.04);">
          <div style="padding:18px 22px 12px 22px;">
            <div style="font-size:11px; font-weight:700; color:#2563EB; text-transform:uppercase; letter-spacing:0.8px;">
              9:00 AM Research Radar • {today_str}
            </div>
            <h1 style="margin:4px 0 0 0; font-size:19px; color:#0F172A; font-weight:800;">
              Papers, Conferences, Grants &amp; XR Intel
            </h1>
          </div>
          <table role="presentation" style="width:100%; border-collapse:collapse; border-top:1px solid #F1F5F9; background:#FAFAFA;">
            <tr>{tab_cells}</tr>
          </table>
        </div>
        {sections_html}
        <p style="text-align:center; font-size:11px; color:#94A3B8; margin:18px 0;">
          Tap any tab above to jump to that section • Capped at 8 items
        </p>
      </div>
    </body>
    </html>
    """

# --- PART 5B: Interactive Local Browser Dashboard (Real Clickable Tabs) ---
def save_interactive_dashboard(items):
    grouped = group_items(items)
    buttons_html = ""
    panels_html = ""
    first_active = True

    for tab in TABS_CONFIG:
        tab_items = grouped[tab["key"]]
        count = len(tab_items)
        active_cls = "active" if (first_active and count > 0) else ""
        if active_cls:
            first_active = False

        buttons_html += f"""
        <button class="tab-btn {active_cls}" data-target="{tab['id']}" style="--accent:{tab['accent']}; --soft:{tab['soft_bg']};">
          {tab['label']} <span class="badge">{count}</span>
        </button>
        """

        cards = ""
        if not tab_items:
            cards = '<p style="color:#64748B; padding:24px; text-align:center;">No new items in this category today.</p>'
        else:
            for item in tab_items:
                days = item.get("days_left", 999)
                urg = f'<span class="urg">{days}d left</span>' if days <= 30 else ""
                cards += f"""
                <div class="card">
                  <div class="card-title">{item.get('title')} {urg}</div>
                  <div class="card-meta">{item.get('meta')}</div>
                  <p class="card-body">{item.get('takeaway')}</p>
                  <a class="btn" href="{item.get('link')}" target="_blank" style="background:{tab['soft_bg']}; color:{tab['accent']};">Open Source &rarr;</a>
                </div>
                """

        panels_html += f'<div id="{tab["id"]}" class="tab-panel {active_cls}">{cards}</div>'

    dashboard_html = f"""<!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Research Radar • {today_str}</title>
      <style>
        body {{ margin:0; background:#F8FAFC; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color:#0F172A; }}
        .wrap {{ max-width:680px; margin:32px auto; padding:0 16px; }}
        .header {{ background:#FFF; border:1px solid #E2E8F0; border-radius:14px; padding:22px 24px 0; margin-bottom:20px; }}
        .tabs {{ display:flex; gap:8px; margin-top:16px; border-top:1px solid #F1F5F9; padding-top:12px; overflow-x:auto; }}
        .tab-btn {{ border:none; background:transparent; padding:10px 14px; font-size:13px; font-weight:700; color:#64748B; cursor:pointer; border-bottom:3px solid transparent; transition:0.15s; }}
        .tab-btn.active {{ color:var(--accent); border-bottom-color:var(--accent); }}
        .badge {{ background:var(--soft); color:var(--accent); padding:2px 8px; border-radius:999px; font-size:11px; margin-left:4px; }}
        .tab-panel {{ display:none; }}
        .tab-panel.active {{ display:block; }}
        .card {{ background:#FFF; border:1px solid #E2E8F0; border-radius:12px; padding:20px; margin-bottom:14px; }}
        .card-title {{ font-size:16px; font-weight:700; margin-bottom:6px; }}
        .card-meta {{ font-size:12px; color:#64748B; margin-bottom:10px; }}
        .card-body {{ font-size:14px; line-height:1.55; color:#334155; margin:0 0 14px; }}
        .btn {{ display:inline-block; text-decoration:none; font-size:12px; font-weight:700; padding:7px 14px; border-radius:8px; }}
        .urg {{ background:#FEE2E2; color:#B91C1C; font-size:11px; padding:2px 8px; border-radius:6px; margin-left:6px; }}
      </style>
    </head>
    <body>
      <div class="wrap">
        <div class="header">
          <div style="font-size:11px; font-weight:700; color:#2563EB; text-transform:uppercase;">Daily Research Radar • {today_str}</div>
          <h1 style="margin:4px 0 0; font-size:21px;">Papers, Conferences, Grants &amp; XR Intel</h1>
          <div class="tabs">{buttons_html}</div>
        </div>
        {panels_html}
      </div>
      <script>
        document.querySelectorAll('.tab-btn').forEach(btn => {{
          btn.addEventListener('click', () => {{
            document.querySelectorAll('.tab-btn, .tab-panel').forEach(el => el.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById(btn.dataset.target).classList.add('active');
          }});
        }});
      </script>
    </body>
    </html>"""
    with open(DASHBOARD_FILE, "w", encoding="utf-8") as f:
        f.write(dashboard_html)

# --- PART 6: Send Email, Save Local Tabbed Dashboard & Update Memory ---
save_interactive_dashboard(cards_data)

print("5. Sending 5-pillar HTML digest to Gmail...")
msg = EmailMessage()
msg["Subject"] = f"9:00 AM Radar: {len(cards_data)} Updates (Papers • CFPs • Grants • XR • Psych)"
msg["From"] = GMAIL_USER
msg["To"] = GMAIL_USER

plain_text = "\n\n".join([f"[{i['category']}] {i['title']} - {i['link']}" for i in cards_data])
msg.set_content(plain_text)
msg.add_alternative(render_email_html(cards_data), subtype="html")

with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
    smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
    smtp.send_message(msg)

seen_urls.update(newly_discovered_urls)
save_seen_urls(seen_urls)
print(f"Success! Sent {len(cards_data)} cards to Gmail and updated dashboard.html.")