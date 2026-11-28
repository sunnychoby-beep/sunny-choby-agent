# sunny-choby-agent

LinkedIn content agent for **Sunny Choby** (C-H-O-B-Y)
Profile: https://www.linkedin.com/in/sunny-choby-184555452

**Business:** Export Consultancy. Helping new exporters get their **first export order**.
**Program:** 6-Month Hand-Hold: 2 Months Live Training + 4 Months Team Support. Only Live Workshops, No Recorded Videos.

## Runs on GitHub Actions with your Claude subscription. No API key. PC can be off.

The agent runs on **GitHub Actions**, not on your PC. Your PC / laptop can be switched off.
Drafts are written by **Claude Code** (`claude -p`) using your **Claude subscription**
through a `CLAUDE_CODE_OAUTH_TOKEN` (made with `claude setup-token`). There is no `ANTHROPIC_API_KEY`.

## Daily flow

| Time (IST) | What happens |
|---|---|
| 8:30 AM | Claude Code finds the top 2 export posts (text or image), writes **2 drafts in simple English** with a **infographic card** each, sends them to Telegram: *"Ye 2 draft ready hain, post kar dun? YES / NO"* |
| You reply | **YES** = approve both. **NO** = nothing posts today. |
| 9:00 AM | Post 1: **photo post** (Problem) goes live on LinkedIn (or right after your YES, if later) |
| 6:00 PM | Post 2: **article-style long post** (Solution) with a cover card goes live on LinkedIn |

- **Nothing is ever posted without your YES.**
- Telegram tells you when each post is live, with the link.
- A YES only counts for that day's drafts. Replies from any other Telegram chat are ignored.
- GitHub's schedule is unreliable (runs can start late or be skipped), so once a day has
  started, the agent keeps itself running: it checks Telegram every 30 seconds until your
  posts are done, then stops. Backup runs at :07 and :37 each hour (8:37 AM - 6:07 PM IST)
  restart it if needed.

## Files

| File | Purpose |
|---|---|
| `.github/workflows/agent.yml` | GitHub Actions: 8:30 AM IST draft, then keeps checking Telegram until the day's posts are done |
| `agent.py` | `auto` (default): draft at 8:30, read YES/NO, post on time. Also `draft`, `check`, `token-test` |
| `linkedin.py` | Posts to LinkedIn (Posts API + image upload) |
| `card.py` | Makes the Sunny Choby infographic card (1080x1350): grid, checklist or cost breakdown |
| `.env.example` | Template for local testing only |

## Setup (one time)

### 1. GitHub Secrets
Repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | What |
|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | Run `claude setup-token` on any computer, log in with your Claude subscription, copy the token |
| `TELEGRAM_BOT_TOKEN` | From **@BotFather** (`123456789:AA...`) |
| `TELEGRAM_CHAT_ID` | Your chat ID (from `getUpdates` after sending your bot `hi`) |
| `LINKEDIN_ACCESS_TOKEN` | From the LinkedIn Token Generator (below) |

### 2. LinkedIn access token
1. https://www.linkedin.com/developers/apps → **Create app** (needs a LinkedIn Company Page).
2. **Products** tab → add **Share on LinkedIn** and **Sign In with LinkedIn using OpenID Connect**.
3. **Auth** tab → redirect URL `https://www.linkedin.com/developers/tools/oauth/redirect`.
4. https://www.linkedin.com/developers/tools/oauth/token-generator → pick your app →
   tick **all three**: `openid`, `profile`, `w_member_social` → **Request access token** → copy it.
5. The token lasts **60 days**. When it expires, Telegram warns you; make a new one and update the secret.

### 3. Test
Repo → **Actions → LinkedIn agent → Run workflow** → `token-test`.
Telegram asks *"Token lag gaya, test karun?"*; a test post goes out only after your YES.

## Content rules
- Simple English only on LinkedIn (Telegram messages to you stay in Hinglish).
- The name is always **Sunny Choby** (C-H-O-B-Y); other spellings are corrected automatically.
- Value first: one concrete export topic per post (hook with a number, breakdown, one practical rule, save/share ending).
- The paid program is mentioned **only on Saturday** (`PITCH_WEEKDAY` in `agent.py`), at the end of the article. Other days have no selling.
- Topics from the last 30 days are remembered (`drafts/topics.json`) so they are not repeated.
- Images are original infographics with 3 templates: `grid` (numbered boxes), `checklist` and `breakdown` (cost bars). Run `python card.py` to see samples.
- Put Sunny's photo at `assets/photo.jpg` to show it in the card footer (otherwise an "SC" badge is used). The repo is public, so the photo is public too.
- Only the idea of a popular post is used, never its text or image.
- LinkedIn's real "Write article" feature has no public API, so Post 2 is an article-style long post.

## Change the style, offer or times
- Voice and offer: `PROFILE`, `STYLE` in `agent.py`; card colours and footer: `card.py`
- Post times: `POST_TIMES` in `agent.py`; draft time: `DRAFT_TIME` in `agent.py`

## Notes
- Each draft run uses your Claude subscription's usage limits (1 run a day with web search).
- GitHub Actions is free for public repos. GitHub pauses scheduled workflows after 60 days
  with no repo activity; if that happens, open **Actions** and click **Enable workflow**.
- This repo is **public**, so Actions logs are public too. Logs never print tokens or drafts.
- LinkedIn posts are found through public web search, not by scraping LinkedIn. Source links are sent to you on Telegram so you can check nothing was copied.
- Honesty rules are built in: no guaranteed orders, no fake testimonials, no copied lines.
