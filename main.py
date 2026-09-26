"""Seedance 2.5 text-to-video example using the official Higgsfield SDK.

Credentials: HF_KEY="key-id:key-secret" in .env.local (git-ignored) or in the
process environment. The value is never printed.

    .venv/bin/python main.py
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

import higgsfield_client

MODEL = "bytedance/seedance-2.5/text-to-video"
ARGUMENTS = {
    "prompt": "A cinematic scene at sunset",
    "duration": 5,
    "resolution": "720p",
    "aspect_ratio": "16:9",
}


def video_url(result):
    video = result.get("video") or result.get("videos")
    items = video if isinstance(video, list) else [video]
    for item in items:
        url = item.get("url") if isinstance(item, dict) else item
        if isinstance(url, str) and url.startswith("https://"):
            return url
    return None


def main():
    # An existing environment variable (e.g. a cloud secret) wins over the file.
    load_dotenv(Path(__file__).with_name(".env.local"), override=False)

    try:
        result = higgsfield_client.subscribe(
            MODEL,
            arguments=ARGUMENTS,
            on_enqueue=lambda request_id: print(f"Submitted request {request_id}", flush=True),
        )
    except higgsfield_client.CredentialsMissedError:
        print("Missing credentials: set HF_KEY=key-id:key-secret in .env.local", file=sys.stderr)
        return 2
    except higgsfield_client.HiggsfieldClientError as exc:
        print(f"Higgsfield API error: {exc}", file=sys.stderr)
        return 1

    # subscribe() returns the final payload for every terminal state, not only success.
    status = result.get("status")
    if status != "completed":
        reason = {"nsfw": "rejected by moderation", "failed": "generation failed",
                  "canceled": "request was canceled"}.get(status, f"unexpected status {status!r}")
        print(f"Request {result.get('request_id', '?')} did not succeed: {reason}", file=sys.stderr)
        return 1

    url = video_url(result)
    if not url:
        print(f"Completed but no video URL in the response (keys: {sorted(result)})", file=sys.stderr)
        return 1
    print(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
