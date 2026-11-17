"""Checks Mini App initData validation and start params. Run: BOT_TOKEN=test python tests/test_webapi.py"""
import hashlib
import hmac
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
import webapi  # noqa: E402


def signed(fields: dict, token: str = None) -> str:
    token = token or config.BOT_TOKEN
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    h = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": h})


base = {"auth_date": str(int(time.time())), "user": json.dumps({"id": 7, "first_name": "A"}), "start_param": "g5133399850"}
ok = webapi.verify_init_data(signed(base))
assert ok and ok["user"]["id"] == 7, "valid initData rejected"
assert webapi.verify_init_data(signed(base, "other-token")) is None, "wrong token accepted"
tampered = signed(base).replace("g5133399850", "g1")
assert webapi.verify_init_data(tampered) is None, "tampered data accepted"
old = dict(base, auth_date=str(int(time.time()) - 10 * 86400))
assert webapi.verify_init_data(signed(old)) is None, "stale initData accepted"
assert webapi.verify_init_data("") is None
assert webapi.parse_start_param("g5133399850") == -5133399850
assert webapi.parse_start_param("u42") == 42
assert webapi.parse_start_param("x1") is None and webapi.parse_start_param(None) is None
print("webapi ok")
