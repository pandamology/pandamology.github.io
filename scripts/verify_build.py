#!/usr/bin/env python3
"""Check that the deployed pages and PDF contain the shared CV records."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import sys
import unicodedata

from prepare_build import ROOT, SECTIONS, load_cv
from cv_structure import visible_keys, layout_sections


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.record_ids = []
        self.links = []
        self.pdf_previews = []
        self.data_hashes = []
        self.words = []
        self.hidden_depth = 0
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "style"):
            self.hidden_depth += 1
        if "data-cv-id" in attrs:
            self.record_ids.append(attrs["data-cv-id"])
        if "data-cv-sha256" in attrs:
            self.data_hashes.append(attrs["data-cv-sha256"])
        if tag == "iframe" and attrs.get("src"):
            self.pdf_previews.append(attrs["src"])
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden_depth = max(0, self.hidden_depth - 1)

    def handle_data(self, data):
        if not self.hidden_depth:
            self.words.append(data)


def normalized(text):
    # Ignore layout-only line wrapping, hyphenation, math delimiters and ligatures.
    text = unicodedata.normalize("NFKC", str(text)).casefold()
    return re.sub(r"[\W_]+", "", text)


def expect(condition, message):
    if not condition:
        raise ValueError(message)


def check_ids(page, records, label):
    expected = Counter(record["id"] for record in records)
    actual = Counter(page.record_ids)
    expect(actual == expected,
           f"{label}: record mismatch; missing {dict(expected - actual)}, unexpected {dict(actual - expected)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "_data/cv.json")
    parser.add_argument("--site", type=Path, default=ROOT / "_site")
    parser.add_argument("--pdf", type=Path)
    args = parser.parse_args()
    data = load_cv(args.data)
    pdf = args.pdf or args.site / "files/CV.pdf"
    records = [record for section in SECTIONS if section != "skills" for record in data[section]]
    pages = {}
    for name in ("cv", "publications", "talks", "teaching"):
        filename = args.site / name / "index.html"
        expect(filename.is_file(), f"Missing page: {filename}")
        pages[name] = Page(filename.read_text(encoding="utf-8"))
    expect(pages["cv"].pdf_previews == ["/files/CV.pdf"], "CV page must embed the canonical PDF preview")
    expect(not pages["cv"].record_ids, "CV page must show the PDF instead of an HTML record list")
    check_ids(pages["publications"], data["publications"] + data["theses"], "Publications page")
    check_ids(pages["talks"], [row for row in data["presentations"] if row.get("homepage", True)], "Talks page")
    check_ids(pages["teaching"], [row for row in data["teaching"] if row.get("homepage", True)], "Teaching page")
    expected_hash = hashlib.sha256(args.data.read_bytes()).hexdigest()
    expect(expected_hash in pages["cv"].data_hashes, "CV page was built from a different data version")
    expect("/files/CV.pdf" in pages["cv"].links, "CV download must use the canonical /files/CV.pdf link")
    expect(pdf.is_file() and pdf.read_bytes().startswith(b"%PDF-"), "Missing or invalid generated PDF")
    expect(pdf.stat().st_size > 5000, "Generated PDF is unexpectedly small")
    result = subprocess.run(["pdftotext", "-enc", "UTF-8", str(pdf), "-"], capture_output=True, text=True, check=True)
    pdf_text = normalized(result.stdout)
    domain = data["basics"]["website"].removeprefix("https://").removeprefix("http://").rstrip("/")
    expect(normalized(domain) not in pdf_text, "PDF must not display the personal domain")
    urls = subprocess.run(["pdfinfo", "-url", str(pdf)], capture_output=True, text=True, check=True)
    expect(not re.search(r"(?:https?://|mailto:)", urls.stdout), "PDF must not contain hyperlink annotations")
    expect(normalized(data["basics"]["name"]) in pdf_text, "PDF is missing the owner's name")
    expect(normalized(data["basics"]["email"]) in pdf_text, "PDF is missing the contact email")
    text_keys = {
        "work": ("position", "organization"), "education": ("degree", "institution"),
        "publications": ("title",), "theses": ("title",), "awards": ("title",),
        "presentations": ("title",), "conferences": ("title",),
        "teaching": ("course",), "supervision": ("organization",),
    }
    visible = visible_keys(data)
    for section, keys in text_keys.items():
        if section not in visible:
            continue
        for record in data[section]:
            for key in keys:
                expect(normalized(record[key]) in pdf_text, f"PDF is missing {section}/{record['id']}: {key}")
            if section == "publications":
                for author in record["authors"]:
                    expect(normalized(author["name"]) in pdf_text,
                           f"PDF is missing an author for {record['id']}")
                if record.get("arxiv"):
                    expect(normalized(record["arxiv"]) in pdf_text, f"PDF is missing arXiv identifier for {record['id']}")
    for group in data["skills"] if "skills" in visible else []:
        for item in group["items"]:
            expect(normalized(item) in pdf_text, f"PDF is missing skill {item!r}")
    for group in data.get("customSections", []):
        if "custom:" + group["id"] not in visible:
            continue
        for record in group["items"]:
            for field in ("title", "date", "organization", "description"):
                value = record.get(field, "")
                if value:
                    expect(normalized(value) in pdf_text, f"PDF is missing custom section {group['id']}: {field}")
    populated = {key for key in SECTIONS if data[key]}
    populated |= {"custom:" + group["id"] for group in data.get("customSections", []) if group["items"]}
    for setting in layout_sections(data):
        if setting["visible"] and setting["key"] in populated:
            expect(normalized(setting["title"]) in pdf_text, f"PDF is missing section heading {setting['title']!r}")
    source_page = (args.site / "index.html").read_text(encoding="utf-8")
    expect(normalized(data["profile"]["researchInterests"]) in normalized(" ".join(Page(source_page).words)),
           "Homepage research statement differs from the shared data")
    expect("Your Sidebar Name" not in " ".join(pages["cv"].words), "Template placeholder found in CV")
    print(f"Verified {len(records)} CV records, all list pages, metadata and PDF contents.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Website/PDF verification failed: {exc}", file=sys.stderr)
        sys.exit(1)
