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
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

import linkedin
from card import make_card

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
LABELS = {"problem": "POST 1 - 9 AM - PHOTO POST (PROBLEM)",
          "solution": "POST 2 - 6 PM - ARTICLE (SOLUTION)"}
SHORT = {"problem": "Post 1 (Photo post)", "solution": "Post 2 (Article)"}
MAX_CHARS = 2900  # LinkedIn allows 3000 characters per post

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
Sunny Choby's writing style on LinkedIn (value first, like a practical export teacher):
- LANGUAGE: simple, clear English only. No Hindi or Hinglish words at all. Short, everyday
  words a new exporter anywhere can follow.
- Teach ONE concrete export topic per post: real terms (Incoterms, THC, BAF, CHA, CFS,
  Shipping Bill, LUT, LC, HS code...), real steps, real costs. Specific beats general.
- Structure that works:
    1. Hook line with a number or a surprise ("Your $500 freight became $850. Here is why.")
    2. The breakdown: a short list, steps, or a cost split (one item per line).
    3. One practical rule the reader can use today ("Always ask for an ALL-IN quote").
    4. A light ending: "Save this for your next shipment" / "Share with your team", or one
       honest question that invites comments ("Which of these surprised you?").
- Short lines, lots of white space. A few emojis as bullets are fine, never more than 6.
- Numbers must be realistic and labelled as examples when they are examples.
  Never invent clients, case studies or results.
- 3-6 relevant hashtags at the end.
- Never promise a free PDF, list or file in return for a comment (we do not have one ready).
"""

HONESTY = """
Honesty rules (must follow):
- Never promise a guaranteed export order, guaranteed income or guaranteed results.
- No fake testimonials, fake numbers or invented client stories.
- Do not copy sentences or phrases from the source posts. Take only the core idea,
  then write it completely fresh in Sunny's own words and angle.
- Do not mention or tag the original authors.
"""

PITCH_WEEKDAY = 5  # Saturday: the only day a post mentions the paid program
TOPICS_FILE = os.path.join(DATA, "topics.json")
TOPIC_MEMORY_DAYS = 30

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


def send_photo(path: str, caption: str = "") -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    with open(path, "rb") as f:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendPhoto",
                          data={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "caption": caption[:1000]},
                          files={"photo": f}, timeout=120)
    r.raise_for_status()


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
def is_pitch_day() -> bool:
    return now().weekday() == PITCH_WEEKDAY


def recent_topics() -> list[str]:
    try:
        with open(TOPICS_FILE) as f:
            items = json.load(f)
    except (OSError, ValueError):
        return []
    cutoff = (now() - timedelta(days=TOPIC_MEMORY_DAYS)).strftime("%Y-%m-%d")
    return [t["topic"] for t in items if t.get("date", "") >= cutoff]


def remember_topics(data: dict) -> None:
    try:
        with open(TOPICS_FILE) as f:
            items = json.load(f)
    except (OSError, ValueError):
        items = []
    today = now().strftime("%Y-%m-%d")
    for slot in ("problem", "solution"):
        card = data[slot].get("card") or {}
        items.append({"date": today, "topic": card.get("headline") or data[slot].get("angle", "")})
    cutoff = (now() - timedelta(days=TOPIC_MEMORY_DAYS)).strftime("%Y-%m-%d")
    with open(TOPICS_FILE, "w") as f:
        json.dump([t for t in items if t.get("date", "") >= cutoff], f, indent=1)


def program_rule(pitch: bool) -> str:
    if pitch:
        return """TODAY IS PROGRAM DAY (once a week). POST 2 (the article) ends with a short, honest
section about the program, after the full value. It must include these exact details:
- 6-Month Hand-Hold
- 2 Months Live Training + 4 Months Team Support
- Only Live Workshops, No Recorded Videos
End POST 2 with a soft invitation, e.g. "If you want to be guided step by step, DM me 'HAND-HOLD'."
POST 1 stays pure value with no program mention."""
    return """NO SELLING TODAY. Do not mention the program, workshops, coaching, DMs for services or
any paid offer in either post. Pure value. The goal is trust: the reader should feel they
learned something real for free."""


def build_prompt(today: str, pitch: bool = False, avoid: list[str] | None = None) -> str:
    avoid_text = "\n".join(f"- {t}" for t in (avoid or [])) or "- (none yet)"
    return f"""Today is {today} (India).

