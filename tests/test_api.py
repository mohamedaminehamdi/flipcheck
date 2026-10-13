"""API guards: rate limit keyed on the proxy-written IP, upload size cap."""
import io

from fastapi.testclient import TestClient
from PIL import Image

from app import main


def test_spoofed_forwarded_for_does_not_reset_the_limit(monkeypatch):
    monkeypatch.setattr(main, "TRUST_PROXY", True)
    monkeypatch.setattr(main, "LIMIT", 2)
    main._hits.clear()
    client = TestClient(main.app)
    body = {"query": "", "condition": "used"}
    codes = [client.post("/api/price", json=body, headers={"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.7"}).status_code
             for i in range(3)]
    assert codes[:2] == [400, 400] and codes[2] == 429  # same real client (last entry) despite a fake first entry


def test_oversized_upload_is_refused(monkeypatch):
    monkeypatch.setattr(main, "MAX_BYTES", 1000)
    main._hits.clear()
    buf = io.BytesIO()
    Image.new("RGB", (400, 400), "red").save(buf, "PNG")
    res = TestClient(main.app).post("/api/identify", files={"photo": ("big.png", buf.getvalue() * 3, "image/png")})
    assert res.status_code == 413


def test_declared_oversized_body_is_refused_before_reading():
    main._hits.clear()
    res = TestClient(main.app).post("/api/identify", content=b"x" * 10, headers={"content-length": str(50 * 1024 * 1024),
                                                                                "content-type": "application/octet-stream"})
    assert res.status_code == 413


def test_ipv6_clients_share_their_64_block(monkeypatch):
    monkeypatch.setattr(main, "TRUST_PROXY", True)

    class R:
        def __init__(self, ip):
            self.headers = {"x-forwarded-for": ip}
            self.client = None

    assert main.client_ip(R("2001:db8:1:2::1")) == main.client_ip(R("2001:db8:1:2:ffff::9"))
    assert main.client_ip(R("2001:db8:1:3::1")) != main.client_ip(R("2001:db8:1:2::1"))
    assert main.client_ip(R("203.0.113.7")) == "203.0.113.7"
