"""
Sunny Choby LinkedIn Agent  (runs on GitHub Actions with your Claude subscription, no API key)
-----------------------------------------------------------------------------------------------
GitHub Actions runs `python agent.py auto` every 10 minutes. Your PC can be off.

  8:30 AM IST (first run after it)
      1. Claude Code (`claude -p`, your subscription via CLAUDE_CODE_OAUTH_TOKEN)
         researches the top 2 export-related LinkedIn posts with web search.
      2. Repackages the ideas (never copies) in Sunny Choby's style into 2 drafts:
         Post 1 = Problem (goes out 9 AM), Post 2 = Solution (goes out 6 PM).
      3. Sends both to Telegram: "Ye 2 draft ready hain, post kar dun? YES / NO"

  Every run
      - Reads your Telegram reply. YES = approve both, NO = skip today.
      - After YES: Post 1 goes to LinkedIn at 9 AM (or right away if later),
        Post 2 at 6 PM. Nothing is ever posted without your YES.

Other commands: `draft`, `check`, `token-test`, `should-draft`. Add --dry-run to
draft/check to print instead of sending / posting.

Settings come from environment variables (GitHub Secrets), or from a local .env
for manual testing: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, LINKEDIN_ACCESS_TOKEN,
CLAUDE_CODE_OAUTH_TOKEN.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

import linkedin

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "drafts")
STATE_FILE = os.path.join(DATA, "state.json")
OFFSET_FILE = os.path.join(DATA, "telegram_offset.txt")
ATTEMPT_FILE = os.path.join(DATA, "last_draft_attempt.txt")
IST = timezone(timedelta(hours=5, minutes=30))
CLAUDE_TIMEOUT_SECONDS = 15 * 60

# When each approved post goes live (IST, 24h clock).
POST_TIMES = {"problem": (9, 0), "solution": (18, 0)}
# Drafts are made by the first run at or after DRAFT_TIME, and not after DRAFT_LAST.
DRAFT_TIME, DRAFT_LAST = (8, 30), (18, 0)
LABELS = {"problem": "POST 1 - 9 AM - PROBLEM", "solution": "POST 2 - 6 PM - SOLUTION"}

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

PROGRAM_LINES = [
    "6-Month Hand-Hold",
    "2 Months Live Training + 4 Months Team Support",
    "Only Live",
    "No Recorded",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def now() -> datetime:
    return datetime.now(IST)


def log(msg: str) -> None:
    print(f"[{now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


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


def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict) -> None:
    os.makedirs(DATA, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
def _tg(method: str, **payload) -> dict:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token or not os.environ.get("TELEGRAM_CHAT_ID"):
        raise RuntimeError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing. Add them to .env")
    r = requests.post(f"https://api.telegram.org/bot{token}/{method}", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def send_telegram(text: str) -> None:
    # Telegram limit is 4096 chars per message.
    for i in range(0, len(text), 4000):
        _tg("sendMessage", chat_id=os.environ["TELEGRAM_CHAT_ID"],
            text=text[i : i + 4000], disable_web_page_preview=True)


def read_replies() -> list[str]:
    """New text messages from Sunny's chat since the last check."""
    offset = 0
    if os.path.exists(OFFSET_FILE):
        offset = int(open(OFFSET_FILE).read().strip() or 0)
    updates = _tg("getUpdates", offset=offset, timeout=0).get("result", [])
    chat_id = str(os.environ["TELEGRAM_CHAT_ID"])
    texts = []
    for u in updates:
        offset = max(offset, u["update_id"] + 1)
        msg = u.get("message") or {}
        # Only accept replies from Sunny's own chat.
        if str(msg.get("chat", {}).get("id")) == chat_id and msg.get("text"):
            texts.append(msg["text"])
    os.makedirs(DATA, exist_ok=True)
    with open(OFFSET_FILE, "w") as f:
        f.write(str(offset))
    return texts


