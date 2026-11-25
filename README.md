# 📡 9:00 AM AI Research & Opportunity Radar

A lightweight, automated Python + LLM pipeline that fetches live academic papers, conference Call for Papers (CFPs), research grants, and industry updates—filters out noise using OpenAI—and delivers a clean, color-coded HTML briefing directly to your Gmail every morning at 9:00 AM.

## ✨ Key Features

* **Multi-Source Live Ingestion:** Automatically pulls fresh preprints from **ArXiv**, upcoming conferences/workshops from **WikiCFP**, and real-time funding/SDK updates via **RSS feeds**.
* **Strict LLM Gatekeeper:** Uses OpenAI (`gpt-4o-mini` with Structured JSON Outputs) to discard expired deadlines, summarize takeaways in one sentence, and cap daily results at **8 high-signal items**.
* **Deduplication Memory (`seen_events.json`):** Remembers previously emailed URLs so you never receive duplicate alerts—and skips sending an email completely if nothing new appeared overnight.
* **Dual-View Clean UI:**
  * **Gmail HTML Digest:** Responsive, light-mode folder cards with clickable jump-link tabs and urgency badges (`< 30d left`).
  * **Local Interactive Dashboard (`dashboard.html`):** Auto-generates a local web page with real click-to-switch JavaScript tabs.

---

## 🛠️ Prerequisites

* **Python 3.10+** installed on your machine
* An **OpenAI API Key** ([platform.openai.com](https://platform.openai.com/))
* A **Gmail Account** with **2-Step Verification** enabled (to generate an App Password)

---

## 🚀 Quick Start (5-Minute Setup)

### 1. Clone the Repository
```bash
git clone [https://github.com/yourusername/your-repo-name.git](https://github.com/yourusername/your-repo-name.git)
cd your-repo-name