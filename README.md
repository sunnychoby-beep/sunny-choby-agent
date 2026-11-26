# sunny-choby-agent

LinkedIn content agent for **Sunny Choby** (C-H-O-B-Y)
Profile: https://www.linkedin.com/in/sunny-choby-184555452

**Business:** Export Consultancy. Helping new exporters get their **first export order**.
**Program:** 6-Month Hand-Hold: 2 Months Live Training + 4 Months Team Support. Only Live Workshops, No Recorded Videos.

## Runs on your Claude subscription. No API key.

Drafts are written by **Claude Code** (`claude -p`) using your Claude subscription login.
There is no `ANTHROPIC_API_KEY`; the code removes it even if one is set in your shell.
Everything runs on **your Mac**.

## Daily flow

| Time (IST) | What happens |
|---|---|
| 8:30 AM | Claude Code finds the top 2 export posts, writes **2 drafts** (Problem + Solution) in Sunny's style, sends them to Telegram: *"Ye 2 draft ready hain, post kar dun? YES / NO"* |
| You reply | **YES** = approve both. **NO** = nothing posts today. |
| 9:00 AM | Post 1 (Problem) goes live on LinkedIn (or right after your YES, if later) |
| 6:00 PM | Post 2 (Solution) goes live on LinkedIn |

- **Nothing is ever posted without your YES.**
- Telegram tells you when each post is live, with the link.
- A YES only counts for that day's drafts. Replies from any other Telegram chat are ignored.

## Files

| File | Purpose |
|---|---|
| `agent.py` | `draft`: research + 2 drafts + Telegram question. `check`: read YES/NO, post on time |
| `linkedin.py` | Posts text to LinkedIn (Posts API) |
| `run.sh` | Runs the agent once (sets up Python on first run, writes `logs/`) |
| `schedule/install.sh` | Turns on the Mac schedule (8:30 AM draft, check every 5 min) |
| `schedule/uninstall.sh` | Turns it off |
| `.env.example` | Template for your private settings |

## Setup (one time)

### 1. Claude Code login
```bash
claude
```
Type `/login` and pick your Claude subscription account (not "API key").

### 2. Telegram bot
1. **@BotFather** → `/newbot` → copy the full token (`123456789:AA...`).
2. Open your bot, press **Start**, send `hi`.
3. Get your chat ID from `https://api.telegram.org/bot<TOKEN>/getUpdates` (`"chat":{"id": ...}`).

### 3. LinkedIn access token
1. Go to https://www.linkedin.com/developers/apps → **Create app**.
   LinkedIn requires a **LinkedIn Company Page** to link the app to.
2. In the app, **Products** tab → request **Share on LinkedIn** and **Sign In with LinkedIn using OpenID Connect**.
3. **Auth** tab → add redirect URL `https://www.linkedin.com/developers/tools/oauth/redirect`.
4. Open https://www.linkedin.com/developers/tools/oauth/token-generator → pick your app →
   tick `openid`, `profile`, `w_member_social` → **Request access token** → sign in → copy the token.
5. The token lasts **60 days**. When it expires, Telegram warns you; repeat step 4.

### 4. `.env`
Copy `.env.example` to `.env` and fill in:
```
TELEGRAM_BOT_TOKEN=123456789:AA...
TELEGRAM_CHAT_ID=987654321
LINKEDIN_ACCESS_TOKEN=AQV...
```
⚠️ This repo is **public**. `.env` is in `.gitignore`. Never commit it.

### 5. Test, then turn on the schedule
```bash
.venv/bin/python agent.py draft --dry-run   # prints 2 drafts, sends nothing
./schedule/install.sh                        # 8:30 AM draft + checks every 5 min
```

## Change the style, offer or times
- Voice and offer: `PROFILE`, `STYLE` in `agent.py`
- Post times: `POST_TIMES` in `agent.py`; draft time: `schedule/draft.plist`, then run `./schedule/install.sh` again

## Notes
- Each draft run uses your Claude subscription's usage limits (1 run a day with web search).
- The Mac must be on (asleep is OK, jobs run on wake; shut down is not).
- LinkedIn posts are found through public web search, not by scraping LinkedIn. Source links are sent to you on Telegram so you can check nothing was copied.
- Honesty rules are built in: no guaranteed orders, no fake testimonials, no copied lines.