You are the content agent for {PROFILE['name']} ({PROFILE['linkedin']}).
Business: {PROFILE['business']}.
Program (only for the weekly program day): {PROFILE['program']}

STEP 1 - RESEARCH
Use web search to find the top 2 export-related LinkedIn posts (text, image, infographic or
carousel posts) that are getting strong engagement recently (topics like starting an export business, first export order, finding
buyers, IEC, documentation, pricing, payments, export mistakes). Prefer posts from the
last 30 days and from linkedin.com. Pick the 2 best ones.

STEP 2 - REPACKAGE INTO 2 DRAFTS (each one goes out with an image card)
POST 1 (goes out at 9 AM): PHOTO POST about a PROBLEM, mistake or hidden cost new exporters
face. Hook with a number or surprise, show the breakdown, give the fix in one line.
The infographic carries most of the detail, so the text stays short: 80-180 words.

POST 2 (goes out at 6 PM): ARTICLE-STYLE long post that SOLVES something step by step
(a process, a checklist, how to compare options). First line is a clear title. Short intro,
then 5-7 numbered points with 1-2 lines each, a "Golden rule" line, and a short ending.
Length: 1,500-2,600 characters in total (hard limit: LinkedIn allows 3,000).

The two posts must be about DIFFERENT topics and must not repeat a recent topic:
{avoid_text}

{program_rule(pitch)}

