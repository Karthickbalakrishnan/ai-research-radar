# AI Research Radar

A small Python application that gathers research and opportunity updates, uses OpenAI to select and summarize the most relevant items, then delivers a daily-style digest by email and as a local interactive dashboard.

It is designed for researchers and practitioners working in **HCI, UX, XR, psychology, and related fields** who want one focused place to review new papers, calls for papers, funding opportunities, and technology updates.

## What it does

On each run, the application:

1. Retrieves recent HCI-related papers from **arXiv**.
2. Searches **WikiCFP** for conferences and workshops matching HCI, UX, virtual reality, and psychology.
3. Checks **Google News RSS** for fellowship/grant and XR technology news.
4. Sends up to 35 collected candidates to **OpenAI (`gpt-4o-mini`)** for relevance filtering, categorization, and concise practical takeaways. The digest is capped at eight items.
5. Writes a tabbed, interactive `dashboard.html` file and emails an HTML digest to the configured Gmail account.
6. Saves discovered URLs in `seen_events.json` to avoid repeating previously processed links.

The digest groups selected items into five categories: **Papers**, **Conferences**, **Fellowships**, **XR & Tech**, and **Psychology**. Event items may include a deadline and days remaining when the model can identify them.

## Who this is for

- Researchers tracking HCI, UX, XR, psychology, or adjacent work.
- Students looking for relevant calls for papers, grants, fellowships, and doctoral opportunities.
- UX and XR practitioners interested in research and technology developments.

## Requirements

- Python **3.10 or later**
- An [OpenAI API key](https://platform.openai.com/api-keys)
- A Gmail account with **2-Step Verification** enabled and a Gmail **App Password**
- Internet access to reach the listed content sources and Gmail SMTP

## Setup

### 1. Get the project

```bash
git clone https://github.com/Karthickbalakrishnan/ai-research-radar.git
cd ai-research-radar
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
```

Activate it:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install openai requests beautifulsoup4 python-dotenv
```

### 4. Configure credentials

Create a file named `.env` in the project directory (the same directory as `focused_radar.py`):

```dotenv
OPENAI_API_KEY=your_openai_api_key
GMAIL_USER=your.email@gmail.com
GMAIL_APP_PASSWORD=your_16_character_app_password
```

The OpenAI Python client reads `OPENAI_API_KEY` from the environment. The script loads `.env` automatically, and `.env` is excluded from Git by `.gitignore`.

To create a Gmail App Password, enable 2-Step Verification on your Google Account, then create an App Password in your account's security settings. Use the generated app password here—not your regular Gmail password. Google may restrict App Passwords for some account types or security configurations.

**Keep credentials private.** Do not commit `.env`, paste keys into source code, or share generated dashboard/email content if it contains information you consider private.

## Run the radar

With the virtual environment active and `.env` configured, run:

```bash
python focused_radar.py
```

The script prints progress as it fetches sources and processes results. If there are no new candidates, or no candidates pass the relevance filter, it exits without sending an email. On a successful run, it creates or replaces these files in the project directory:

- `dashboard.html` — open this file in a browser to view and switch between category tabs.
- `seen_events.json` — the URL history used for deduplication.

Both files are generated locally and are ignored by Git.

## Schedule daily runs

The script does **not** create its own schedule. To receive a recurring digest, schedule `focused_radar.py` with your operating system's task scheduler (for example, `cron` on macOS/Linux or Task Scheduler on Windows). Set the desired time zone and ensure the scheduler uses the project's Python environment and working directory.

Example `cron` entry for 9:00 AM every day (edit the paths for your machine):

```cron
0 9 * * * cd /path/to/ai-research-radar && /path/to/ai-research-radar/.venv/bin/python focused_radar.py
```

The “9:00 AM” text in the email subject/header is a label; actual delivery time is determined by when you run or schedule the script.

## Sources and scope

| Source | What the script looks for |
| --- | --- |
| arXiv (`cs.HC`) | A recent selection of papers matching topics such as virtual reality, adaptive systems, cognitive load, visual guidance, and user experience |
| WikiCFP | Conference and workshop listings returned for HCI, UX, virtual reality, and psychology searches |
| Google News RSS | Fellowship/dissertation opportunities and selected XR technology updates |

Source availability, page layout, search results, and deadlines can change. A source may be skipped if a request fails; check the terminal output and verify important deadlines and details at the original source before acting on them.

## Privacy and safe use

- The script sends collected titles, abstracts, and news/event details to OpenAI for filtering and summarization. Review the relevant provider terms and your organization's data policies before use.
- It connects to Gmail SMTP to send the digest to the address in `GMAIL_USER`.
- The dashboard is generated from external source content and model output. Keep it local; do not publish or host it publicly without reviewing and safely escaping its contents.
- Treat summaries and deadline estimates as a starting point, not authoritative information. Follow the original source link to confirm details.

## Project files

```text
.
├── focused_radar.py   # Fetch, filter, render, email, and deduplicate the digest
├── requirements.txt   # Dependency manifest (currently empty; install packages as shown above)
├── README.md
└── .gitignore
```

## Troubleshooting

- **OpenAI authentication error:** Check that `OPENAI_API_KEY` is present in `.env`, correctly spelled, and active.
- **Gmail authentication error:** Verify `GMAIL_USER`, use an App Password rather than your account password, and confirm the account permits SMTP access.
- **A source is skipped:** The script reports fetch failures in the terminal. Try again later; upstream services may be unavailable or may change their response format.
- **No email arrives:** Check the terminal output. The script intentionally skips email when there are no new candidates or nothing passes the relevance filter; also check the recipient account's spam folder.
- **An opportunity appears missing or outdated:** Check the original source directly. Search coverage and deadline interpretation depend on external data and model output.

## Contributing

Issues and pull requests are welcome. When reporting a problem, include your Python version, operating system, and the relevant error output, but **never include API keys, App Passwords, or other credentials**.

## License

No license is currently specified in this repository. Unless the project owner adds one, assume that reuse, modification, and redistribution are not granted by default.
