from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .config import ROOT

DEFAULT_PROFILE_PATH = ROOT / "profile.json"

ALL_INTERESTS = [
    "Agriculture / Agtech",
    "Artificial Intelligence",
    "Augmented Reality / Virtual Reality",
    "B2B / Enterprise",
    "Biomedical / Biotech",
    "Blockchain",
    "Climate / Sustainability",
    "Consumer",
    "E-Commerce",
    "Developer Tools",
    "Education / Edtech",
    "Energy",
    "Entertainment",
    "Financial / Fintech",
    "Food / Beverage",
    "Gaming",
    "Government",
    "Hardware",
    "Hard Tech",
    "Health / Wellness",
    "Healthcare",
    "Marketplace",
    "Non-Profit",
    "Real Estate / Proptech",
    "Robotics",
    "Security",
    "Travel / Tourism",
]


@dataclass
class MoreAboutYou:
    has_startup_idea: str = "none"  # committed | open | none
    ideas: str = ""
    already_has_cofounder: bool = False
    full_time_timing: str = "passive"  # active | ready | year | passive
    responsibilities: list[str] = field(default_factory=lambda: ["Engineering"])
    interests: list[str] = field(default_factory=lambda: list(ALL_INTERESTS))
    equity_expectations: str = ""
    free_time: str = ""
    life_story: str = ""
    anything_else: str = ""


@dataclass
class CofounderPreferences:
    looking_for: str = ""
    idea_preference: str = "has_idea"  # has_idea | no_idea | no_preference
    idea_preference_importance: str = "Required"
    technical_preference: str = "non_technical"  # technical | non_technical | no_preference
    technical_preference_importance: str = "Required"
    timing_preference: str = "no_preference"  # require | prefer | no_preference
    location_preference: str = "no_preference"  # distance | country | region | no_preference
    location_preference_importance: str = "Required"
    age_preference: str = "no_preference"  # range | no_preference
    age_preference_importance: str = "Required"
    desired_responsibilities: list[str] = field(default_factory=lambda: ["Engineering"])
    desired_responsibilities_importance: str = "Required"
    shared_interests_preference: str = "no_preference"  # require | prefer | no_preference
    alert_on_match: bool = True


@dataclass
class ProfileData:
    first_name: str
    last_name: str
    linkedin_url: str
    education: str
    employment: str
    location: str
    accomplishment: str
    introduction: str
    is_technical: bool
    working_on_startup: bool
    seeking_a_cofounder: bool
    gender: str
    birthday: str  # YYYY-MM-DD
    calendly_url: str = ""
    avatar_path: Path = ROOT / "profile.png"
    video_link: str = ""
    twitter_url: str = ""
    instagram_url: str = ""
    how_heard: str = ""
    hear_about: str = ""
    more_about_you: MoreAboutYou = field(default_factory=MoreAboutYou)
    cofounder_preferences: CofounderPreferences = field(
        default_factory=CofounderPreferences
    )


def _format_education(raw) -> str:
    if isinstance(raw, list):
        return "\n".join(str(item).strip() for item in raw if str(item).strip())
    return str(raw or "").strip()


def _format_employment(raw) -> str:
    if isinstance(raw, dict):
        lines: list[str] = []
        for item in raw.values():
            if not isinstance(item, dict):
                continue
            company = str(item.get("company", "")).strip()
            title = str(item.get("title", "")).strip()
            start = str(item.get("start_date", "")).strip()
            end = str(item.get("end_date", "")).strip() or "present"
            location = str(item.get("location", "")).strip()
            parts = [p for p in (company, title, location) if p]
            dates = " - ".join(p for p in (start, end) if p)
            line = ", ".join(parts)
            if dates:
                line = f"{line}, {dates}" if line else dates
            if line:
                lines.append(line)
        return "\n".join(lines)
    if isinstance(raw, list):
        return "\n".join(str(item).strip() for item in raw if str(item).strip())
    return str(raw or "").strip()


def _format_accomplishment(data: dict) -> str:
    achievements = data.get("achievements")
    if isinstance(achievements, dict):
        lines = [str(v).strip() for v in achievements.values() if str(v).strip()]
        if lines:
            return "\n".join(lines)
    if isinstance(achievements, list):
        lines = [str(v).strip() for v in achievements if str(v).strip()]
        if lines:
            return "\n".join(lines)
    return str(data.get("introduction") or "").strip()


def _as_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_interests(raw) -> list[str]:
    if raw is None or raw == "all" or raw is True:
        return list(ALL_INTERESTS)
    if isinstance(raw, str) and raw.strip().lower() == "all":
        return list(ALL_INTERESTS)
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return list(ALL_INTERESTS)


