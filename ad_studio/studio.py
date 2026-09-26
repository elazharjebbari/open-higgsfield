"""Job orchestration and the local consumption ledger.

The ledger (work/ledger.json) records every submission with its estimate so
you always know what you spent — the "consommation" view from the video.
"""

import json
import random
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from .client import TERMINAL, ApiError, estimate_usd, media_urls
from .models import build_payload, get_model

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"
OUTPUTS = ROOT / "outputs"
_lock = threading.Lock()


class Ledger:
    def __init__(self, path=WORK / "ledger.json"):
        self.path = Path(path)

    def load(self):
        try:
            return json.loads(self.path.read_text())
        except (FileNotFoundError, ValueError):
            return []

    def _save(self, jobs):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(jobs, indent=2, ensure_ascii=False))
        tmp.replace(self.path)

    def add(self, job):
        with _lock:
            jobs = self.load()
            jobs.append(job)
            self._save(jobs)

    def update(self, request_id, **fields):
        with _lock:
            jobs = self.load()
            for job in jobs:
                if job.get("request_id") == request_id:
                    job.update(fields)
            self._save(jobs)

    def get(self, request_id):
        return next((j for j in self.load() if j.get("request_id") == request_id), None)

    def consumption(self):
        jobs = self.load()
        billable = [j for j in jobs if j.get("status") not in ("failed", "nsfw", "canceled", "cancelled")]
        return {
            "jobs": len(jobs),
            "videos": sum(1 for j in jobs if j.get("status") == "completed"),
            "seconds": sum(j["payload"].get("duration", 0) for j in billable),
            "estimated_usd": round(sum(j.get("estimate_usd") or 0 for j in billable), 2),
        }


def prepare(model_key, prompt, **params):
    model = get_model(model_key)
    return model, build_payload(model, prompt, **params)


def estimate(client, model_key, prompt, **params):
    model, payload = prepare(model_key, prompt, **params)
    result = client.estimate(model.endpoint, payload)
    return {"payload": payload, "usd": estimate_usd(result), "raw": result}


def submit(client, ledger, model_key, prompt, label="", template="", **params):
    model, payload = prepare(model_key, prompt, **params)
    try:
        usd = estimate_usd(client.estimate(model.endpoint, payload))
    except ApiError:
        usd = None  # an estimate failure must not block a deliberate generation
    result = client.submit(model.endpoint, payload)
    request_id = result.get("request_id")
    if not request_id:
        raise ApiError(f"Réponse sans request_id : {json.dumps(result)[:300]}")
    job = {
        "request_id": request_id,
        "label": label,
        "template": template,
        "model": model.endpoint,
        "payload": payload,
        "estimate_usd": usd,
        "status": result.get("status", "queued"),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": [],
    }
    ledger.add(job)
    return job


def refresh(client, ledger, request_id, download=True):
    result = client.status(request_id)
    status = result.get("status", "unknown")
    fields = {"status": status}
    urls = media_urls(result) if status == "completed" else []
    if urls:
        fields["urls"] = urls
    if download and urls:
        job = ledger.get(request_id) or {}
        if not job.get("files"):
            ext = "." + (job.get("payload", {}).get("output_format") or "mp4")
            files = []
            for i, url in enumerate(urls, 1):
                dest = OUTPUTS / f"{request_id}-{i}{ext}"
                client.download(url, dest)
                files.append(str(dest.relative_to(ROOT)))
            fields["files"] = files
    ledger.update(request_id, **fields)
    return {**(ledger.get(request_id) or {}), "raw_status": result}


def wait(client, ledger, request_id, timeout=1200, on_tick=None):
    """Poll 2s → 10s with jitter. Timing out never cancels the remote job."""
    deadline = time.monotonic() + timeout
    delay = 2.0
    while True:
        job = refresh(client, ledger, request_id)
        if on_tick:
            on_tick(job)
        if job.get("status") in TERMINAL or time.monotonic() > deadline:
            return job
        time.sleep(delay + random.uniform(0, 1))
        delay = min(delay * 1.5, 10.0)
