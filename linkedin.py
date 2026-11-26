"""
Post text to Sunny Choby's LinkedIn profile with the LinkedIn Posts API.

Needs in .env:
  LINKEDIN_ACCESS_TOKEN   token with scopes: openid profile w_member_social
Optional:
  LINKEDIN_PERSON_URN     urn:li:person:xxxx  (looked up automatically if missing)
  LINKEDIN_VERSION        YYYYMM API version (defaults to a recent month)
"""

import os
import re
from datetime import date

import requests

API = "https://api.linkedin.com"


class LinkedInError(Exception):
    pass


class LinkedInAuthError(LinkedInError):
    """Token missing, expired or without the right permissions."""


def _token() -> str:
    token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "").strip()
    if not token:
        raise LinkedInAuthError("LINKEDIN_ACCESS_TOKEN is missing in .env")
    return token


def _api_version() -> str:
    v = os.environ.get("LINKEDIN_VERSION", "").strip()
    if v:
        return v
    # LinkedIn versions are monthly (YYYYMM) and stay valid for about a year.
    # Use two months back so the version is always already released.
    today = date.today()
    y, m = today.year, today.month - 2
    if m <= 0:
        y, m = y - 1, m + 12
    return f"{y}{m:02d}"


def person_urn() -> str:
    urn = os.environ.get("LINKEDIN_PERSON_URN", "").strip()
    if urn:
        return urn
    r = requests.get(f"{API}/v2/userinfo",
                     headers={"Authorization": f"Bearer {_token()}"}, timeout=30)
    if r.status_code in (401, 403):
        raise LinkedInAuthError(f"LinkedIn token rejected ({r.status_code}). It may have expired (60 days).")
    if not r.ok:
        raise LinkedInError(f"LinkedIn userinfo failed: {r.status_code} {r.text[:300]}")
    return f"urn:li:person:{r.json()['sub']}"


# LinkedIn "little text" format: these characters must be escaped in commentary.
_RESERVED = re.compile(r"([\\|{}@\[\]()<>#*_~])")
_HASHTAG = re.compile(r"(?<![\w#])#(\w+)")


def _escape(text: str) -> str:
    return _RESERVED.sub(r"\\\1", text)


def to_little_text(text: str) -> str:
    """Escape reserved characters and turn #Words into real LinkedIn hashtags."""
    out, last = [], 0
    for m in _HASHTAG.finditer(text):
        out.append(_escape(text[last:m.start()]))
        out.append("{hashtag|\\#|" + _escape(m.group(1)) + "}")
        last = m.end()
    out.append(_escape(text[last:]))
    return "".join(out)


def post_text(text: str) -> str:
    """Publish a text post. Returns the public URL of the post."""
    body = {
        "author": person_urn(),
        "commentary": to_little_text(text),
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    r = requests.post(
        f"{API}/rest/posts",
        json=body,
        headers={
            "Authorization": f"Bearer {_token()}",
            "LinkedIn-Version": _api_version(),
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    if r.status_code in (401, 403):
        raise LinkedInAuthError(f"LinkedIn refused the post ({r.status_code}): {r.text[:300]}")
    if r.status_code != 201:
        raise LinkedInError(f"LinkedIn post failed: {r.status_code} {r.text[:300]}")
    post_id = r.headers.get("x-restli-id", "")
    return f"https://www.linkedin.com/feed/update/{post_id}/" if post_id else "https://www.linkedin.com/in/me/recent-activity/all/"
