import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ad_studio import cli, studio
from ad_studio.client import ApiError, HiggsfieldClient, media_urls
from ad_studio.models import MODELS, ValidationError, build_payload
from ad_studio.templates import TEMPLATES, render


class FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeOpener:
    """Records requests and answers from a route table."""

    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def open(self, req, timeout=None):
        self.calls.append(req)
        body = self.routes[(req.get_method(), req.full_url)]
        return FakeResponse(body if isinstance(body, bytes) else json.dumps(body).encode())


BASE = "https://api.higgsfield.ai"
T2V = f"{BASE}/bytedance/seedance-2.5/text-to-video"


class PayloadTests(unittest.TestCase):
    def test_t2v_payload_matches_schema(self):
        p = build_payload(MODELS["t2v"], "a bottle", duration=8, aspect_ratio="9:16")
        self.assertEqual(set(p), {"prompt", "duration", "resolution", "aspect_ratio", "output_format", "generate_audio"})

    def test_rejects_out_of_range(self):
        for kwargs in ({"duration": 3}, {"duration": 31}, {"resolution": "1080p"}, {"aspect_ratio": "4:5"}):
            with self.assertRaises(ValidationError):
                build_payload(MODELS["t2v"], "x", **kwargs)

    def test_i2v_requires_public_image(self):
        with self.assertRaises(ValidationError):
            build_payload(MODELS["i2v"], "x")
        p = build_payload(MODELS["i2v"], "x", image_url="https://cdn.example/p.png")
        self.assertEqual(p["image_url"], "https://cdn.example/p.png")

    def test_t2v_refuses_image(self):
        with self.assertRaises(ValidationError):
            build_payload(MODELS["t2v"], "x", image_url="https://cdn.example/p.png")


class TemplateTests(unittest.TestCase):
    def test_every_template_renders(self):
        for key in TEMPLATES:
            prompt = render(key, "a serum bottle", "glowing skin", script="Zwin bzaf")
            self.assertIn("a serum bottle", prompt)
            self.assertIn("Moroccan Darija", prompt)
            self.assertNotIn("{", prompt)

    def test_product_required(self):
        with self.assertRaises(ValueError):
            render("hero", " ")


class ClientTests(unittest.TestCase):
    def test_auth_header_and_model_allowlist(self):
        opener = FakeOpener({("POST", T2V): {"request_id": "r1", "status": "queued"}})
        client = HiggsfieldClient("id:secret", opener=opener)
        client.submit("bytedance/seedance-2.5/text-to-video", {"prompt": "x"})
        self.assertEqual(opener.calls[0].get_header("Authorization"), "Key id:secret")
        with self.assertRaises(ApiError):
            client.submit("kling/v3/text-to-video", {"prompt": "x"})

    def test_missing_credentials(self):
        with mock.patch.dict("os.environ", {}, clear=True), self.assertRaises(ApiError):
            HiggsfieldClient()

    def test_media_urls_shapes(self):
        self.assertEqual(media_urls({"video": {"url": "https://a/v.mp4"}}), ["https://a/v.mp4"])
        self.assertEqual(media_urls({"videos": [{"url": "https://a/1.mp4"}, "https://a/2.mp4"]}),
                         ["https://a/1.mp4", "https://a/2.mp4"])


class StudioFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        patches = [mock.patch.object(studio, "ROOT", root), mock.patch.object(studio, "OUTPUTS", root / "outputs")]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.ledger = studio.Ledger(root / "work" / "ledger.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_submit_poll_download_and_consumption(self):
        opener = FakeOpener({
            ("POST", f"{BASE}/estimate/bytedance/seedance-2.5/text-to-video"): {"credits": 10, "usd": 1.44},
            ("POST", T2V): {"request_id": "abc", "status": "queued"},
            ("GET", f"{BASE}/requests/abc/status"): {"status": "completed", "video": {"url": "https://cdn.hf/v.mp4"}},
            ("GET", "https://cdn.hf/v.mp4"): b"MP4DATA",
        })
        client = HiggsfieldClient("id:secret", opener=opener)
        job = studio.submit(client, self.ledger, "t2v", "a bottle", duration=8, template="hero")
        self.assertEqual(job["estimate_usd"], 1.44)
        done = studio.wait(client, self.ledger, "abc", timeout=5)
        self.assertEqual(done["status"], "completed")
        self.assertEqual(Path(studio.ROOT, done["files"][0]).read_bytes(), b"MP4DATA")
        media_req = opener.calls[-1]
        self.assertIsNone(media_req.get_header("Authorization"))
        self.assertEqual(self.ledger.consumption(), {"jobs": 1, "videos": 1, "seconds": 8, "estimated_usd": 1.44})

    def test_cli_prompt_is_offline(self):
        out = io.StringIO()
        with mock.patch("sys.stdout", out), mock.patch.dict("os.environ", {}, clear=True):
            code = cli.main(["prompt", "--template", "ugc", "--product", "argan oil", "--language", "fr"])
        self.assertEqual(code, 0)
        data = json.loads(out.getvalue())
        self.assertEqual(data["model"], "t2v")
        self.assertEqual(data["duration"], TEMPLATES["ugc"].duration)


if __name__ == "__main__":
    unittest.main()