# ---------------------------------------------------------------------------
# Drafting (Claude Code on the subscription)
# ---------------------------------------------------------------------------
def build_prompt(today: str) -> str:
    return f"""Today is {today} (India).

You are the content agent for {PROFILE['name']} ({PROFILE['linkedin']}).
Business: {PROFILE['business']}.
Program: {PROFILE['program']}

STEP 1 - RESEARCH
Use web search to find the top 2 export-related LinkedIn posts that are getting strong
engagement recently (topics like starting an export business, first export order, finding
buyers, IEC, documentation, pricing, payments, export mistakes). Prefer posts from the
last 30 days and from linkedin.com. Pick the 2 best ones.

STEP 2 - REPACKAGE INTO 2 DRAFTS
POST 1 (goes out at 9 AM): PROBLEM post. Pick the strongest pain point / mistake new exporters
face from the research. Make the reader feel 'yeh toh mere saath ho raha hai'. Agitate the
problem, hint that there is a structured way out, and mention the program briefly near the end.

POST 2 (goes out at 6 PM): SOLUTION post. Give a clear, practical step-by-step way (3-5 steps)
to solve a problem new exporters face (from the research). Give real value first, then
position the program as the guided way to do it.

The 2 posts must not repeat the same hook or the same example.

{STYLE}
{HONESTY}

Each draft MUST include these exact program details (they can be on separate lines):
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
  "problem": {{"angle": "one line: idea taken and how you changed it", "draft": "full post text"}},
  "solution": {{"angle": "one line: idea taken and how you changed it", "draft": "full post text"}}
}}
"""


def find_claude() -> str:
    for path in (shutil.which("claude"), "/opt/homebrew/bin/claude",
                 os.path.expanduser("~/.local/bin/claude"), "/usr/local/bin/claude"):
        if path and os.path.exists(path):
            return path
    raise RuntimeError("Claude Code not found. Install it and log in with `claude` then /login.")


