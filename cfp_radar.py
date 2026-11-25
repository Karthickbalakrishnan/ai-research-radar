import datetime
import json
import os
import smtplib
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

# --- PART 1: Fetch Live CFPs ---
print("1. Fetching live HCI & UX Call for Papers...")
cfp_url = "http://www.wikicfp.com/cfp/call?conference=HCI"
cfp_resp = requests.get(cfp_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
soup = BeautifulSoup(cfp_resp.text, "html.parser")

rows = soup.find_all("tr")
for i in range(len(rows) - 1):
    cols = rows[i].find_all("td")
    if len(cols) == 2 and cols[0].find("a"):
        acronym = cols[0].get_text(strip=True)
        full_name = cols[1].get_text(strip=True)
        link = "http://www.wikicfp.com" + cols[0].find("a")["href"]
        next_cols = rows[i + 1].find_all("td")

        if len(next_cols) == 3 and link not in seen_urls:
            new_items.append(
                f"[CFP] {acronym} - {full_name} | Where: {next_cols[1].get_text(strip=True)} "
                f"| Deadline: {next_cols[2].get_text(strip=True)} | Link: {link}"
            )
            newly_discovered_urls.append(link)

# --- PART 2: Fetch Live Grants ---
print("2. Fetching live technology & human-centered research grants...")
grants_url = "https://api.grants.gov/v1/api/search2"
payload = {
    "keyword": "human computer interaction OR virtual reality OR artificial intelligence education",
    "oppStatuses": "posted",
    "rows": 5,
}

try:
    g_resp = requests.post(grants_url, json=payload, timeout=15).json()
    for hit in g_resp.get("data", {}).get("oppHits", []):
        opp_id = hit.get("id", "")
        grant_link = f"https://www.grants.gov/search-results-detail/{opp_id}"
        if grant_link not in seen_urls:
            new_items.append(
                f"[GRANT] {hit.get('title')} | Agency: {hit.get('agencyName')} "
                f"| Deadline: {hit.get('closeDate', 'Open/Rolling')} "
                f"| Link: {grant_link}"
            )
            newly_discovered_urls.append(grant_link)
except Exception as e:
    print(f"Grants API skipped: {e}")

if not new_items:
    print("No brand-new CFPs or Grants today. Skipping email.")
    exit(0)

combined_feed = "\n".join(new_items[:15])

# --- PART 3: Ask OpenAI for Clean Structured JSON ---
print("3. Synthesizing structured cards with LLM...")
ai_response = client.chat.completions.create(
    model="gpt-4o-mini",
    response_format={"type": "json_object"},
    messages=[
        {
            "role": "system",
            "content": (
                f"You are an academic research strategist. Today is {today_str}. "
                "Filter out expired items and return valid JSON with a single key 'items' containing a list of objects. "
                "Each object must have:\n"
                "- 'type': 'CFP' or 'GRANT'\n"
                "- 'title': clean title or acronym + full name\n"
                "- 'deadline_text': formatted date (e.g., 'Dec 15, 2026')\n"
                "- 'days_left': integer estimate of days remaining (use 999 if rolling/open)\n"
                "- 'location_or_agency': city/country or funding agency\n"
                "- 'relevance': 1 concise sentence on why this matters for UX, HCI, or XR researchers\n"
                "- 'link': exact URL\n"
                "Sort the list so the smallest 'days_left' comes first."
            ),
        },
        {"role": "user", "content": combined_feed},
    ],
)

structured_data = json.loads(ai_response.choices[0].message.content)
cards_data = structured_data.get("items", [])

if not cards_data:
    print("All fetched items were expired. Skipping email.")
    exit(0)

# --- PART 4: Build Clean Light-Mode HTML Template ---
def render_html_email(items):
    urgent_count = sum(1 for item in items if item.get("days_left", 999) <= 30)
    cards_html = ""

    for item in items:
        days = item.get("days_left", 999)
        is_urgent = days <= 30
        item_type = item.get("type", "CFP")

        # Urgency Pill Styling
        if is_urgent:
            badge_bg = "#FEE2E2"
            badge_color = "#B91C1C"
            badge_label = f"URGENT • {days} DAYS LEFT"
        elif days == 999:
            badge_bg = "#E0F2FE"
            badge_color = "#0369A1"
            badge_label = "ROLLING DEADLINE"
        else:
            badge_bg = "#DCFCE7"
            badge_color = "#15803D"
            badge_label = f"{days} DAYS LEFT"

        # Type Tag Styling
        type_bg = "#EDE9FE" if item_type == "CFP" else "#FEF3C7"
        type_color = "#5B21B6" if item_type == "CFP" else "#B45309"

        cards_html += f"""
        <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; padding:20px; margin-bottom:16px;">
          <div style="margin-bottom:10px;">
            <span style="display:inline-block; background:{type_bg}; color:{type_color}; font-size:11px; font-weight:700; padding:4px 10px; border-radius:999px; letter-spacing:0.5px; margin-right:6px;">
              {item_type}
            </span>
            <span style="display:inline-block; background:{badge_bg}; color:{badge_color}; font-size:11px; font-weight:700; padding:4px 10px; border-radius:999px; letter-spacing:0.5px;">
              {badge_label}
            </span>
          </div>

          <h2 style="margin:0 0 8px 0; font-size:17px; line-height:1.4; color:#0F172A; font-weight:700;">
            {item.get('title')}
          </h2>

          <p style="margin:0 0 12px 0; font-size:13px; color:#64748B;">
            <strong>Deadline:</strong> {item.get('deadline_text')} &nbsp;•&nbsp; <strong>Host:</strong> {item.get('location_or_agency')}
          </p>

          <p style="margin:0 0 16px 0; font-size:14px; line-height:1.55; color:#334155;">
            {item.get('relevance')}
          </p>

          <a href="{item.get('link')}" style="display:inline-block; background:#2563EB; color:#FFFFFF; text-decoration:none; font-size:13px; font-weight:600; padding:9px 16px; border-radius:8px;">
            View Call &amp; Guidelines &rarr;
          </a>
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <body style="margin:0; padding:0; background-color:#F8FAFC; font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
      <div style="max-width:620px; margin:24px auto; padding:0 16px;">

        <!-- Header Banner -->
        <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:14px; padding:24px; margin-bottom:20px;">
          <p style="margin:0 0 4px 0; font-size:12px; font-weight:700; color:#2563EB; text-transform:uppercase; letter-spacing:0.8px;">
            Daily Research Intelligence • {today_str}
          </p>
          <h1 style="margin:0 0 12px 0; font-size:22px; color:#0F172A; font-weight:800;">
            UX, HCI &amp; XR Opportunity Radar
          </h1>
          <div style="display:inline-block; background:#F1F5F9; border-radius:8px; padding:8px 14px; font-size:13px; color:#334155;">
            <strong>{len(items)}</strong> New Opportunities &nbsp;|&nbsp; <strong style="color:#B91C1C;">{urgent_count}</strong> Closing Within 30 Days
          </div>
        </div>

        <!-- Opportunity Cards -->
        {cards_html}

        <!-- Footer -->
        <p style="text-align:center; font-size:12px; color:#94A3B8; margin-top:24px;">
          Automated 9:00 AM Digest • Deduplicated via seen_events.json
        </p>
      </div>
    </body>
    </html>
    """

html_report = render_html_email(cards_data)

# --- PART 5: Send Multipart Email (Plain Text Fallback + Rich HTML) ---
print("4. Sending HTML digest to Gmail...")
msg = EmailMessage()
msg["Subject"] = f"9:00 AM Radar: {len(cards_data)} New UX/HCI Opportunities ({today_str})"
msg["From"] = GMAIL_USER
msg["To"] = GMAIL_USER

# Plain-text fallback for smartwatches/notifications
plain_fallback = "\n\n".join(
    [f"[{i['type']}] {i['title']} (Due: {i['deadline_text']}) - {i['link']}" for i in cards_data]
)
msg.set_content(plain_fallback)
msg.add_alternative(html_report, subtype="html")

with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
    smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
    smtp.send_message(msg)

seen_urls.update(newly_discovered_urls)
save_seen_urls(seen_urls)
print("Success! Clean HTML card digest sent to Gmail.")