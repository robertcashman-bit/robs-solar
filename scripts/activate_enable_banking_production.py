#!/usr/bin/env python3
"""Enable Banking production diagnostics, sign-in, and activation helper.

Uses the saved Firebase refresh token (robertdavidcashman@gmail.com) for Control
Panel API access. Discovered CP endpoints (not the public AIS API):
  GET  /api/aspsps              (Firebase token)
  POST /api/link_accounts       (Firebase token — starts bank linking / activation)
"""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
from pathlib import Path
from urllib.parse import urlencode

import httpx

ROOT = Path(__file__).resolve().parent.parent
SECRETS = ROOT / "backend" / ".secrets" / "enable_banking"
FIREBASE_API_KEY = "AIzaSyBn8fvjRYQKslskRaO3cblUjmcyl5b9o-c"
CP_SIGN_IN = "https://enablebanking.com/sign-in/?next=%2Fcp%2Fapplications"
CP_APP_URL = "https://enablebanking.com/cp/applications"
SIGN_IN_EMAIL = "robertdavidcashman@gmail.com"
TARGET_BANKS = ("Lloyds", "MBNA", "Virgin Money", "Halifax", "Monzo", "Starling")


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


def send_sign_in_link(email: str) -> None:
    response = httpx.post(
        f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FIREBASE_API_KEY}",
        json={
            "requestType": "EMAIL_SIGNIN",
            "email": email,
            "continueUrl": CP_APP_URL,
            "canHandleCodeInApp": False,
        },
        timeout=60,
    )
    response.raise_for_status()
    print(f"Sign-in link sent to {email} — check inbox and spam.")


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


def cp_aspsps(id_token: str, *, country: str = "GB") -> list[dict[str, object]]:
    response = httpx.get(
        "https://enablebanking.com/api/aspsps",
        headers={"Authorization": f"Bearer {id_token}", "Accept": "application/json"},
        params={"country": country, "psu_type": "personal"},
        timeout=90,
    )
    response.raise_for_status()
    rows = response.json().get("aspsps", [])
    return rows if isinstance(rows, list) else []


def start_link_accounts(
    id_token: str,
    *,
    app_id: str,
    country: str,
    aspsp_name: str,
) -> str:
    body = urlencode(
        {
            "country": country,
            "aspsp": aspsp_name,
            "appId": app_id,
            "psuType": "personal",
            "redirectUrl": "https://enablebanking.com/api/auth_redirect",
        }
    )
    response = httpx.post(
        "https://enablebanking.com/api/link_accounts",
        headers={
            "Authorization": f"Bearer {id_token}",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        content=body,
        timeout=90,
    )
    if response.status_code >= 400:
        raise httpx.HTTPStatusError(
            f"link_accounts failed: {response.text[:300]}",
            request=response.request,
            response=response,
        )
    url = response.json().get("url")
    if not url:
        raise SystemExit(f"link_accounts returned no URL: {response.text[:300]}")
    return str(url)


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


def find_production_app(apps: list[dict[str, object]]) -> dict[str, object] | None:
    for app in apps:
        if app.get("environment") == "PRODUCTION":
            return app
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Enable Banking production activation helper")
    parser.add_argument(
        "--backend-url",
        default="https://robs-solar.vercel.app/backend",
        help="Hosted backend base URL",
    )
    parser.add_argument(
        "--send-sign-in-link",
        action="store_true",
        help="Email a Control Panel magic sign-in link to robertdavidcashman@gmail.com",
    )
    parser.add_argument(
        "--open-cp",
        action="store_true",
        help="Open Enable Banking sign-in in the default browser",
    )
    parser.add_argument(
        "--start-link",
        metavar="BANK",
        default="",
        help="Start CP account linking (e.g. 'Revolut' with --link-country IE)",
    )
    parser.add_argument(
        "--link-country",
        default="IE",
        help="Country code for --start-link (default IE — GB has no banks on this account)",
    )
    args = parser.parse_args()

    id_token, _session = firebase_session()
    apps = list_applications(id_token)
    production = find_production_app(apps)
    if production is None:
        print("No production application found.", file=sys.stderr)
        return 1

    name = production.get("name")
    active = production.get("active")
    kid = str(production.get("kid") or "")

    print(f"Signed in (API) as: {SIGN_IN_EMAIL}")
    print(f"Production app: {name}")
    print(f"Application ID: {kid}")
    print(f"Active in Enable Banking: {active}")

    gb_banks = cp_aspsps(id_token, country="GB")
    uk_matches = [
        row["name"]
        for row in gb_banks
        if any(needle.lower() in str(row.get("name", "")).lower() for needle in TARGET_BANKS)
    ]
    print(f"\nUK (GB) banks available on your Enable account: {len(gb_banks)}")
    if uk_matches:
        print("  Matches for Lloyds/MBNA/Virgin:", ", ".join(uk_matches))
    else:
        print(
            "  No Lloyds, MBNA, Virgin Money, Monzo, or Starling listed under GB.\n"
            "  Enable Banking on your account does not currently offer UK open banking.\n"
            "  For Lloyds / MBNA / Virgin, switch Open Banking provider to GoCardless\n"
            "  (Bank Account Data) in /finance/open-banking/settings — free for personal use."
        )

    try:
        readiness = hosted_readiness(args.backend_url)
        print("\nHosted app readiness:")
        print(
            json.dumps(
                {
                    "provider_ready": readiness.get("provider_ready"),
                    "readiness_status": readiness.get("readiness_status"),
                    "readiness_message": readiness.get("readiness_message"),
                },
                indent=2,
            )
        )
    except httpx.HTTPError as exc:
        print(f"\nCould not query hosted readiness: {exc}", file=sys.stderr)

    if args.send_sign_in_link:
        send_sign_in_link(SIGN_IN_EMAIL)

    if args.start_link:
        if not kid:
            print("Missing application kid.", file=sys.stderr)
            return 1
        try:
            bank_url = start_link_accounts(
                id_token,
                app_id=kid,
                country=args.link_country.upper(),
                aspsp_name=args.start_link,
            )
            print(f"\nBank linking URL ({args.link_country} / {args.start_link}):")
            print(bank_url)
            if args.open_cp:
                webbrowser.open(bank_url)
        except httpx.HTTPError as exc:
            print(f"\nCould not start account linking: {exc}", file=sys.stderr)
            return 1

    if not active:
        print(
            "\n--- Control Panel access ---\n"
            f"1. Sign in at {CP_SIGN_IN}\n"
            f"   Use {SIGN_IN_EMAIL} (not AOL — the app is registered under Gmail).\n"
            "2. Check Gmail for the magic link (run with --send-sign-in-link if needed).\n"
            f"3. Open Applications → '{name}' → Activate by linking accounts.\n"
            "4. Pick a bank Enable actually lists (GB is empty on your account; try IE Revolut\n"
            "   if you have it: --start-link Revolut --link-country IE).\n"
            "5. After activation, return to https://robs-solar.vercel.app/finance/connect"
        )
    elif gb_banks:
        print("\nApp is active and UK banks are listed — connect at /finance/connect")
    else:
        print(
            "\nApp may be active but UK banks are still unavailable on Enable Banking.\n"
            "Use GoCardless for Lloyds / MBNA / Virgin Money."
        )

    if args.open_cp and not args.start_link:
        webbrowser.open(CP_SIGN_IN)

    if active and gb_banks:
        return 0
    if active and not gb_banks:
        return 3
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