def research_and_draft() -> dict:
    cmd = [
        find_claude(), "-p", build_prompt(now().strftime("%d %B %Y")),
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
        raise RuntimeError(f"Claude Code reported an error: {str(result.get('result', ''))[:1500]}")
    return parse_json(result.get("result", ""))


def parse_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON found in Claude's reply:\n{text[:500]}")
    data = json.loads(text[start : end + 1])
    for slot in ("problem", "solution"):
        if not data.get(slot, {}).get("draft"):
            raise ValueError(f"Claude's reply has no '{slot}' draft.")
    return data


def ensure_program_lines(draft: str) -> str:
    """Make sure every required program detail is in the draft."""
    missing = [line for line in PROGRAM_LINES if line.lower() not in draft.lower()]
    if not missing:
        return draft
    return draft.rstrip() + (
        "\n\n6-Month Hand-Hold Program:\n"
        "2 Months Live Training + 4 Months Team Support\n"
        "Only Live Workshops. No Recorded Videos."
    )


def format_draft(slot: str, post: dict) -> str:
    return (
        f"📝 {LABELS[slot]}\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"{post['draft']}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Angle: {post.get('angle', '')}"
    )


def format_question(data: dict) -> str:
    sources = "\n".join(
        f"{i}. {s.get('title', '')}\n   {s.get('url', '')}"
        for i, s in enumerate(data.get("sources", []), 1)
    )
    return (
        "✅ Ye 2 draft ready hain, post kar dun?\n\n"
        "Post 1 (Problem) → 9:00 AM\n"
        "Post 2 (Solution) → 6:00 PM\n\n"
        f"Idea yahan se liya (copy nahi kiya):\n{sources}\n\n"
        "👉 Reply YES ya NO"
    )


def cmd_draft(dry_run: bool) -> int:
    log("Drafting 2 posts with Claude Code...")
    data = research_and_draft()
    posts = {}
    for slot in ("problem", "solution"):
        draft = ensure_program_lines(data[slot]["draft"])
        posts[slot] = {"draft": draft, "angle": data[slot].get("angle", ""),
                       "status": "waiting", "url": None, "error": None}

    state = {"date": now().strftime("%Y-%m-%d"), "status": "pending",
             "created_at": now().isoformat(), "sources": data.get("sources", []), "posts": posts}

    if dry_run:
        for slot in posts:
            print(format_draft(slot, posts[slot]), "\n")
        print(format_question(state))
        return 0

    # Ignore any old replies so a stale YES can't approve today's drafts.
    read_replies()
    save_state(state)
    for slot in ("problem", "solution"):
        send_telegram(format_draft(slot, posts[slot]))
    send_telegram(format_question(state))
    log("2 drafts sent to Telegram. Waiting for YES / NO.")
    return 0


# ---------------------------------------------------------------------------
# Approval + posting
# ---------------------------------------------------------------------------
def is_due(slot: str) -> bool:
    h, m = POST_TIMES[slot]
    return now() >= now().replace(hour=h, minute=m, second=0, microsecond=0)


TEST_FILE = os.path.join(DATA, "token_test.json")
TEST_POST = "Testing my LinkedIn agent ✅ Please ignore this post."


def load_test() -> dict:
    try:
        with open(TEST_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_test(test: dict) -> None:
    os.makedirs(DATA, exist_ok=True)
    tmp = TEST_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(test, f, ensure_ascii=False, indent=2)
    os.replace(tmp, TEST_FILE)


def cmd_token_test() -> int:
    """Check the LinkedIn token without posting, then ask on Telegram before a test post."""
    read_replies()  # skip old replies so they don't approve the test
    urn = linkedin.person_urn()
    log(f"LinkedIn token OK: {urn}")
    save_test({"status": "pending", "asked_at": now().isoformat()})
    send_telegram("Token lag gaya, test karun?\n\n👉 Reply YES ya NO")
    return 0


def handle_test_reply(test: dict, word: str) -> None:
    if word in ("YES", "Y", "HAAN"):
        try:
            url = linkedin.post_text(TEST_POST)
            test.update(status="posted", url=url, posted_at=now().isoformat())
            send_telegram(f"✅ Test post LinkedIn pe live hai:\n{url}\n\nDekh lo, chaho to LinkedIn se delete kar dena.")
        except Exception as e:
            test.update(status="failed", error=str(e))
            send_telegram(f"⚠️ Test post nahi hua:\n{str(e)[:1000]}")
    else:
        test["status"] = "rejected"
        send_telegram("❌ Theek hai, test post nahi karunga.")
    save_test(test)


def handle_reply(state: dict, text: str) -> None:
    word = text.strip().upper().strip(".!")
    test = load_test()
    if test.get("status") == "pending" and word in ("YES", "Y", "HAAN", "NO", "N", "NAHI"):
        handle_test_reply(test, word)
        return
    today = now().strftime("%Y-%m-%d")
    pending = state.get("status") == "pending" and state.get("date") == today

    if word not in ("YES", "Y", "HAAN", "NO", "N", "NAHI"):
        send_telegram("Main sirf YES ya NO samajhta hoon. 🙂")
        return
    if not pending:
        send_telegram("Abhi koi draft approval ke liye pending nahi hai.")
        return

    if word in ("YES", "Y", "HAAN"):
        state["status"] = "approved"
        state["approved_at"] = now().isoformat()
        p1 = "abhi jaa raha hai" if is_due("problem") else "9:00 AM pe jaayega"
        p2 = "abhi jaa raha hai" if is_due("solution") else "6:00 PM pe jaayega"
        send_telegram(f"👍 Approved!\nPost 1 (Problem) {p1}.\nPost 2 (Solution) {p2}.")
    else:
        state["status"] = "rejected"
        send_telegram("❌ Theek hai, aaj ke dono drafts post nahi honge.")
    save_state(state)


def post_due(state: dict, dry_run: bool) -> None:
    if state.get("status") != "approved" or state.get("date") != now().strftime("%Y-%m-%d"):
        return
    for slot in ("problem", "solution"):
        post = state["posts"][slot]
        if post["status"] != "waiting" or not is_due(slot):
            continue
        label = "Post 1 (Problem)" if slot == "problem" else "Post 2 (Solution)"
        if dry_run:
            log(f"[dry-run] Would post {label} to LinkedIn now.")
            continue
        try:
            post["url"] = linkedin.post_text(post["draft"])
            post["status"] = "posted"
            post["posted_at"] = now().isoformat()
            send_telegram(f"🚀 {label} LinkedIn pe live hai:\n{post['url']}")
            log(f"Posted {slot}: {post['url']}")
        except linkedin.LinkedInAuthError as e:
            post["status"], post["error"] = "failed", str(e)
            send_telegram(f"⚠️ {label} post nahi hua. LinkedIn token missing ya expire ho gaya.\n"
                          f"Naya token .env mein daalo.\n\n{e}")
            log(f"LinkedIn auth error: {e}")
        except Exception as e:  # network / API errors
            post["status"], post["error"] = "failed", str(e)
            send_telegram(f"⚠️ {label} post nahi hua:\n{e}")
            log(f"LinkedIn error: {e}")
        save_state(state)


def cmd_check(dry_run: bool) -> int:
    state = load_state()
    for text in read_replies():
        log(f"Reply: {text!r}")
        handle_reply(state, text)
    post_due(state, dry_run)
    return 0


def should_draft() -> bool:
    """True when today's drafts have not been made or tried yet and it is drafting time."""
    t, today = now(), now().strftime("%Y-%m-%d")
    start = t.replace(hour=DRAFT_TIME[0], minute=DRAFT_TIME[1], second=0, microsecond=0)
    last = t.replace(hour=DRAFT_LAST[0], minute=DRAFT_LAST[1], second=0, microsecond=0)
    if not (start <= t < last) or load_state().get("date") == today:
        return False
    try:
        with open(ATTEMPT_FILE) as f:
            return f.read().strip() != today
    except FileNotFoundError:
        return True


WATCH_SECONDS = 50 * 60   # one GitHub run watches this long, then starts the next run
POLL_SECONDS = 30


def day_active() -> bool:
    """True while today's drafts still need a reply or an approved post is still waiting."""
    state, today = load_state(), now().strftime("%Y-%m-%d")
    if state.get("date") != today:
        return False
    if state.get("status") == "pending":
        return True
    return state.get("status") == "approved" and any(
        p.get("status") == "waiting" for p in state.get("posts", {}).values())


def cmd_watch() -> int:
    """Check Telegram every 30 s while the day is active. Prints active=true/false at the end."""
    start = time.time()
    while True:
        cmd_check(False)
        if not day_active() or time.time() - start > WATCH_SECONDS:
            break
        time.sleep(POLL_SECONDS)
    active = day_active()
    log(f"Watch finished. Still active: {active}")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"active={'true' if active else 'false'}\n")
    return 0


def cmd_auto() -> int:
    if should_draft():
        os.makedirs(DATA, exist_ok=True)
        with open(ATTEMPT_FILE, "w") as f:  # one try a day, so a failure can't loop
            f.write(now().strftime("%Y-%m-%d"))
        try:
            cmd_draft(False)
        except Exception as e:
            log(f"ERROR while drafting: {e}")
            try:
                send_telegram(f"⚠️ Aaj ke drafts nahi ban paaye:\n{str(e)[:1000]}")
            except Exception:
                pass
    return cmd_watch()


def main() -> int:
    parser = argparse.ArgumentParser(description="Sunny Choby LinkedIn agent")
    parser.add_argument("command", nargs="?", default="auto", choices=["auto", "draft", "check", "watch", "token-test", "should-draft"])
    parser.add_argument("--dry-run", action="store_true", help="print instead of sending / posting")
    args = parser.parse_args()

    load_env_file(os.path.join(HERE, ".env"))
    try:
        if args.command == "should-draft":
            print("true" if should_draft() else "false")
            return 0
        if args.command == "watch":
            return cmd_watch()
        if args.command == "auto":
            return cmd_auto()
        if args.command == "token-test":
            return cmd_token_test()
        return cmd_draft(args.dry_run) if args.command == "draft" else cmd_check(args.dry_run)
    except Exception as e:
        log(f"ERROR: {e}")
        if args.command == "draft" and not args.dry_run:
            try:
                send_telegram(f"⚠️ Aaj ke drafts nahi ban paaye:\n{str(e)[:1000]}")
            except Exception:
                pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
