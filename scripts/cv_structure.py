"""Optional CV presentation settings; old data keeps its original layout."""
from __future__ import annotations

import re

BUILTIN_TITLES = {
    "work": "Employment", "education": "Education", "publications": "Publications",
    "theses": "Thesis", "awards": "Grants and Awards", "presentations": "Seminars and Talks",
    "conferences": "Conferences and Research Visits", "teaching": "Teaching",
    "supervision": "Student Supervision", "skills": "Skills",
}


def layout_sections(data):
    layout = data.get("cvLayout")
    if layout is None:
        return [{"key": key, "title": title, "visible": True}
                for key, title in BUILTIN_TITLES.items()]
    return layout["sections"]


def validate_structure(data):
    customs = data.get("customSections", [])
    if not isinstance(customs, list):
        raise ValueError("customSections must be a list")
    custom_keys = set()
    ids = {record.get("id") for key in BUILTIN_TITLES for record in data.get(key, [])}
    for group in customs:
        if not isinstance(group, dict) or not isinstance(group.get("id"), str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*", group["id"]):
            raise ValueError("Custom section needs a unique alphanumeric/hyphen id")
        key = "custom:" + group["id"]
        if key in custom_keys:
            raise ValueError(f"Duplicate custom section: {key}")
        custom_keys.add(key)
        if not isinstance(group.get("items"), list):
            raise ValueError(f"{key}.items must be a list")
        for record in group["items"]:
            if not isinstance(record, dict):
                raise ValueError(f"{key}: each record must be an object")
            identifier = record.get("id")
            if not isinstance(identifier, str) or not identifier.strip() or identifier in ids:
                raise ValueError(f"{key}: missing or duplicate record id")
            ids.add(identifier)
            if not isinstance(record.get("title"), str) or not record["title"].strip():
                raise ValueError(f"{key}/{identifier}: title is required")
            for field in ("date", "organization", "description"):
                if field in record and not isinstance(record[field], str):
                    raise ValueError(f"{key}/{identifier}.{field} must be text")
    layout = data.get("cvLayout")
    if layout is None:
        if customs:
            raise ValueError("Custom sections require cvLayout.sections")
        return data
    if not isinstance(layout, dict) or not isinstance(layout.get("sections"), list):
        raise ValueError("cvLayout.sections must be a list")
    expected = set(BUILTIN_TITLES) | custom_keys
    seen = set()
    for item in layout["sections"]:
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            raise ValueError("Each CV layout entry needs a key")
        key = item["key"]
        if key not in expected or key in seen:
            raise ValueError(f"Unknown or duplicate CV section: {key}")
        seen.add(key)
        if not isinstance(item.get("title"), str) or not item["title"].strip():
            raise ValueError(f"{key}: section title is required")
        if type(item.get("visible")) is not bool:
            raise ValueError(f"{key}: visibility must be true or false")
    if seen != expected:
        raise ValueError("CV layout must include each built-in and custom section exactly once")
    return data


def visible_keys(data):
    return {item["key"] for item in layout_sections(data) if item["visible"]}
