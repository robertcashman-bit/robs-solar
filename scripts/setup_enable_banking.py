#!/usr/bin/env python3
"""Enable Banking setup: local sandbox, or hosted Restricted Production via Vercel."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parent.parent
SECRETS = ROOT / "backend" / ".secrets" / "enable_banking"
ENV_FILE = ROOT / "backend" / ".env"
LOCAL_BACKEND = "http://127.0.0.1:8000"
LOCAL_REDIRECT = "http://127.0.0.1:3000/open-banking/callback"
FIREBASE_API_KEY = "AIzaSyBn8fvjRYQKslskRaO3cblUjmcyl5b9o-c"
ENABLE_APPS_API = "https://enablebanking.com/api/applications"

SANDBOX_ENV_KEYS = {
    "OPEN_BANKING_PROVIDER": "enable_banking",
    "ENABLE_BANKING_ENVIRONMENT": "SANDBOX",
    "OPEN_BANKING_REDIRECT_URL": LOCAL_REDIRECT,
}


def ensure_keys() -> tuple[Path, Path]:
    SECRETS.mkdir(parents=True, exist_ok=True)
    private = SECRETS / "private.pem"
    public = SECRETS / "public.crt"
    if not private.exists() or not public.exists():
        subprocess.run(
            [
                "openssl",
                "req",
                "-new",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-keyout",
                str(private),
                "-x509",
                "-days",
                "730",
                "-out",
                str(public),
                "-subj",
                "/CN=Rob Finance/O=Rob's Finance/C=GB",
            ],
            check=True,
        )
        private.chmod(0o600)
    return private, public


def read_env() -> dict[str, str]:
    if not ENV_FILE.exists():
        return {}
    out: dict[str, str] = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out


def upsert_env(updates: dict[str, str]) -> None:
    lines: list[str] = []
    seen: set[str] = set()
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key = line.split("=", 1)[0].strip()
                if key in updates:
                    lines.append(f"{key}={updates[key]}")
                    seen.add(key)
                    continue
            lines.append(line)
    for key, value in updates.items():
        if key not in seen:
            lines.append(f"{key}={value}")
    text = "\n".join(lines) + ("\n" if lines else "")
    ENV_FILE.write_text(text, encoding="utf-8")


def load_sandbox_application_id(env: dict[str, str]) -> str:
    app_id_file = SECRETS / "application_id"
    if app_id_file.exists():
        file_id = app_id_file.read_text(encoding="utf-8").strip()
        if file_id:
            return file_id
    return env.get("ENABLE_BANKING_APPLICATION_ID", "").strip()


def load_production_application_id() -> str:
    app_id_file = SECRETS / "application_id_production"
    if app_id_file.exists():
        return app_id_file.read_text(encoding="utf-8").strip()
    return ""


def enable_firebase_token() -> str:
    refresh_file = SECRETS / "firebase_refresh.txt"
    if not refresh_file.exists():
        raise SystemExit(
            f"Missing {refresh_file} — sign in at enablebanking.com and save refresh token."
        )
    refresh = refresh_file.read_text(encoding="utf-8").strip()
    response = httpx.post(
        f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}",
        data={"grant_type": "refresh_token", "refresh_token": refresh},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["id_token"]


def require_https_url(url: str, label: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SystemExit(f"{label} must be HTTPS: {url}")
    return url.rstrip("/")


def base_url_from_redirect(redirect_url: str) -> str:
    parsed = urlparse(redirect_url)
    return f"{parsed.scheme}://{parsed.netloc}"


def register_production_app(
    redirect_url: str,
    gdpr_email: str,
    cert: str,
    token: str,
) -> str:
    base = base_url_from_redirect(redirect_url)
    body = {
        "name": "Rob's Finance Production",
        "certificate": cert,
        "environment": "PRODUCTION",
        "redirect_urls": [redirect_url],
        "description": "Personal finance dashboard — read-only bank balance sync",
        "gdpr_email": gdpr_email,
        "privacy_url": f"{base}/privacy",
        "terms_url": f"{base}/terms",
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    response = httpx.post(ENABLE_APPS_API, headers=headers, json=body, timeout=60)
    if response.status_code >= 400:
        raise SystemExit(f"Enable app registration failed ({response.status_code}): {response.text[:800]}")
    data = response.json()
    app_id = data.get("app_id") or data.get("application_id") or data.get("id")
    if not app_id:
        raise SystemExit(f"Enable response missing app_id: {data}")
    return str(app_id)


def api_configure(
    *,
    backend_url: str,
    private_pem: str,
    application_id: str,
    environment: str,
    redirect_url: str,
    env: dict[str, str],
) -> None:
    password = env.get("ADMIN_PASSWORD", "change-me-admin")
    username = env.get("ADMIN_USERNAME", "admin")
    with httpx.Client(base_url=backend_url, timeout=60.0, follow_redirects=True) as client:
        login = client.post(
            "/auth/login",
            json={"username": username, "password": password},
        )
        login.raise_for_status()
        csrf = login.json().get("csrf_token", "")

        settings_body = {
            "provider": "enable_banking",
            "application_id": application_id,
            "private_key_pem": private_pem,
            "environment": environment,
            "redirect_url": redirect_url,
            "secret_id": "",
            "secret_key": "",
        }
        headers = {"X-CSRF-Token": csrf} if csrf else {}
        put = client.put(
            "/finance/integrations/open-banking/settings",
            json=settings_body,
            headers=headers,
        )
        put.raise_for_status()
        print("Open Banking settings saved:", json.dumps(put.json(), indent=2))

        test = client.post("/finance/integrations/open-banking/test", headers=headers)
        test.raise_for_status()
        print("Connection test:", json.dumps(test.json(), indent=2))


def run_sandbox(args) -> int:
    private, public = ensure_keys()
    private_pem = private.read_text(encoding="utf-8")
    env = read_env()

    upsert_env(
        {
            **SANDBOX_ENV_KEYS,
            "ENABLE_BANKING_PRIVATE_KEY_PATH": str(private.resolve()),
        }
    )

    application_id = load_sandbox_application_id(env)

    if args.open:
        subprocess.run(["open", str(SECRETS)], check=False)
        subprocess.run(["open", "https://enablebanking.com/cp/"], check=False)

    print(f"Private key: {private}")
    print(f"Public cert: {public}")
    print(f"Redirect URL: {LOCAL_REDIRECT}")

    app_id_file = SECRETS / "application_id"
    if args.wait and not application_id:
        import time

        print(f"Waiting up to {args.wait}s for {app_id_file} …")
        deadline = time.time() + args.wait
        while time.time() < deadline:
            if app_id_file.exists():
                application_id = app_id_file.read_text(encoding="utf-8").strip()
                if application_id:
                    break
            time.sleep(2)

    if not application_id:
        print(
            f"\nMissing sandbox application_id — create in CP then:\n"
            f"  echo 'YOUR-APP-ID' > {app_id_file}",
            file=sys.stderr,
        )
        return 2

    upsert_env({"ENABLE_BANKING_APPLICATION_ID": application_id})
    try:
        api_configure(
            backend_url=LOCAL_BACKEND,
            private_pem=private_pem,
            application_id=application_id,
            environment="SANDBOX",
            redirect_url=LOCAL_REDIRECT,
            env=env,
        )
    except httpx.HTTPError as exc:
        print(f"API setup failed: {exc}", file=sys.stderr)
        if hasattr(exc, "response") and exc.response is not None:
            print(exc.response.text[:500], file=sys.stderr)
        return 1

    subprocess.run(["open", "http://127.0.0.1:3000/settings"], check=False)
    print("\nSandbox setup done.")
    return 0


def run_production(args) -> int:
    redirect_url = require_https_url(args.redirect_url, "Redirect URL")
    backend_url = args.backend_url.rstrip("/")
    private, _public = ensure_keys()
    private_pem = private.read_text(encoding="utf-8")
    cert = (SECRETS / "public.crt").read_text(encoding="utf-8")
    env = read_env()

    gdpr_email = args.gdpr_email or env.get("ENABLE_BANKING_GDPR_EMAIL", "robertdcashman@aol.com")

    application_id = load_production_application_id()
    if not application_id or args.force_register:
        print("Registering Enable Banking Production app…")
        token = enable_firebase_token()
        application_id = register_production_app(redirect_url, gdpr_email, cert, token)
        (SECRETS / "application_id_production").write_text(application_id + "\n", encoding="utf-8")
        print(f"Production Application ID: {application_id}")
    else:
        print(f"Using existing Production Application ID: {application_id}")

    production_env = {
        "OPEN_BANKING_PROVIDER": "enable_banking",
        "ENABLE_BANKING_APPLICATION_ID": application_id,
        "ENABLE_BANKING_PRIVATE_KEY_PEM": private_pem.replace("\n", "\\n"),
        "ENABLE_BANKING_ENVIRONMENT": "PRODUCTION",
        "OPEN_BANKING_REDIRECT_URL": redirect_url,
    }
    upsert_env(production_env)

    try:
        api_configure(
            backend_url=backend_url,
            private_pem=private_pem,
            application_id=application_id,
            environment="PRODUCTION",
            redirect_url=redirect_url,
            env=env,
        )
    except httpx.HTTPError as exc:
        print(f"Hosted API setup failed: {exc}", file=sys.stderr)
        if hasattr(exc, "response") and exc.response is not None:
            print(exc.response.text[:800], file=sys.stderr)
        return 1

    base = base_url_from_redirect(redirect_url)
    print("\nProduction setup done.")
    print(f"Hosted app: {base}")
    print(f"Redirect:   {redirect_url}")
    print("\nNext: Enable Control Panel → Production app → Activate by linking accounts")
    subprocess.run(["open", "https://enablebanking.com/cp/"], check=False)
    return 0


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Enable Banking setup (sandbox or production)")
    parser.add_argument("--production", action="store_true", help="Register/configure hosted Production app")
    parser.add_argument("--redirect-url", default="", help="HTTPS redirect URL (production)")
    parser.add_argument(
        "--backend-url",
        default="",
        help="Backend API base URL (default: derived from redirect /backend or local)",
    )
    parser.add_argument("--gdpr-email", default="", help="GDPR contact email for Enable registration")
    parser.add_argument(
        "--force-register",
        action="store_true",
        help="Register a new Production app even if application_id_production exists",
    )
    parser.add_argument("--wait", type=int, default=0, metavar="SECONDS", help="Sandbox: wait for app_id file")
    parser.add_argument("--open", action="store_true", help="Open Control Panel (sandbox)")
    args = parser.parse_args()

    if args.production:
        if not args.redirect_url:
            print("--redirect-url is required for --production", file=sys.stderr)
            return 2
        if not args.backend_url:
            base = base_url_from_redirect(require_https_url(args.redirect_url, "Redirect URL"))
            args.backend_url = f"{base}/backend"
        return run_production(args)

    return run_sandbox(args)


if __name__ == "__main__":
    raise SystemExit(main())