IMAGE CARD for each post: a data-dense export INFOGRAPHIC that teaches on its own, even
without the text (we design it ourselves; never copy anyone's image). Choose the template
that fits the content best:
- "grid": 3-6 numbered boxes (mistakes, tips, comparisons). Each item: "title" (2-5 words),
  "text" (max 14 words), "note" (max 6 words: the consequence or the fix).
- "checklist": 6-12 ticked items (documents, steps to check). Each item: "title" (1-4
  words), "text" (max 7 words).
- "breakdown": 3-8 cost or share items shown as bars. Each item: "title" (1-3 words),
  "text" (max 4 words), "amount" (a plain number used for the bar), "value" (display, e.g. "$80").
  Add "total" (e.g. "Total: $850 (+70%)").
Also give: "series" (e.g. "Export Costing Series", 2-4 words), "headline" (max 9 words, with
a number or a surprise), "highlight" (1-2 words from the headline shown in orange),
"subtitle" (max 10 words), "takeaway" (max 18 words, the one rule to remember) and "cta"
(max 4 words, e.g. "Save this post").

NAME: the name is always spelled exactly "Sunny Choby" (C-H-O-B-Y). Never "Chaubey",
"Choubey", "Chobey" or any other spelling.

The 2 posts must not repeat the same hook or the same example.

{STYLE}
{HONESTY}

Write both drafts entirely in simple English.

STEP 3 - OUTPUT
Do not create or edit any files. Reply with ONLY one JSON object, no other text, in this shape:
{{
  "sources": [
    {{"title": "short description of source post 1", "url": "https://..."}},
    {{"title": "short description of source post 2", "url": "https://..."}}
  ],
  "problem": {{"angle": "one line: idea taken and how you changed it", "draft": "full post text",
              "card": {{"template": "grid|checklist|breakdown", "series": "...", "headline": "...",
                        "highlight": "...", "subtitle": "...", "items": [{{"title": "...", "text": "...", "note": "..."}}],
                        "takeaway": "...", "cta": "..."}}}},
  "solution": {{"angle": "one line: idea taken and how you changed it", "draft": "full article text",
               "card": {{ ...same shape as above... }}}}
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
        find_claude(), "-p", build_prompt(now().strftime("%d %B %Y"), is_pitch_day(), recent_topics()),
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


_WRONG_NAME = re.compile(r"\b(Chaubey|Choubey|Chobey|Chaube|Choubay|Chaubay)\b", re.I)


def fix_name(text: str) -> str:
    """Sunny's surname is always spelled Choby."""
    return _WRONG_NAME.sub("Choby", text)


def fit_length(draft: str, pitch: bool = False) -> str:
    """Keep a post under LinkedIn's limit, cutting at a paragraph break if needed."""
    if len(draft) <= MAX_CHARS:
        return draft
    room = MAX_CHARS - (200 if pitch else 0)  # space for the program lines
    cut = draft[:room].rfind("\n\n")
    draft = draft[: cut if cut > 0 else room].rstrip()
    return ensure_program_lines(draft) if pitch else draft


def fix_card(card) -> dict:
    """Apply the name fix to every text field of an image card."""
    def walk(v):
        if isinstance(v, str):
            return fix_name(v)
        if isinstance(v, list):
            return [walk(x) for x in v]
        if isinstance(v, dict):
            return {k: walk(x) for k, x in v.items()}
        return v
    return walk(card if isinstance(card, dict) else {})


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
        "Post 1 (Photo post) → 9:00 AM\n"
        "Post 2 (Article) → 6:00 PM\n\n"
        f"Idea yahan se liya (copy nahi kiya):\n{sources}\n\n"
        "👉 Reply YES ya NO"
    )


def cmd_draft(dry_run: bool) -> int:
    log("Drafting 2 posts with Claude Code...")
    data = research_and_draft()
    pitch = is_pitch_day()
    posts = {}
    for slot in ("problem", "solution"):
        draft = fix_name(data[slot]["draft"])
        if pitch and slot == "solution":
            draft = ensure_program_lines(draft)
        draft = fit_length(draft, pitch and slot == "solution")
        card = fix_card(data[slot].get("card"))
        image = os.path.join(DATA, f"{now():%Y-%m-%d}_{slot}.png")
        make_card(card, image)
        posts[slot] = {"draft": draft, "angle": data[slot].get("angle", ""), "card": card,
                       "image": image, "status": "waiting", "url": None, "error": None}

    state = {"date": now().strftime("%Y-%m-%d"), "status": "pending",
             "created_at": now().isoformat(), "sources": data.get("sources", []), "posts": posts}

    if dry_run:
        print(f"Program day: {'YES' if pitch else 'no'} | avoiding {len(recent_topics())} recent topics\n")
        for slot in posts:
            print(format_draft(slot, posts[slot]), "\n")
        print(format_question(state))
        return 0

    # Ignore any old replies so a stale YES can't approve today's drafts.
    read_replies()
    save_state(state)
    remember_topics(data)
    for slot in ("problem", "solution"):
        send_photo(posts[slot]["image"], f"🖼 {SHORT[slot]} ki photo")
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


def cmd_image_check() -> int:
    """Upload a sample card to LinkedIn without posting it (checks image permission)."""
    path = make_card({"tag": "Test", "headline": "Image upload check", "points": ["Not posted"]},
                     os.path.join(DATA, "image_check.png"))
    urn = linkedin.upload_image(path, linkedin.person_urn())
    log(f"LinkedIn image upload OK (not posted): {urn.split(':')[0]}:li:image:…")
    return 0


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
        send_telegram(f"👍 Approved!\nPost 1 (Photo post) {p1}.\nPost 2 (Article) {p2}.")
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
        label = SHORT[slot]
        if dry_run:
            log(f"[dry-run] Would post {label} to LinkedIn now.")
            continue
        try:
            image = post.get("image")
            if image and os.path.exists(image):
                post["url"] = linkedin.post_with_image(post["draft"], image,
                                                       post.get("card", {}).get("headline", ""))
            else:
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
    errors = 0
    while True:
        try:
            cmd_check(False)
            errors = 0
        except Exception as e:  # a network blip must not stop the day
            errors += 1
            log(f"Check failed ({errors}), will retry: {e}")
            if errors == 10:
                try:
                    send_telegram(f"⚠️ Agent ko Telegram/LinkedIn se baar baar error aa raha hai:\n{str(e)[:500]}")
                except Exception:
                    pass
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
    parser.add_argument("command", nargs="?", default="auto", choices=["auto", "draft", "check", "watch", "token-test", "image-check", "should-draft"])
    parser.add_argument("--dry-run", action="store_true", help="print instead of sending / posting")
    args = parser.parse_args()

    load_env_file(os.path.join(HERE, ".env"))
    try:
        if args.command == "should-draft":
            print("true" if should_draft() else "false")
            return 0
        if args.command == "image-check":
            return cmd_image_check()
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
