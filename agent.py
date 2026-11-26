"""
Sunny Choby LinkedIn Agent  (runs on your Claude subscription, no API key)
-------------------------------------------------------------------------
Every run:
  1. Asks Claude Code (`claude -p`, using your logged-in Claude subscription) to
     research the top 2 export-related LinkedIn posts right now with web search.
  2. Repackages the ideas (never copies) in Sunny Choby's style into a draft.
       - 9 AM run  -> Problem post
       - 6 PM run  -> Solution post
  3. Sends the draft to Telegram for approval (reply YES to approve).

Posting to LinkedIn after YES is the next step (Step 3); this file only drafts + sends.

Needs:
  - Claude Code installed and logged in with your Claude subscription (`claude` then /login)
  - A .env file next to this script with TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID

Run:
  python3 agent.py --slot problem --dry-run     # prints the draft, no Telegram
  python3 agent.py                              # slot picked from the time of day
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
IST = timezone(timedelta(hours=5, minutes=30))
CLAUDE_TIMEOUT_SECONDS = 15 * 60

# ---------------------------------------------------------------------------
# Who Sunny is. Edit this block to change the voice or the offer.
# ---------------------------------------------------------------------------
PROFILE = {
    "name": "Sunny Choby",
    "linkedin": "https://www.linkedin.com/in/sunny-choby-184555452",
    "business": "Export Consultancy: helping new exporters get their FIRST export order",
    "program": (
        "6-Month Hand-Hold Program: 2 Months Live Training + 4 Months Team Support. "
        "Only Live Workshops. No Recorded Videos."
    ),
}

STYLE = """
Sunny Choby's writing style on LinkedIn:
- Talks like a mentor sitting across the table from a new exporter: direct, warm, practical.
- Simple English with light Hinglish words where natural (e.g. "yaar", "seedhi baat", "pehla order").
- Short lines. One idea per line. Lots of white space. No long paragraphs.
- Opens with a sharp hook line that stops the scroll.
- Uses 1 real-feeling example or number, never fake case studies or fake client names.
- 3-6 relevant hashtags at the end (#Export #ExportBusiness #FirstExportOrder etc.).
- Length: 120-220 words.
- Ends with a clear call to action, e.g. "Comment EXPORT" or "DM me 'FIRST ORDER'".
"""

HONESTY = """
Honesty rules (must follow):
- Never promise a guaranteed export order, guaranteed income or guaranteed results.
- No fake testimonials, fake numbers or invented client stories.
- Do not copy sentences or phrases from the source posts. Take only the core idea,
  then write it completely fresh in Sunny's own words and angle.
- Do not mention or tag the original authors.
"""

SLOT_BRIEF = {
    "problem": (
        "POST 1 (9 AM): PROBLEM post. Pick the strongest pain point / mistake new exporters face "
        "from the research. Make the reader feel 'yeh toh mere saath ho raha hai'. Agitate the problem, "
        "hint that there is a structured way out, and mention the 6-Month Hand-Hold program briefly "
        "near the end."
    ),
    "solution": (
        "POST 2 (6 PM): SOLUTION post. Give a clear, practical step-by-step way to solve a problem new "
        "exporters face (from the research). Give real value (3-5 steps). Then position the "
        "6-Month Hand-Hold program as the guided way to do it."
    ),
}

PROGRAM_LINES = [
    "6-Month Hand-Hold",
    "2 Months Live Training + 4 Months Team Support",
    "Only Live",
    "No Recorded",
]


def load_env_file(path: str) -> None:
    """Load KEY=VALUE lines from .env into os.environ (without overriding)."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def build_prompt(slot: str, today: str) -> str:
    return f"""Today is {today} (India).

You are the content agent for {PROFILE['name']} ({PROFILE['linkedin']}).
Business: {PROFILE['business']}.
Program: {PROFILE['program']}

STEP 1 - RESEARCH
Use web search to find the top 2 export-related LinkedIn posts that are getting strong
engagement recently (topics like starting an export business, first export order, finding
buyers, IEC, documentation, pricing, payments, export mistakes). Prefer posts from the
last 30 days and from linkedin.com. Pick the 2 best ones.

STEP 2 - REPACKAGE
{SLOT_BRIEF[slot]}

{STYLE}
{HONESTY}

The draft MUST include these exact program details (they can be on separate lines):
- 6-Month Hand-Hold
- 2 Months Live Training + 4 Months Team Support
- Only Live Workshops, No Recorded Videos

STEP 3 - OUTPUT
Do not create or edit any files. Reply with ONLY one JSON object, no other text, in this shape:
{{
  "sources": [
    {{"title": "short description of source post 1", "url": "https://..."}},
    {{"title": "short description of source post 2", "url": "https://..."}}
  ],
  "angle": "one line: the idea you took and how you changed it",
  "draft": "the full LinkedIn post text, ready to publish"
}}
"""


def find_claude() -> str:
    for path in (shutil.which("claude"), "/opt/homebrew/bin/claude",
                 os.path.expanduser("~/.local/bin/claude"), "/usr/local/bin/claude"):
        if path and os.path.exists(path):
            return path
    raise RuntimeError("Claude Code not found. Install it and log in with `claude` then /login.")


def research_and_draft(slot: str) -> dict:
    today = datetime.now(IST).strftime("%d %B %Y")
    cmd = [
        find_claude(), "-p", build_prompt(slot, today),
        "--output-format", "json",
        "--allowedTools", "WebSearch", "WebFetch",
        "--disallowedTools", "Bash", "Edit", "Write", "NotebookEdit",
        "--no-session-persistence",
    ]
    env = os.environ.copy()
    # Use the subscription login, never an API key, even if one is set in the shell.
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("CLAUDECODE", None)

    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=HERE,
                          timeout=CLAUDE_TIMEOUT_SECONDS)
    if proc.returncode != 0:
        raise RuntimeError(f"Claude Code failed (exit {proc.returncode}):\n{proc.stderr[-1500:] or proc.stdout[-1500:]}")

    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"Unexpected Claude Code output:\n{proc.stdout[-1500:]}")
    if result.get("is_error"):
        raise RuntimeError(f"Claude Code reported an error: {result.get('result', '')[:1500]}")
    return parse_json(result.get("result", ""))


