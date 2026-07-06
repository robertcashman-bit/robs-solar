#!/usr/bin/env python3
"""Upload Mock ASPSP data, complete sandbox auth via Tilisy, finalize, and sync."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx

ROOT = Path(__file__).resolve().parent.parent
SECRETS = ROOT / "backend" / ".secrets" / "enable_banking"
BACKEND = "http://127.0.0.1:8000"
TILISY = "https://tilisy-sandbox.enablebanking.com"
REDIRECT = "http://127.0.0.1:3000/open-banking/callback"
SAMPLE_JSON = "https://enablebanking.com/sample-data/DK-Danske_Bank-synthetic-1.json"
FIREBASE_API_KEY = "AIzaSyBn8fvjRYQKslskRaO3cblUjmcyl5b9o-c"
CP_API = "https://enablebanking.com/api/v2"


def firebase_id_token() -> str:
    refresh = (SECRETS / "firebase_refresh.txt").read_text(encoding="utf-8").strip()
    response = httpx.post(
        f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}",
        data={"grant_type": "refresh_token", "refresh_token": refresh},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["id_token"]


def cp_headers(id_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {id_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _account_ids(accounts_payload: object) -> list[str]:
    if isinstance(accounts_payload, dict):
        rows = accounts_payload.get("accounts", [])
    elif isinstance(accounts_payload, list):
        rows = accounts_payload
    else:
        rows = []
    ids: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        payload = row.get("payload") or {}
        if isinstance(payload, dict) and payload.get("resourceId"):
            ids.append(str(payload["resourceId"]))
    return ids


def ensure_mock_accounts(id_token: str) -> list[str]:
    headers = cp_headers(id_token)
    with httpx.Client(timeout=90) as client:
        listed = client.get(f"{CP_API}/cp/mock-aspsp/mock-accounts", headers=headers)
        listed.raise_for_status()
        account_ids = _account_ids(listed.json())
        if account_ids:
            return account_ids

        sample = client.get(SAMPLE_JSON)
        sample.raise_for_status()
        uploaded = client.post(
            f"{CP_API}/cp/mock-aspsp/mock-upload",
            json=sample.json(),
            headers=headers,
        )
        uploaded.raise_for_status()
        listed = client.get(f"{CP_API}/cp/mock-aspsp/mock-accounts", headers=headers)
        listed.raise_for_status()
        account_ids = _account_ids(listed.json())
        if account_ids:
            return account_ids

        payload = {
            "name": "Rob Personal Current",
            "cashAccountType": "CACC",
            "currency": "GBP",
            "usage": "PRIV",
            "bicFi": "LOYDGB21XXX",
            "psuStatus": "Account Holder",
        }
        created = client.post(
            f"{CP_API}/cp/mock-aspsp/mock-accounts",
            json={"title": "Rob Personal Current", "payload": payload},
            headers=headers,
        )
        created.raise_for_status()
        listed = client.get(f"{CP_API}/cp/mock-aspsp/mock-accounts", headers=headers)
        listed.raise_for_status()
        return _account_ids(listed.json())


def backend_login(client: httpx.Client) -> str:
    login = client.post(
        "/auth/login", json={"username": "admin", "password": "change-me-admin"}
    )
    login.raise_for_status()
    return login.json()["csrf_token"]


def backend_connect(client: httpx.Client, *, csrf: str) -> tuple[str, str]:
    response = client.post(
        "/finance/integrations/open-banking/connect",
        headers={"X-CSRF-Token": csrf},
        json={"institution_id": "FI:Mock ASPSP", "institution_name": "Mock ASPSP"},
    )
    response.raise_for_status()
    data = response.json()
    return str(data["state"]), str(data["link"])


def complete_tilisy_mock_auth(
    id_token: str,
    *,
    auth_link: str,
    account_ids: list[str],
) -> tuple[str, str]:
    """Drive Tilisy + Mock ASPSP and return (pending_state, enable auth code)."""
    headers = cp_headers(id_token)
    link_path = auth_link.replace(TILISY, "")

    with httpx.Client(base_url=TILISY, follow_redirects=True, timeout=90) as tilisy:

        def session_status() -> dict[str, object]:
            response = tilisy.get(
                "/ais/get_session_status",
                params={"current_uri": REDIRECT},
            )
            response.raise_for_status()
            body = response.json()
            response_obj = body.get("response")
            if not isinstance(response_obj, dict):
                raise RuntimeError(f"Unexpected Tilisy status response: {body}")
            return response_obj

        tilisy.get(link_path)

        consent = tilisy.post("/ais/confirm_data_sharing_consent")
        consent.raise_for_status()

        started = tilisy.post("/ais/start_authorization", json={})
        started.raise_for_status()

        status = session_status()
        bank_url = str(status.get("redirect_url") or "")
        if not bank_url:
            raise RuntimeError(
                f"Tilisy did not return a mock bank redirect URL: {status}"
            )

        bank_qs = parse_qs(urlparse(bank_url).query)
        mock_state = bank_qs.get("state", [""])[0]
        valid_until = bank_qs.get("valid_until", [""])[0]
        if not mock_state or not valid_until:
            raise RuntimeError(f"Mock bank URL missing state/valid_until: {bank_url}")

        leaving = tilisy.post("/ais/leaving")
        leaving.raise_for_status()

        mock_body = {
            "valid_until": valid_until,
            "redirect_url": f"{TILISY}/",
            "selected_accounts": account_ids,
        }
        mock_response = httpx.post(
            f"{CP_API}/cp/mock-aspsp/mock-access-token",
            params={"state": mock_state},
            json=mock_body,
            headers=headers,
            timeout=90,
        )
        mock_response.raise_for_status()
        mock_redirect = str(mock_response.json().get("redirect") or "")
        if not mock_redirect:
            raise RuntimeError(
                f"mock-access-token missing redirect: {mock_response.text}"
            )

        continued = tilisy.post(
            "/ais/continue_authorization",
            json={"redirect_uri": mock_redirect},
        )
        continued.raise_for_status()

        enable_redirect = ""
        for _ in range(30):
            status = session_status()
            if status.get("status") == "AuthDone":
                enable_redirect = str(status.get("redirect_url") or "")
                break
            time.sleep(0.5)

        if not enable_redirect:
            raise RuntimeError("Timed out waiting for Tilisy AuthDone status")

    callback = httpx.get(enable_redirect, follow_redirects=True, timeout=90)
    callback.raise_for_status()
    callback_qs = parse_qs(urlparse(str(callback.url)).query)
    pending_state = callback_qs.get("state", [""])[0]
    code = callback_qs.get("code", [""])[0]
    if not pending_state or not code:
        raise RuntimeError(
            f"Enable auth redirect missing callback params: {callback.url}"
        )
    return pending_state, code


def finalize_and_sync(state: str, code: str) -> dict[str, object]:
    with httpx.Client(base_url=BACKEND, timeout=120) as client:
        csrf = backend_login(client)
        finalized = client.post(
            "/finance/integrations/open-banking/finalize",
            headers={"X-CSRF-Token": csrf},
            json={"state": state, "code": code},
        )
        finalized.raise_for_status()
        result = finalized.json()

        synced = client.post(
            "/finance/integrations/open-banking/sync",
            headers={"X-CSRF-Token": csrf},
        )
        synced.raise_for_status()

        status = client.get("/finance/integrations/open-banking/status")
        status.raise_for_status()
        print("Status:", json.dumps(status.json(), indent=2))
        return result


def main() -> int:
    id_token = firebase_id_token()
    account_ids = ensure_mock_accounts(id_token)
    print(f"Mock accounts ready: {len(account_ids)}")

    with httpx.Client(base_url=BACKEND, timeout=90) as client:
        csrf = backend_login(client)
        pending_state, auth_link = backend_connect(client, csrf=csrf)
    print("Pending state:", pending_state)
    print("Auth link:", auth_link)

    cb_state, code = complete_tilisy_mock_auth(
        id_token,
        auth_link=auth_link,
        account_ids=account_ids,
    )
    print("Callback state:", cb_state)
    if cb_state != pending_state:
        print(
            "Warning: callback state differs from connect state; "
            f"connect={pending_state} callback={cb_state}"
        )

    result = finalize_and_sync(cb_state, code)
    print("Finalize:", json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        raise
