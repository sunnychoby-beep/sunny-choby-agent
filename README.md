# sunny-choby-agent

LinkedIn content agent for **Sunny Choby** (C-H-O-B-Y)
Profile: https://www.linkedin.com/in/sunny-choby-184555452

**Business:** Export Consultancy. Helping new exporters get their **first export order**.
**Program:** 6-Month Hand-Hold: 2 Months Live Training + 4 Months Team Support. Only Live Workshops, No Recorded Videos.

## Runs on your Claude subscription. No API key.

The agent uses **Claude Code** (`claude -p`) with your existing Claude subscription login.
There is no `ANTHROPIC_API_KEY` anywhere, and the code removes it even if one is set in your shell.
It runs on **your Mac** (or any computer or cloud machine where Claude Code is logged in).

## What it does

| Time (IST) | Post | Type |
|---|---|---|
| 9:00 AM | Post 1 | **Problem** post |
| 6:00 PM | Post 2 | **Solution** post |

Each run:
1. **Research:** Claude Code web search finds the top 2 export-related LinkedIn posts right now.
2. **Repackage:** takes only the core idea, never copies, and writes a fresh draft in Sunny Choby's style. The program details are always included.
3. **Approval:** sends the draft to Telegram with the source links. You reply **YES** to approve.

> Posting to LinkedIn after YES is Step 3 (not built yet).

## Files

| File | Purpose |
|---|---|
| `agent.py` | Research + draft through Claude Code, send to Telegram |
| `run.sh` | Runs the agent once (sets up Python on first run, writes `logs/`) |
| `schedule/install.sh` | Puts the 9 AM / 6 PM schedule on your Mac |
| `schedule/uninstall.sh` | Removes the schedule |
| `.env.example` | Template for your Telegram details |
| `requirements.txt` | `requests` |

## Setup (one time)

### 1. Claude Code login
Claude Code must be installed and logged in with your Claude subscription:
```bash
claude
```
Inside it, type `/login` and pick your Claude subscription account (not "API key").

### 2. Telegram bot
1. In Telegram, open **@BotFather** → `/newbot` → follow the steps → copy the **bot token**.
2. Open your new bot, press **Start**, send `hi`.
3. Open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` and copy the number after `"chat":{"id":`. That's your **chat ID**.

### 3. Create `.env`
Copy `.env.example` to `.env` in this folder and fill it in:
```
TELEGRAM_BOT_TOKEN=123456789:ABC...
TELEGRAM_CHAT_ID=987654321
```
⚠️ This repo is **public**. `.env` is in `.gitignore`. Never commit it.

### 4. Test
```bash
./run.sh --slot problem --dry-run
```
Check `logs/` for the draft. Without `--dry-run` it is also sent to Telegram.

### 5. Turn on the schedule
```bash
./schedule/install.sh
```
Runs every day at 9:00 AM and 6:00 PM (Mac time, must be IST).
If the Mac is asleep at that time, the run happens as soon as it wakes up.

## Change the style or offer
Edit `PROFILE`, `STYLE` and `SLOT_BRIEF` at the top of `agent.py`.

## Notes
- Each run uses your Claude subscription's usage limits (2 runs a day with web search).
- The Mac needs to be on (asleep is fine, shut down is not) for the schedule to run.
- LinkedIn posts are found through public web search, not by scraping LinkedIn.
- Honesty rules are built in: no guaranteed orders, no fake testimonials, no copied lines.
