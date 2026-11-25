import os
from dotenv import load_dotenv
from openai import OpenAI

# 1. Load your secret API key from the .env file
load_dotenv()
client = OpenAI()

# 2. Read the messy input file
with open("notes.txt", "r") as file:
    messy_notes = file.read()

print("Reading notes and sending to AI...")

# 3. Send the text to OpenAI with clear instructions
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {
            "role": "system",
            "content": "You are a helpful assistant. Extract all action items from the text as a clean bulleted list with Owner and Deadline (if mentioned).",
        },
        {"role": "user", "content": messy_notes},
    ],
)

# 4. Get the AI's reply and save it automatically to a new file
action_items = response.choices[0].message.content

with open("action_items.md", "w") as output_file:
    output_file.write("# Extracted Action Items\n\n" + action_items)

print("Done! Check your folder for 'action_items.md'.")