def _parse_more_about(data: dict) -> MoreAboutYou:
    # Support both nested block and flat legacy keys
    block = data.get("more_about_you")
    src = block if isinstance(block, dict) else data

    has_idea = src.get("has_startup_idea")
    if has_idea is None:
        legacy = src.get("have_a_idea", src.get("have_an_idea"))
        if legacy is not None and not _as_bool(legacy, False):
            has_idea = "none"
        elif _as_bool(legacy, False):
            has_idea = "committed"
        else:
            has_idea = "none"

    already = src.get("already_has_cofounder")
    if already is None:
        already = src.get("already_have_a_cofounder", False)

    responsibilities = src.get("responsibilities") or ["Engineering"]
    if isinstance(responsibilities, str):
        responsibilities = [responsibilities]

    return MoreAboutYou(
        has_startup_idea=str(has_idea).strip() or "none",
        ideas=str(src.get("ideas") or "").strip(),
        already_has_cofounder=_as_bool(already, False),
        full_time_timing=str(src.get("full_time_timing") or "passive").strip(),
        responsibilities=[str(x).strip() for x in responsibilities if str(x).strip()],
        interests=_parse_interests(src.get("interests")),
        equity_expectations=str(src.get("equity_expectations") or "").strip(),
        free_time=str(src.get("free_time") or "").strip(),
        life_story=str(src.get("life_story") or "").strip(),
        anything_else=str(src.get("anything_else") or "").strip(),
    )


def _parse_preferences(data: dict) -> CofounderPreferences:
    block = data.get("cofounder_preferences")
    src = block if isinstance(block, dict) else {}
    desired = src.get("desired_responsibilities") or ["Engineering"]
    if isinstance(desired, str):
        desired = [desired]
    return CofounderPreferences(
        looking_for=str(src.get("looking_for") or "").strip(),
        idea_preference=str(src.get("idea_preference") or "has_idea").strip(),
        idea_preference_importance=str(
            src.get("idea_preference_importance") or "Required"
        ).strip(),
        technical_preference=str(
            src.get("technical_preference") or "non_technical"
        ).strip(),
        technical_preference_importance=str(
            src.get("technical_preference_importance") or "Required"
        ).strip(),
        timing_preference=str(src.get("timing_preference") or "no_preference").strip(),
        location_preference=str(
            src.get("location_preference") or "no_preference"
        ).strip(),
        location_preference_importance=str(
            src.get("location_preference_importance") or "Required"
        ).strip(),
        age_preference=str(src.get("age_preference") or "no_preference").strip(),
        age_preference_importance=str(
            src.get("age_preference_importance") or "Required"
        ).strip(),
        desired_responsibilities=[str(x).strip() for x in desired if str(x).strip()],
        desired_responsibilities_importance=str(
            src.get("desired_responsibilities_importance") or "Required"
        ).strip(),
        shared_interests_preference=str(
            src.get("shared_interests_preference") or "no_preference"
        ).strip(),
        alert_on_match=_as_bool(src.get("alert_on_match"), True),
    )


def load_profile(path: Path | None = None) -> ProfileData:
    path = path or DEFAULT_PROFILE_PATH
    if not path.exists():
        raise FileNotFoundError(f"Profile file not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    birthday = str(data.get("birthday") or data.get("birthdate") or "").strip()
    if birthday and "T" in birthday:
        birthday = birthday.split("T", 1)[0]

    avatar_raw = str(data.get("avatar") or "profile.png").strip()
    avatar_path = Path(avatar_raw)
    if not avatar_path.is_absolute():
        avatar_path = ROOT / avatar_path

    introduction = str(data.get("introduction") or "").strip()
    profile = ProfileData(
        first_name=str(data.get("first_name") or "").strip(),
        last_name=str(data.get("last_name") or "").strip(),
        linkedin_url=str(data.get("linkedin_url") or "").strip(),
        education=_format_education(data.get("education")),
        employment=_format_employment(data.get("employment")),
        location=str(data.get("location") or "").strip(),
        accomplishment=_format_accomplishment(data),
        introduction=introduction,
        is_technical=_as_bool(data.get("is_technical"), True),
        working_on_startup=_as_bool(data.get("working_on_startup"), False),
        seeking_a_cofounder=_as_bool(data.get("seeking_a_cofounder"), True),
        gender=str(data.get("gender") or "").strip(),
        birthday=birthday,
        calendly_url=str(data.get("calendly_url") or "").strip(),
        avatar_path=avatar_path,
        video_link=str(data.get("video_link") or "").strip(),
        twitter_url=str(data.get("twitter_url") or "").strip(),
        instagram_url=str(data.get("instagram_url") or "").strip(),
        how_heard=str(data.get("how_heard") or "").strip(),
        hear_about=str(data.get("hear_about") or "").strip(),
        more_about_you=_parse_more_about(data),
        cofounder_preferences=_parse_preferences(data),
    )

    missing = [
        name
        for name, value in {
            "first_name": profile.first_name,
            "last_name": profile.last_name,
            "linkedin_url": profile.linkedin_url,
            "location": profile.location,
            "accomplishment": profile.accomplishment,
            "birthday": profile.birthday,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(f"profile.json missing required fields: {', '.join(missing)}")

    return profile
