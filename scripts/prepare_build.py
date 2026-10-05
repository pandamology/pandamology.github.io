#!/usr/bin/env python3
"""Validate the shared CV and derive Jekyll metadata from the same records."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from cv_structure import validate_structure

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = (
    "work", "education", "publications", "theses", "awards", "presentations",
    "conferences", "teaching", "supervision", "skills",
)
REQUIRED = {
    "work": ("id", "position", "organization", "startDate"),
    "education": ("id", "degree", "area", "institution", "endDate", "supervisorRole"),
    "publications": ("id", "title", "status"),
    "theses": ("id", "title", "url"),
    "awards": ("id", "title", "date"),
    "presentations": ("id", "title", "event", "date", "status"),
    "conferences": ("id", "title", "date"),
    "teaching": ("id", "course", "institution", "role", "date"),
    "supervision": ("id", "role", "organization", "date"),
    "skills": ("name",),
}


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key!r}")
        result[key] = value
    return result


def date_value(value: str, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}(?:-\d{2})?(?:-\d{2})?", value):
        raise ValueError(f"{label}: use YYYY, YYYY-MM, or YYYY-MM-DD")
    parts = [int(part) for part in value.split("-")]
    dt.date(*(parts + [1] * (3 - len(parts))))
    return value


def require_text(record, field, label):
    if not isinstance(record.get(field), str) or not record[field].strip():
        raise ValueError(f"{label}.{field}: a non-empty text value is required")


def validate_cv(data):
    if not isinstance(data, dict) or data.get("schemaVersion") != 1:
        raise ValueError("The CV must be a JSON object with schemaVersion: 1")
    basics = data.get("basics", {})
    for field in ("name", "email", "institutionalEmail", "website", "orcid", "avatar"):
        require_text(basics, field, "basics")
    for field in ("email", "institutionalEmail"):
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", basics[field]):
            raise ValueError(f"basics.{field}: enter a valid email address")
    if not re.fullmatch(r"\d{4}-\d{4}-\d{4}-[\dX]{4}", basics["orcid"]):
        raise ValueError("basics.orcid: use the 0000-0000-0000-0000 identifier format")
    profile = data.get("profile", {})
    for field in ("researchInterests", "industrySummary", "researchArea"):
        require_text(profile, field, "profile")
    for section in SECTIONS:
        records = data.get(section)
        if not isinstance(records, list):
            raise ValueError(f"{section}: expected a list (use [] for an empty section)")
        identifiers = set()
        for index, record in enumerate(records):
            label = f"{section}[{index}]"
            if not isinstance(record, dict):
                raise ValueError(f"{label}: expected an object")
            for field in REQUIRED[section]:
                require_text(record, field, label)
            identifier = record.get("id", record.get("name"))
            if identifier in identifiers:
                raise ValueError(f"{label}: repeated id {identifier!r}")
            identifiers.add(identifier)
            for field in ("date", "startDate", "endDate"):
                if record.get(field):
                    date_value(record[field], f"{label}.{field}")
            if section in ("awards", "presentations", "teaching") and not isinstance(record.get("homepage"), bool):
                raise ValueError(f"{label}.homepage: use true or false")
            if section in ("publications", "theses"):
                year = record.get("year")
                if type(year) is not int or not 1000 <= year <= 9999:
                    raise ValueError(f"{label}.year: use a four-digit number")
            if section == "publications":
                if record["status"] not in ("preprint", "accepted", "published"):
                    raise ValueError(f"{label}.status: use preprint, accepted, or published")
                if record["status"] in ("accepted", "published") and not record.get("journal"):
                    raise ValueError(f"{label}.journal: required for accepted/published papers")
                if not record.get("authors") or not isinstance(record["authors"], list):
                    raise ValueError(f"{label}.authors: an ordered author list is required")
                for author in record["authors"]:
                    require_text(author, "name", f"{label}.authors")
            if section == "presentations" and record["status"] not in ("past", "upcoming"):
                raise ValueError(f"{label}.status: use past or upcoming")
            if section == "education":
                if not isinstance(record.get("supervisors"), list):
                    raise ValueError(f"{label}.supervisors: expected a list")
                for supervisor in record["supervisors"]:
                    require_text(supervisor, "name", f"{label}.supervisors")
            if section == "skills" and (not isinstance(record.get("items"), list) or
                    not all(isinstance(item, str) and item.strip() for item in record["items"])):
                raise ValueError(f"{label}.items: expected a list of non-empty text values")
    if not data["work"] or not data["education"]:
        raise ValueError("Employment and education must not be empty")

    def check_links(value, label="cv"):
        if isinstance(value, dict):
            for key, item in value.items():
                if key.lower().endswith("url") or key in ("website", "googleScholar", "arxiv"):
                    if isinstance(item, str) and item and (key != "arxiv" or "://" in item):
                        parsed = urlsplit(item)
                        if parsed.scheme not in ("https", "http") or not parsed.netloc:
                            raise ValueError(f"{label}.{key}: use a full https:// or http:// URL")
                check_links(item, f"{label}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                check_links(item, f"{label}[{index}]")

    check_links(data)
    return validate_structure(data)


def load_cv(path: Path):
    return validate_cv(json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys))


def source_date(path: Path) -> str:
    result = subprocess.run(
        ["git", "log", "-1", "--format=%cs", "--", str(path.resolve())],
        cwd=ROOT, text=True, capture_output=True, check=True,
    )
    value = result.stdout.strip()
    if not value:
        raise ValueError("No source commit date available; pass --updated YYYY-MM-DD")
    dt.date.fromisoformat(value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "_data/cv.json")
    parser.add_argument("--output", type=Path, default=ROOT / "build/cv-config.yml")
    parser.add_argument("--updated", help="Override the data's last Git commit date for a local preview")
    parser.add_argument("--as-of", help="Override the build's calendar date for a reproducible preview")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    data = load_cv(args.data)
    print("CV data valid: " + ", ".join(f"{len(data[key])} {key}" for key in SECTIONS))
    if args.validate_only:
        return
    updated = args.updated or source_date(args.data)
    dt.date.fromisoformat(updated)
    as_of = args.as_of or dt.datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    dt.date.fromisoformat(as_of)
    basics = data["basics"]
    current = next((job for job in data["work"] if not job.get("endDate")), data["work"][0])
    config = {
        "name": basics["name"],
        "title": basics["name"],
        "description": f"{basics['name']} | {current['position']} | {data['profile']['researchArea']}",
        "cv_updated": updated,
        "cv_as_of": as_of,
        "cv_data_sha256": hashlib.sha256(args.data.read_bytes()).hexdigest(),
        "author": {
            "name": basics["name"], "avatar": basics["avatar"],
            "email": basics["institutionalEmail"], "uri": basics["website"],
            "orcid": "https://orcid.org/" + basics["orcid"],
            "github": basics.get("github", ""),
            "googlescholar": basics.get("googleScholar", ""),
            "arxiv": basics.get("arxiv", ""),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Generated {args.output}; CV updated {updated}")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        print(f"CV validation failed: {exc}", file=sys.stderr)
        sys.exit(1)
