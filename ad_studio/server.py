"""Local web studio: python -m ad_studio.server  ->  http://127.0.0.1:8787

The browser never sees the API key: the page talks to this local server,
which holds the key and forwards only Seedance 2.5 requests to Higgsfield.
Binds to 127.0.0.1 by default. Do not expose it publicly without adding
your own authentication, or anyone could spend your balance.
"""

import argparse
import base64
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from . import studio
from .client import ApiError, HiggsfieldClient, load_dotenv
from .models import MODELS, ValidationError
from .templates import LANGUAGES, TEMPLATES, render

WEB = Path(__file__).resolve().parent / "web"
MAX_BODY = 48 * 1024 * 1024


class Handler(BaseHTTPRequestHandler):
    ledger = studio.Ledger()
    _client = None

    @classmethod
    def client(cls):
        if cls._client is None:
            cls._client = HiggsfieldClient()
        return cls._client

    def log_message(self, fmt, *args):  # keep prompts out of the terminal log
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise ValidationError("Requête trop volumineuse")
        return json.loads(self.rfile.read(length) or b"{}")

    def _file(self, base, rel):
        path = (base / rel).resolve()
        if base.resolve() not in path.parents or not path.is_file():
            return self._send(404, {"error": "introuvable"})
        self._send(200, path.read_bytes(), mimetypes.guess_type(path.name)[0] or "application/octet-stream")

    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        if path in ("/", "/index.html"):
            return self._file(WEB, "index.html")
        if path.startswith("/outputs/"):
            return self._file(studio.OUTPUTS, path[len("/outputs/"):])
        if path == "/api/config":
            return self._send(200, {
                "models": {k: m.label for k, m in MODELS.items()},
                "templates": {k: {"name": t.name, "goal": t.goal, "aspect_ratio": t.aspect_ratio,
                                  "duration": t.duration} for k, t in TEMPLATES.items()},
                "languages": LANGUAGES,
            })
        if path == "/api/history":
            return self._send(200, {"jobs": self.ledger.load()[::-1], "consumption": self.ledger.consumption()})
        if path.startswith("/api/status/"):
            return self._api(lambda: studio.refresh(self.client(), self.ledger, path.rsplit("/", 1)[1]))
        self._send(404, {"error": "introuvable"})

    def do_POST(self):
        path = urlsplit(self.path).path
        routes = {
            "/api/prompt": self._prompt,
            "/api/estimate": self._estimate,
            "/api/generate": self._generate,
            "/api/upload": self._upload,
        }
        if path not in routes:
            return self._send(404, {"error": "introuvable"})
        self._api(lambda: routes[path](self._json()))

    def _api(self, fn):
        try:
            self._send(200, fn())
        except (ValidationError, ValueError, KeyError) as exc:
            self._send(400, {"error": str(exc)})
        except ApiError as exc:
            self._send(502, {"error": str(exc)})

    @staticmethod
    def _spec(body):
        prompt = (body.get("prompt") or "").strip()
        tkey = body.get("template") or "custom"
        if not prompt:
            prompt = render(tkey, body.get("product", ""), body.get("description", ""),
                            body.get("audience", ""), body.get("persona", ""), body.get("setting", ""),
                            body.get("language", "darija"), body.get("script", ""))
        image_url = body.get("image_url") or None
        params = {
            "duration": int(body.get("duration") or 5),
            "resolution": body.get("resolution") or "720p",
            "aspect_ratio": body.get("aspect_ratio") or "9:16",
            "generate_audio": bool(body.get("generate_audio", True)),
            "image_url": image_url,
        }
        return ("i2v" if image_url else "t2v"), prompt, params, tkey

    def _prompt(self, body):
        return {"prompt": self._spec(body)[1]}

    def _estimate(self, body):
        model, prompt, params, _ = self._spec(body)
        est = studio.estimate(self.client(), model, prompt, **params)
        return {"usd": est["usd"], "raw": est["raw"]}

    def _generate(self, body):
        model, prompt, params, tkey = self._spec(body)
        return studio.submit(self.client(), self.ledger, model, prompt,
                             label=body.get("label", ""), template=tkey, **params)

    def _upload(self, body):
        data = base64.b64decode(body.get("data", ""), validate=True)
        return {"public_url": self.client().upload(data=data, content_type=body.get("content_type"))}


def main(argv=None):
    load_dotenv(studio.ROOT / ".env")
    parser = argparse.ArgumentParser(description="Studio web local Seedance 2.5")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Open Higgsfield Ad Studio → http://{args.host}:{args.port}  (Ctrl+C pour arrêter)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
