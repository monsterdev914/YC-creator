from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from .config import ROOT

DEFAULT_CREDENTIALS_PATH = ROOT / "credentials.csv"

CREDENTIAL_FIELDS = [
    "email",
    "username",
    "password",
    "first_name",
    "last_name",
    "linkedin_url",
    "status",
    "created_at",
]


@dataclass
class Credential:
    email: str
    username: str
    password: str
    first_name: str = ""
    last_name: str = ""
    linkedin_url: str = ""
    status: str = ""
    created_at: str = ""


def _read_raw_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _dedupe_by_email(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Keep the last row for each email (most recent write wins)."""
    by_email: dict[str, dict[str, str]] = {}
    order: list[str] = []
    for row in rows:
        email = (row.get("email") or "").strip()
        if not email:
            continue
        if email not in by_email:
            order.append(email)
        by_email[email] = row
    return [by_email[email] for email in order]


def _write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(CREDENTIAL_FIELDS)
    # Preserve any unexpected extra columns
    for row in rows:
        for key in row:
            if key and key not in fieldnames:
                fieldnames.append(key)

    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def find_credential(email: str, path: Path | None = None) -> dict[str, str] | None:
    """Return the stored credential row for an email, if any."""
    path = path or DEFAULT_CREDENTIALS_PATH
    needle = email.strip()
    for row in _dedupe_by_email(_read_raw_rows(path)):
        if (row.get("email") or "").strip() == needle:
            return row
    return None


def load_credentials(path: Path | None = None) -> list[Credential]:
    path = path or DEFAULT_CREDENTIALS_PATH
    if not path.exists():
        raise FileNotFoundError(f"Credentials file not found: {path}")

    rows = _dedupe_by_email(_read_raw_rows(path))
    credentials: list[Credential] = []
    for index, row in enumerate(rows, start=1):
        email = (row.get("email") or "").strip()
        username = (row.get("username") or "").strip()
        password = (row.get("password") or "").strip()
        if not email or not username or not password:
            raise ValueError(
                f"credentials.csv row {index} needs email, username, password"
            )
        credentials.append(
            Credential(
                email=email,
                username=username,
                password=password,
                first_name=(row.get("first_name") or "").strip(),
                last_name=(row.get("last_name") or "").strip(),
                linkedin_url=(row.get("linkedin_url") or "").strip(),
                status=(row.get("status") or "").strip(),
                created_at=(row.get("created_at") or "").strip(),
            )
        )

    if not credentials:
        raise ValueError(f"No credentials found in {path}")
    return credentials


def upsert_credentials(
    updates: list[dict[str, str]],
    path: Path | None = None,
) -> Path:
    """Insert or replace credentials by email (no duplicates)."""
    path = path or DEFAULT_CREDENTIALS_PATH
    rows = _dedupe_by_email(_read_raw_rows(path))
    by_email = {(row.get("email") or "").strip(): row for row in rows}
    order = [(row.get("email") or "").strip() for row in rows]

    for update in updates:
        email = (update.get("email") or "").strip()
        if not email:
            continue
        existing = by_email.get(email, {})
        merged = {**existing, **{k: v for k, v in update.items() if v is not None}}
        if email not in by_email:
            order.append(email)
        by_email[email] = merged

    _write_rows(path, [by_email[email] for email in order if email in by_email])
    return path


def dedupe_credentials_file(path: Path | None = None) -> Path:
    path = path or DEFAULT_CREDENTIALS_PATH
    rows = _dedupe_by_email(_read_raw_rows(path))
    _write_rows(path, rows)
    return path


def update_credential_status(
    email: str,
    status: str,
    path: Path | None = None,
) -> None:
    path = path or DEFAULT_CREDENTIALS_PATH
    rows = _dedupe_by_email(_read_raw_rows(path))
    updated = False
    for row in rows:
        if (row.get("email") or "").strip() == email:
            row["status"] = status
            updated = True
    if not updated:
        rows.append({"email": email, "status": status})
    _write_rows(path, rows)
