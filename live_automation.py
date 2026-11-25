import requests
from dotenv import load_dotenv
from openai import OpenAI

# 1. Load your API key
load_dotenv()
client = OpenAI()

print("Fetching real-time tech headlines from Hacker News...")

# 2. Fetch live top story IDs from the real-time Hacker News API
top_ids_url = "https://hacker-news.firebaseio.com/v0/topstories.json"
story_ids = requests.get(top_ids_url).json()[:5]  # Grab top 5 live stories

live_headlines = []
for story_id in story_ids:
    story_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
    story = requests.get(story_url).json()
    title = story.get("title", "No Title")
    score = story.get("score", 0)
    live_headlines.append(f"- {title} (Upvotes: {score})")

raw_live_data = "\n".join(live_headlines)
print("\n--- Raw Real-Time Data Fetched ---")
print(raw_live_data)

# 3. Pass the real-time data to OpenAI to analyze and summarize
print("\nSending live data to LLM for analysis...")
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {
            "role": "system",
            "content": "You are a sharp tech analyst. Summarize these live trending headlines into a crisp 3-bullet morning briefing and highlight the single biggest trend right now.",
        },
        {"role": "user", "content": raw_live_data},
    ],
)

# 4. Print the final AI-processed result
print("\n--- AI Briefing ---")
print(response.choices[0].message.content)