def parse_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON found in Claude's reply:\n{text[:500]}")
    data = json.loads(text[start : end + 1])
    if not data.get("draft"):
        raise ValueError("Claude's reply has no 'draft'.")
    return data


def ensure_program_lines(draft: str) -> str:
    """Make sure every required program detail is in the draft."""
    missing = [line for line in PROGRAM_LINES if line.lower() not in draft.lower()]
    if not missing:
        return draft
    block = (
        "\n\n6-Month Hand-Hold Program:\n"
        "2 Months Live Training + 4 Months Team Support\n"
        "Only Live Workshops. No Recorded Videos."
    )
    return draft.rstrip() + block


def send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing. Add them to .env")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # Telegram limit is 4096 chars per message.
    for i in range(0, len(text), 4000):
        r = requests.post(
            url,
            json={"chat_id": chat_id, "text": text[i : i + 4000], "disable_web_page_preview": True},
            timeout=30,
        )
        r.raise_for_status()


def format_for_telegram(slot: str, data: dict) -> str:
    label = "POST 1 - 9 AM - PROBLEM" if slot == "problem" else "POST 2 - 6 PM - SOLUTION"
    sources = "\n".join(
        f"{i}. {s.get('title', '')}\n   {s.get('url', '')}"
        for i, s in enumerate(data.get("sources", []), 1)
    )
    return (
        f"📝 DRAFT READY: {label}\n"
        f"{datetime.now(IST).strftime('%d %b %Y, %I:%M %p IST')}\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"{data['draft']}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Idea taken from (not copied):\n{sources}\n\n"
        f"Angle: {data.get('angle', '')}\n\n"
        f"👉 Reply YES to approve this post."
    )


def pick_slot(cli_slot: str | None) -> str:
    slot = (cli_slot or os.environ.get("SLOT") or "").strip().lower()
    if slot in SLOT_BRIEF:
        return slot
    # Morning run = problem, evening run = solution.
    return "problem" if datetime.now(IST).hour < 14 else "solution"


def main() -> int:
    parser = argparse.ArgumentParser(description="Sunny Choby LinkedIn draft agent")
    parser.add_argument("--slot", choices=list(SLOT_BRIEF), help="problem (9 AM) or solution (6 PM)")
    parser.add_argument("--dry-run", action="store_true", help="print the draft, do not send to Telegram")
    args = parser.parse_args()

    load_env_file(os.path.join(HERE, ".env"))
    slot = pick_slot(args.slot)
    print(f"[{datetime.now(IST):%Y-%m-%d %H:%M}] Slot: {slot}", flush=True)

    data = research_and_draft(slot)
    data["draft"] = ensure_program_lines(data["draft"])
    message = format_for_telegram(slot, data)

    drafts_dir = os.path.join(HERE, "drafts")
    os.makedirs(drafts_dir, exist_ok=True)
    out = os.path.join(drafts_dir, f"{datetime.now(IST).strftime('%Y-%m-%d')}_{slot}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"slot": slot, **data}, f, ensure_ascii=False, indent=2)
    print(f"Saved {out}")

    if args.dry_run:
        print(message)
        return 0

    send_telegram(message)
    print("Draft sent to Telegram for approval.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
