# sunny-choby-agent

LinkedIn content agent for **Sunny Choby** (C-H-O-B-Y)
Profile: https://www.linkedin.com/in/sunny-choby-184555452

**Business:** Export Consultancy. Helping new exporters get their **first export order**.
**Program:** 6-Month Hand-Hold: 2 Months Live Training + 4 Months Team Support. Only Live Workshops, No Recorded Videos.

## What it does

Every day, 2 runs (GitHub Actions):

| Time (IST) | Post | Type |
|---|---|---|
| 9:00 AM | Post 1 | **Problem** post |
| 6:00 PM | Post 2 | **Solution** post |

Each run:
1. **Research:** uses Claude web search to find the top 2 export-related LinkedIn posts right now.
2. **Repackage:** takes only the core idea, never copies, and writes a fresh draft in Sunny Choby's style. The program details are always included.
3. **Approval:** sends the draft to Telegram with the source links. You reply **YES** to approve.

> Posting to LinkedIn after YES is Step 3 (not built yet). Right now the agent drafts and sends to Telegram.

## Files

| File | Purpose |
|---|---|
| `agent.py` | Research, draft, send to Telegram |
| `.github/workflows/linkedin.yml` | Cron: 9 AM and 6 PM IST, plus a manual run button |
| `requirements.txt` | `requests`, `anthropic` |

## Setup (one time)

### 1. Claude API key
- Go to https://console.anthropic.com → **API Keys** → create a key.

### 2. Telegram bot
1. In Telegram, open **@BotFather** → send `/newbot` → follow steps → copy the **bot token**.
2. Open your new bot and send it any message (e.g. `hi`).
3. Open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser and copy the number at `"chat":{"id": ...}`. That's your **chat ID**.

### 3. Add GitHub Secrets
Repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**:

| Name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | your Claude API key |
| `TELEGRAM_BOT_TOKEN` | bot token from BotFather |
| `TELEGRAM_CHAT_ID` | your chat ID |

⚠️ This repo is **public**. Never put keys or tokens inside any file. Only use GitHub Secrets.

### 4. Test it
Repo → **Actions** → **LinkedIn Draft Agent** → **Run workflow** → choose `problem` or `solution`.
A draft should arrive on Telegram in 1-3 minutes.

## Run on your computer (optional)

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...
python agent.py --slot problem --dry-run   # prints the draft, sends nothing
```

## Change the style or offer

Edit `PROFILE`, `STYLE` and `SLOT_BRIEF` at the top of `agent.py`.

## Notes
- GitHub's scheduled runs can start 5-20 minutes late at busy times.
- LinkedIn posts are found through public web search, not by scraping LinkedIn.
- Honesty rules are built in: no guaranteed orders, no fake testimonials, no copied lines.
