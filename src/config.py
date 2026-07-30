from __future__ import annotations

import csv
import os
import secrets
import string
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EMAILS_PATH = ROOT / "emails.csv"
load_dotenv(ROOT / ".env")

SIGNUP_URL = (
    "https://account.ycombinator.com/"
    "?continue=https%3A%2F%2Fwww.startupschool.org%2Fusers%2Fsign_in"
)


@dataclass
class AccountTarget:
    email: str
    first_name: str
    last_name: str
    linkedin_url: str
    username: str | None = None
    password: str | None = None


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def load_shared_profile() -> dict[str, str]:
    first_name = os.getenv("FIRST_NAME", "").strip()
    last_name = os.getenv("LAST_NAME", "").strip()
    linkedin_url = os.getenv("LINKEDIN_URL", "").strip()
    password = os.getenv("PASSWORD", "").strip()

    missing = [
        key
        for key, value in {
            "FIRST_NAME": first_name,
            "LAST_NAME": last_name,
            "LINKEDIN_URL": linkedin_url,
            "PASSWORD": password,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Copy .env.example to .env and fill them in."
        )

    return {
        "first_name": first_name,
        "last_name": last_name,
        "linkedin_url": linkedin_url,
        "password": password,
    }


def _looks_like_email(value: str) -> bool:
    return bool(value) and "@" in value


def _emails_from_csv(path: Path) -> list[str]:
    """Read emails from CSV: one per line, or an `email` column / first column."""
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return []

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    # Simple one-email-per-line file (no header / commas).
    if all("," not in line and _looks_like_email(line) for line in lines):
        return lines

    emails: list[str] = []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        sample = fh.read(2048)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel

        has_header = False
        try:
            has_header = csv.Sniffer().has_header(sample)
        except csv.Error:
            has_header = False

        if has_header:
            reader = csv.DictReader(fh, dialect=dialect)
            fieldnames = [name.strip().lower() for name in (reader.fieldnames or [])]
            email_key = None
            for candidate in ("email", "e-mail", "mail"):
                if candidate in fieldnames:
                    email_key = (reader.fieldnames or [])[fieldnames.index(candidate)]
                    break
            if email_key is None and reader.fieldnames:
                email_key = reader.fieldnames[0]

            for row in reader:
                if not email_key:
                    continue
                value = str(row.get(email_key, "")).strip()
                if value:
                    emails.append(value)
        else:
            reader = csv.reader(fh, dialect=dialect)
            for row in reader:
                if not row:
                    continue
                value = str(row[0]).strip()
                if value:
                    emails.append(value)

    return emails


def load_email_rows(path: Path | None = None) -> list[dict[str, str]]:
    """Load emails.csv rows as {email, status} (status may be empty)."""
    path = path or DEFAULT_EMAILS_PATH
    if not path.exists():
        raise FileNotFoundError(f"Email list not found: {path}")

    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return []

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if all("," not in line and _looks_like_email(line) for line in lines):
        return [{"email": line, "status": ""} for line in lines]

    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = [name.strip().lower() for name in (reader.fieldnames or [])]
        email_key = None
        status_key = None
        for candidate in ("email", "e-mail", "mail"):
            if candidate in fieldnames:
                email_key = (reader.fieldnames or [])[fieldnames.index(candidate)]
                break
        if "status" in fieldnames:
            status_key = (reader.fieldnames or [])[fieldnames.index("status")]
        if email_key is None and reader.fieldnames:
            email_key = reader.fieldnames[0]

        for row in reader:
            if not email_key:
                continue
            email = str(row.get(email_key, "")).strip()
            if not email:
                continue
            status = str(row.get(status_key, "")).strip() if status_key else ""
            rows.append({"email": email, "status": status})
    return rows


def update_email_statuses(
    updates: dict[str, str], path: Path | None = None
) -> Path:
    """Write/merge status into emails.csv (email,status)."""
    path = path or DEFAULT_EMAILS_PATH
    existing = load_email_rows(path) if path.exists() else []
    by_email = {row["email"]: row.get("status", "") for row in existing}

    for email, status in updates.items():
        by_email[email] = status

    # Preserve original order, then append any new emails
    ordered: list[str] = [row["email"] for row in existing]
    for email in updates:
        if email not in ordered:
            ordered.append(email)

    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["email", "status"])
        writer.writeheader()
        for email in ordered:
            writer.writerow({"email": email, "status": by_email.get(email, "")})
    return path


def load_email_targets(config_path: Path | None = None) -> list[AccountTarget]:
    path = config_path or DEFAULT_EMAILS_PATH
    rows = load_email_rows(path)
    if not rows:
        raise ValueError(f"No emails found in {path}. Put one email per line.")

    profile = load_shared_profile()
    targets: list[AccountTarget] = []

    for index, row in enumerate(rows, start=1):
        email = row["email"].strip()
        if not _looks_like_email(email):
            raise ValueError(f"Invalid email at line/row {index}: {email!r}")

        # Skip emails already successfully submitted unless status is failed/empty
        status = (row.get("status") or "").strip().lower()
        if status in {"submitted", "profile_complete", "cofounder_started",
                      "cofounder_agreed", "cofounder_profile_complete"}:
            continue

        targets.append(
            AccountTarget(
                email=email,
                first_name=profile["first_name"],
                last_name=profile["last_name"],
                linkedin_url=profile["linkedin_url"],
                username=None,
                password=profile["password"],
            )
        )

    return targets


def random_username(length: int = 12) -> str:
    """Generate a random username: letter start, then letters/digits."""
    length = max(6, min(length, 30))
    first = secrets.choice(string.ascii_lowercase)
    rest = "".join(
        secrets.choice(string.ascii_lowercase + string.digits)
        for _ in range(length - 1)
    )
    return first + rest


def browser_settings() -> dict:
    return {
        "headless": _env_bool("HEADLESS", default=False),
        "slow_mo": int(os.getenv("SLOW_MO", "50")),
    }
