#!/usr/bin/env python3
"""Check production Enable Banking app status and print activation steps.

Uses the saved Firebase refresh token (robertdavidcashman@gmail.com) for CP API
access. Restricted Production activation still requires linking a real bank
account through Enable Banking's authorisation UI — that step cannot be completed
via API alone.
"""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
SECRETS = ROOT / "backend" / ".secrets" / "enable_banking"
FIREBASE_API_KEY = "AIzaSyBn8fvjRYQKslskRaO3cblUjmcyl5b9o-c"
CP_APPLICATIONS = "https://enablebanking.com/cp/applications"
PRODUCTION_KID = "fd4c8a86-6433-4f04-9086-7f7a44d69e8c"


def firebase_session() -> tuple[str, dict[str, object]]:
    refresh_file = SECRETS / "firebase_refresh.txt"
    if not refresh_file.exists():
        raise SystemExit(f"Missing {refresh_file}")
    refresh = refresh_file.read_text(encoding="utf-8").strip()
    response = httpx.post(
        f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}",
        data={"grant_type": "refresh_token", "refresh_token": refresh},
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    return str(data["id_token"]), data


def list_applications(id_token: str) -> list[dict[str, object]]:
    response = httpx.get(
        "https://enablebanking.com/api/applications",
        headers={"Authorization": f"Bearer {id_token}", "Accept": "application/json"},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise SystemExit(f"Unexpected applications response: {payload}")
    return payload


def find_production_app(apps: list[dict[str, object]]) -> dict[str, object] | None:
    for app in apps:
        if app.get("environment") == "PRODUCTION":
            return app
    return None


def hosted_readiness(backend_url: str) -> dict[str, object]:
    with httpx.Client(base_url=backend_url.rstrip("/"), timeout=60) as client:
        login = client.post(
            "/auth/login",
            json={"username": "admin", "password": "change-me-admin"},
        )
        login.raise_for_status()
        status = client.get("/finance/integrations/open-banking/status")
        status.raise_for_status()
        return status.json()


def firebase_browser_storage(session: dict[str, object]) -> str:
    """Build localStorage payload for Enable Banking Firebase web auth."""
    import base64

    id_token = str(session["id_token"])
    payload = id_token.split(".")[1] + "=="
    claims = json.loads(base64.urlsafe_b64decode(payload))
    expiration_ms = int(claims.get("exp", 0)) * 1000
    auth_user = {
        "uid": session.get("user_id") or claims.get("user_id") or claims.get("sub"),
        "email": claims.get("email"),
        "emailVerified": bool(claims.get("email_verified")),
        "isAnonymous": False,
        "providerData": [],
        "stsTokenManager": {
            "refreshToken": session.get("refresh_token"),
            "accessToken": session.get("access_token") or id_token,
            "expirationTime": expiration_ms,
        },
    }
    storage_key = f"firebase:authUser:{FIREBASE_API_KEY}:[DEFAULT]"
    return json.dumps({storage_key: json.dumps(auth_user)})


def main() -> int:
    parser = argparse.ArgumentParser(description="Enable Banking production activation helper")
    parser.add_argument(
        "--backend-url",
        default="https://robs-solar.vercel.app/backend",
        help="Hosted backend base URL",
    )
    parser.add_argument(
        "--open-cp",
        action="store_true",
        help="Open Enable Banking Control Panel in the default browser",
    )
    parser.add_argument(
        "--print-browser-auth",
        action="store_true",
        help="Print Firebase localStorage JSON for manual browser session injection",
    )
    args = parser.parse_args()

    id_token, session = firebase_session()
    apps = list_applications(id_token)
    production = find_production_app(apps)
    if production is None:
        print("No production application found.", file=sys.stderr)
        return 1

    name = production.get("name")
    active = production.get("active")
    kid = production.get("kid")
    print(f"Signed in as: robertdavidcashman@gmail.com")
    print(f"Production app: {name}")
    print(f"Application ID (kid): {kid}")
    print(f"CP active flag: {active}")

    try:
        readiness = hosted_readiness(args.backend_url)
        print("\nHosted readiness:")
        print(json.dumps(
            {
                "provider_ready": readiness.get("provider_ready"),
                "readiness_status": readiness.get("readiness_status"),
                "readiness_message": readiness.get("readiness_message"),
            },
            indent=2,
        ))
    except httpx.HTTPError as exc:
        print(f"\nCould not query hosted readiness: {exc}", file=sys.stderr)

    if active:
        print("\nProduction app is already active in Enable Banking.")
        return 0

    print(
        "\nActivation requires linking at least one real bank account in the Control Panel.\n"
        "Enable Banking does not expose a public API for this step — complete it in the CP UI:"
    )
    print(f"  1. Open {CP_APPLICATIONS}")
    print(f"  2. Open '{name}'")
    print("  3. Click 'Activate by linking accounts'")
    print("  4. Sign in at Lloyds, MBNA, or Virgin Money and authorise access")
    print("  5. Return to https://robs-solar.vercel.app/finance/connect")

    if args.print_browser_auth:
        print("\nFirebase localStorage injection payload:")
        print(firebase_browser_storage(session))

    if args.open_cp:
        webbrowser.open(CP_APPLICATIONS)

    return 2 if not active else 0


if __name__ == "__main__":
    raise SystemExit(main())
