"""Send a local file to a Feishu user using credentials from OpenClaw config."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from pathlib import Path
from typing import Any

import requests


OPENCLAW_CONFIG = Path.home() / ".openclaw" / "openclaw.json"
FEISHU_BASE = "https://open.feishu.cn/open-apis"
DEFAULT_USER_OPEN_ID = "ou_065e5bdad4f0989b318e12d180050312"


def load_openclaw_feishu_account(account: str) -> dict[str, str]:
    data = json.loads(OPENCLAW_CONFIG.read_text(encoding="utf-8"))
    accounts = (
        data.get("channels", {})
        .get("feishu", {})
        .get("accounts", {})
    )
    if account not in accounts:
        raise KeyError(f"Feishu account '{account}' not found in {OPENCLAW_CONFIG}")
    item = accounts[account]
    app_id = item.get("appId")
    app_secret = item.get("appSecret")
    if not app_id or not app_secret:
        raise ValueError(f"Feishu account '{account}' is missing appId/appSecret")
    return {"app_id": app_id, "app_secret": app_secret}


def get_access_token(app_id: str, app_secret: str) -> str:
    response = requests.post(
        f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=20,
    )
    result = response.json()
    if result.get("code") != 0:
        raise RuntimeError(f"Failed to get tenant access token: {result}")
    return result["tenant_access_token"]


def upload_file(token: str, file_path: Path, file_name: str) -> str:
    mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
    with file_path.open("rb") as handle:
        files: dict[str, Any] = {
            "file": (file_name, handle, mime_type),
            "file_name": (None, file_name),
            "file_type": (None, "stream"),
        }
        response = requests.post(
            f"{FEISHU_BASE}/im/v1/files",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            timeout=60,
        )
    result = response.json()
    if result.get("code") != 0:
        raise RuntimeError(f"Failed to upload file: {result}")
    return result["data"]["file_key"]


def send_file_message(token: str, user_open_id: str, file_key: str) -> str:
    response = requests.post(
        f"{FEISHU_BASE}/im/v1/messages",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        params={"receive_id_type": "open_id"},
        json={
            "receive_id": user_open_id,
            "msg_type": "file",
            "content": json.dumps({"file_key": file_key}, ensure_ascii=False),
        },
        timeout=30,
    )
    result = response.json()
    if result.get("code") != 0:
        raise RuntimeError(f"Failed to send file message: {result}")
    return result.get("data", {}).get("message_id", "")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a file through Feishu using OpenClaw config.")
    parser.add_argument("file", type=Path)
    parser.add_argument("--account", default="main")
    parser.add_argument("--open-id", default=os.environ.get("FEISHU_OPEN_ID", DEFAULT_USER_OPEN_ID))
    parser.add_argument("--name", default=None, help="Override displayed file name.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    file_path = args.file.resolve()
    if not file_path.exists():
        raise FileNotFoundError(file_path)
    file_name = args.name or file_path.name
    account = load_openclaw_feishu_account(args.account)
    token = get_access_token(account["app_id"], account["app_secret"])
    file_key = upload_file(token, file_path, file_name)
    message_id = send_file_message(token, args.open_id, file_key)
    print(json.dumps(
        {
            "sent": True,
            "file": str(file_path),
            "file_name": file_name,
            "bytes": file_path.stat().st_size,
            "message_id": message_id,
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
