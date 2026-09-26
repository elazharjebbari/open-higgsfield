"""Minimal Higgsfield REST client (stdlib only).

Auth, endpoints and job lifecycle follow docs.higgsfield.ai:
  POST /<model>                      -> {request_id, status_url, status}
  GET  /requests/<id>/status         -> {status, video: {url} | [...]}
  POST /estimate/<model>             -> {credits, usd}
  POST /files/generate-upload-url    -> {upload_url, public_url, upload_headers}

The API key never leaves this process: it is read from the environment and
is only sent to api.higgsfield.ai, never to storage or media hosts.
"""

import json
import mimetypes
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .models import ALLOWED_ENDPOINTS

BASE = os.environ.get("HF_API_BASE", "https://api.higgsfield.ai").rstrip("/")
USER_AGENT = "open-higgsfield-ad-studio/0.1"
TERMINAL = {"completed", "failed", "nsfw", "canceled", "cancelled"}
UPLOAD_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD = 64 * 1024 * 1024
MAX_DOWNLOAD = 512 * 1024 * 1024


class ApiError(RuntimeError):
    def __init__(self, message, code=0):
        super().__init__(message)
        self.code = code


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def load_credentials():
    """Return 'KEY_ID:KEY_SECRET' from HF_API_KEY_ID/HF_API_KEY_SECRET or HF_KEY."""
    key_id = os.environ.get("HF_API_KEY_ID", "").strip()
    secret = os.environ.get("HF_API_KEY_SECRET", "").strip()
    if not (key_id and secret):
        key_id, _, secret = os.environ.get("HF_KEY", "").strip().partition(":")
    if not key_id or not secret:
        raise ApiError("Clé API absente : définissez HF_API_KEY_ID et HF_API_KEY_SECRET (voir .env.example)")
    return f"{key_id}:{secret}"


def load_dotenv(path=".env"):
    """Load KEY=VALUE lines into os.environ without overriding existing vars."""
    env = Path(path)
    if not env.is_file():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def _check_public_https(url):
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise ApiError(f"URL refusée (https public requis) : {url}")
    return url


class HiggsfieldClient:
    def __init__(self, credentials=None, base=BASE, opener=None):
        self._auth = "Key " + (credentials or load_credentials())
        self.base = base
        self._open = (opener or build_opener(_NoRedirect())).open

    def _request(self, method, path, payload=None, timeout=60):
        url = f"{self.base}/{path.lstrip('/')}"
        data = None if payload is None else json.dumps(payload).encode()
        req = Request(url, data=data, method=method, headers={
            "Authorization": self._auth,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        })
        try:
            with self._open(req, timeout=timeout) as resp:
                return json.loads(resp.read() or b"{}")
        except HTTPError as exc:
            detail = exc.read(2000).decode("utf-8", "replace")
            raise ApiError(_explain(exc.code, detail), exc.code) from None
        except (URLError, TimeoutError, OSError) as exc:
            raise ApiError(f"Réseau : impossible de joindre {self.base} ({exc}). "
                           "En session cloud, autorisez api.higgsfield.ai dans la politique réseau.") from None

    @staticmethod
    def _endpoint(model_endpoint):
        if model_endpoint not in ALLOWED_ENDPOINTS:
            raise ApiError(f"Modèle interdit : {model_endpoint}. Ce studio n'utilise que Seedance 2.5.")
        return model_endpoint

    def estimate(self, model_endpoint, payload):
        return self._request("POST", f"estimate/{self._endpoint(model_endpoint)}", payload)

    def submit(self, model_endpoint, payload):
        """One paid submission. Never retried automatically (no idempotency key)."""
        return self._request("POST", self._endpoint(model_endpoint), payload)

    def status(self, request_id):
        if not request_id or "/" in request_id:
            raise ApiError("request_id invalide")
        return self._request("GET", f"requests/{request_id}/status")

    def upload(self, filename=None, data=None, content_type=None):
        """Upload a product image and return its public URL for image_url."""
        if filename:
            data = Path(filename).read_bytes()
            content_type = content_type or mimetypes.guess_type(str(filename))[0]
        if content_type not in UPLOAD_TYPES:
            raise ApiError("Image produit : JPEG, PNG ou WebP uniquement")
        if not data or len(data) > MAX_UPLOAD:
            raise ApiError("Image vide ou > 64 Mo")
        info = self._request("POST", "files/generate-upload-url", {"content_type": content_type})
        headers = dict(info.get("upload_headers") or {})
        if any(k.lower() in ("authorization", "cookie", "host") for k in headers):
            raise ApiError("En-têtes d'upload inattendus")
        headers.setdefault("Content-Type", content_type)
        req = Request(_check_public_https(info["upload_url"]), data=data, method="PUT", headers=headers)
        with self._open(req, timeout=120) as resp:
            if not 200 <= resp.status < 300:
                raise ApiError(f"Upload refusé ({resp.status})")
        return _check_public_https(info["public_url"])

    def download(self, url, dest):
        """Fetch a finished video without sending credentials to the media host."""
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_suffix(dest.suffix + ".part")
        with self._open(Request(_check_public_https(url), headers={"User-Agent": USER_AGENT}), timeout=300) as resp, \
                part.open("wb") as out:
            total = 0
            while chunk := resp.read(1 << 20):
                total += len(chunk)
                if total > MAX_DOWNLOAD:
                    raise ApiError("Vidéo trop volumineuse")
                out.write(chunk)
        part.replace(dest)
        return dest


def media_urls(result):
    """Collect output URLs from a completed status response."""
    urls = []
    for key in ("video", "videos", "images", "output", "outputs"):
        value = result.get(key)
        for item in value if isinstance(value, list) else [value]:
            url = item.get("url") if isinstance(item, dict) else item if isinstance(item, str) else None
            if url and url.startswith("https://") and url not in urls:
                urls.append(url)
    return urls


def estimate_usd(result):
    for key in ("usd", "price_usd", "cost_usd"):
        if isinstance(result.get(key), (int, float, str)):
            try:
                return float(result[key])
            except ValueError:
                pass
    return None


def _explain(code, detail):
    hints = {
        401: "clé API invalide ou révoquée",
        402: "solde insuffisant — rechargez votre compte API (minimum 5 $)",
        403: "modèle non activé pour cette clé — sélectionnez Seedance 2.5 dans la console API",
        422: "paramètres refusés par le modèle",
        429: "trop de requêtes — attendez la fin des générations en cours",
    }
    hint = hints.get(code, "erreur de l'API")
    return f"HTTP {code} : {hint}. {detail[:500]}".strip()
