#!/usr/bin/env python3
"""Build the downloadable CV from the same JSON used by Jekyll.

Requires Python 3.10+ and XeLaTeX with the packages in templates/cv.tex;
there are no third-party Python dependencies. Example (from the repository):

    python3 scripts/build_cv.py --updated 2026-10-05 \
        --output build/CV.pdf --tex-output build/CV.tex

The date is explicit so that a rebuild cannot silently change the CV's
last-updated date. --as-of separately controls whether talks are upcoming;
it defaults to --updated and should match the website's cv_as_of setting.
Data strings are escaped as text; the only supported
inline mathematics is a single Latin letter with an optional subscript or
superscript, such as $T^i$. Add richer math deliberately in the renderer.
"""

from __future__ import annotations

import argparse
import calendar
from datetime import date
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from cv_structure import BUILTIN_TITLES, layout_sections, validate_structure


ROOT = Path(__file__).resolve().parents[1]
SECTIONS = (
    "work", "education", "publications", "theses", "awards",
    "presentations", "conferences", "teaching", "supervision", "skills",
)
ESCAPES = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
    "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}
MATH = re.compile(r"\$([A-Za-z](?:[_^](?:[A-Za-z0-9]|\{[A-Za-z0-9]+\})){0,2})\$")


def text(value: object) -> str:
    """Escape literal text, including characters that would execute TeX."""
    if value is None:
        return ""
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise ValueError(f"Expected text or an integer, got {type(value).__name__}")
    value = str(value).replace("\u00a0", " ")
    value = re.sub(r"[\r\n\t]+", " ", value)
    # Keep source ASCII for punctuation; let TeX supply typographic dashes.
    value = value.replace("\u2013", "--").replace("\u2014", "---")
    value = value.replace("\u2011", "-").replace("\u2212", "-")
    return "".join(ESCAPES.get(char, char) for char in value)


def title(value: str) -> str:
    """Preserve narrowly defined inline math without accepting raw LaTeX."""
    parts = []
    end = 0
    for match in MATH.finditer(value):
        parts.extend((text(value[end:match.start()]), "$" + match[1] + "$"))
        end = match.end()
    parts.append(text(value[end:]))
    return "".join(parts)


def link(url: str | None, label: str, *, rendered: bool = False) -> str:
    """Render PDF labels as plain text, with no clickable links."""
    return label if rendered else text(label)


def emphasis(value: str) -> str:
    return r"\textit{" + title(value) + "}"


def detail(value: str) -> str:
    return r"\cvdetail{" + value + "}"


def display_date(value: object) -> str:
    if value in (None, "", "present"):
        return "present"
    value = str(value)
    if re.fullmatch(r"\d{4}", value):
        return value
    if re.fullmatch(r"\d{4}-\d{2}", value):
        year, month = (int(part) for part in value.split("-"))
        if not 1 <= month <= 12:
            raise ValueError(f"Invalid month in date: {value}")
        return f"{calendar.month_abbr[month]} {year}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        parsed = date.fromisoformat(value)
        return f"{parsed.day} {calendar.month_abbr[parsed.month]} {parsed.year}"
    raise ValueError(f"Dates must be YYYY, YYYY-MM, YYYY-MM-DD, or present: {value!r}")


def date_range(start: object, end: object) -> str:
    if not start or str(start) == str(end):
        return text(display_date(end))
    return text(display_date(start)) + " -- " + text(display_date(end))


def dated_entry(entry: dict) -> str:
    return date_range(entry.get("startDate"), entry["date"])


def sentence(parts: list[str], separator: str = ", ") -> str:
    result = separator.join(part.rstrip(".") for part in parts if part)
    return result + "." if result else ""


def row(when: str, body: str) -> str:
    return "\\cvrow{" + when + "}{" + body + "}\n"


def section(name: str, items: list[str]) -> str:
    return "\\cvsection{" + name + "}\n" + "".join(items) if items else ""


def people(authors: list[dict]) -> str:
    # Keep the source's exact author order, including the CV owner's name.
    names = [link(author.get("url"), author["name"]) for author in authors]
    if len(names) > 1:
        return ", ".join(names[:-1]) + " and " + names[-1]
    return "".join(names)


def render_publications(publications: list[dict]) -> str:
    result = []
    groups = (
        ("Published and accepted papers", {"published", "accepted"}),
        ("Preprints", {"preprint"}),
    )
    for label, statuses in groups:
        entries = [entry for entry in publications if entry["status"] in statuses]
        if not entries:
            continue
        result.append(r"\cvsubsection{" + label + "}\n" + r"\begin{cvpapers}" + "\n")
        for entry in entries:
            parts = [link(entry.get("url"), emphasis(entry["title"]), rendered=True)]
            parts.append(people(entry["authors"]))
            if entry.get("journal"):
                journal = text(entry["journal"])
                if entry["status"] == "accepted":
                    journal += " (accepted)"
                parts.append(journal)
            elif entry["status"] == "accepted":
                parts.append("Accepted for publication")
            parts.append(text(entry["year"]))
            if entry.get("arxiv"):
                arxiv = entry["arxiv"]
                parts.append(link("https://arxiv.org/abs/" + arxiv, "arXiv:" + arxiv))
            if entry.get("note"):
                parts.append(text(entry["note"]))
            result.append("\\item " + sentence(parts, ". ") + "\n")
        result.append("\\end{cvpapers}\n")
    return section("Publications", result)


def presentation_upcoming(entry: dict, as_of: str) -> bool:
    """Match the HTML rule without inventing a day for partial dates.

    A future year/month/day is upcoming even if its stored status is stale.
    During the recorded period, use the stored status; after it, it is past.
    """
    when = str(entry["date"])
    current_period = as_of[:len(when)]
    return when > current_period or (
        when == current_period and entry.get("status") == "upcoming"
    )


def render_sections(data: dict, as_of: str) -> str:
    sections = []

    entries = []
    for entry in data["work"]:
        organization = entry["organization"]
        short = entry.get("organizationShort")
        if short and short not in organization:
            organization += " (" + short + ")"
        body = sentence([
            emphasis(entry["position"]), text(entry.get("department", "")),
            link(entry.get("url"), organization),
        ])
        if entry.get("summary"):
            body += detail(text(entry["summary"]))
        entries.append(row(date_range(entry["startDate"], entry["endDate"]), body))
    sections.append(section("Employment", entries))

    entries = []
    for entry in data["education"]:
        degree = entry["degree"] + (" in " + entry["area"] if entry.get("area") else "")
        body = sentence([emphasis(degree), link(entry.get("url"), entry["institution"])])
        if entry.get("program"):
            body += detail(text(entry["program"]))
        if entry.get("department"):
            body += detail(link(entry.get("departmentUrl"), entry["department"]))
        if entry.get("supervisors"):
            label = entry.get("supervisorRole") or ("Supervisors" if len(entry["supervisors"]) > 1 else "Supervisor")
            body += detail(text(label) + ": " + people(entry["supervisors"]) + ".")
        if entry.get("thesisHost"):
            body += detail("Thesis host: " + link(entry.get("thesisHostUrl"), entry["thesisHost"]) + ".")
        entries.append(row(text(display_date(entry["endDate"])), body))
    sections.append(section("Education", entries))

    sections.append(render_publications(data["publications"]))
    sections.append(section("Thesis", [
        row(text(entry["year"]), link(entry.get("url"), emphasis(entry["title"]), rendered=True) + ".")
        for entry in data["theses"]
    ]))
    sections.append(section("Grants and Awards", [
        row(dated_entry(entry), sentence([text(entry["title"]), text(entry.get("organization", ""))]))
        for entry in data["awards"]
    ]))
    entries = []
    for entry in data["presentations"]:
        body = sentence([emphasis(entry["title"]), text(entry["event"]), text(entry.get("location", ""))])
        if presentation_upcoming(entry, as_of):
            body += " (Upcoming.)"
        entries.append(row(text(display_date(entry["date"])), body))
    sections.append(section("Seminars and Talks", entries))
    entries = []
    for entry in data["conferences"]:
        conference_title = emphasis(entry["title"])
        note = entry.get("note", "")
        if note.lower() in {"annually", "regularly"}:
            conference_title += " (" + text(note.lower()) + ")"
            note = ""
        body = sentence([conference_title, text(entry.get("location", ""))])
        if note:
            body += " " + text(note.rstrip(".")) + "."
        entries.append(row(dated_entry(entry), body))
    sections.append(section("Conferences and Research Visits", entries))
    entries = []
    for entry in data["teaching"]:
        body = sentence([emphasis(entry["course"]), text(entry["role"]), text(entry["institution"])])
        when = dated_entry(entry)
        if entry.get("term"):
            when = text(entry["term"]) + " " + when
        entries.append(row(when, body))
    sections.append(section("Teaching", entries))
    sections.append(section("Student Supervision", [
        row(dated_entry(entry), sentence([text(entry["role"]), text(entry["organization"])]))
        for entry in data["supervision"]
    ]))
    sections.append(section("Skills", [
        row(text(entry["name"]), sentence([text(item) for item in entry["items"]], "; "))
        for entry in data["skills"]
    ]))
    rendered = dict(zip(BUILTIN_TITLES, sections))
    customs = {"custom:" + group["id"]: group for group in data.get("customSections", [])}
    ordered = []
    for setting in layout_sections(data):
        if not setting["visible"]:
            continue
        key = setting["key"]
        if key in rendered:
            body = rendered[key]
            heading = "\\cvsection{" + BUILTIN_TITLES[key] + "}"
            body = body.replace(heading, "\\cvsection{" + text(setting["title"]) + "}", 1)
        else:
            entries = []
            for entry in customs[key]["items"]:
                body = sentence([emphasis(entry["title"]), text(entry.get("organization", ""))])
                for line in entry.get("description", "").splitlines():
                    if line.strip():
                        body += detail(text(line))
                entries.append(row(text(entry.get("date", "")), body))
            body = section(text(setting["title"]), entries)
        if body:
            ordered.append(body)
    return "\n".join(ordered)


def load_data(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, dict) or data.get("schemaVersion") != 1:
        raise ValueError("Expected the shared CV schemaVersion 1")
    # Reject absent sections instead of successfully generating an incomplete CV.
    for name in SECTIONS:
        if name not in data or not isinstance(data[name], list):
            raise ValueError(f"Missing or invalid CV section: {name}")
        if any(not isinstance(entry, dict) for entry in data[name]):
            raise ValueError(f"Every {name} entry must be an object")
    for name in ("basics", "profile"):
        if not isinstance(data.get(name), dict):
            raise ValueError(f"Missing or invalid CV object: {name}")
    for name in ("name", "email", "website", "orcid"):
        if not isinstance(data["basics"].get(name), str) or not data["basics"][name]:
            raise ValueError(f"Missing basics.{name}")
    for publication in data["publications"]:
        if publication.get("status") not in {"published", "accepted", "preprint"}:
            raise ValueError(f"Unknown publication status: {publication.get('status')!r}")
        if not publication.get("authors"):
            raise ValueError(f"A publication needs an ordered author list: {publication.get('id')}")
    return validate_structure(data)


def make_tex(data: dict, updated: date, template: Path, as_of: date | None = None) -> str:
    basics = data["basics"]
    orcid = basics["orcid"].removeprefix("https://orcid.org/").rstrip("/")
    contact = "Email: " + link("mailto:" + basics["email"], basics["email"])
    contact += r"\qquad ORCID: " + link("https://orcid.org/" + orcid, orcid)
    replacements = {
        "NAME": text(basics["name"]),
        "PDF_TITLE": text(basics["name"] + " - Curriculum Vitae"),
        "CONTACT": contact,
        "SECTIONS": render_sections(data, (as_of or updated).isoformat()),
        "UPDATED": f"{calendar.month_name[updated.month]} {updated.day}, {updated.year}",
    }
    source = template.read_text(encoding="utf-8")
    def replace(match: re.Match) -> str:
        key = match[1]
        if key not in replacements:
            raise ValueError(f"Unknown template marker: {key}")
        return replacements[key]
    rendered = re.sub(r"@@([A-Z_]+)@@", replace, source)
    if "@@" in rendered:
        raise ValueError("An unresolved template marker remains")
    return rendered


def atomic_write(destination: Path, content: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(content)
    try:
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def build(tex: str, output: Path, tex_output: Path | None) -> None:
    compiler = shutil.which("xelatex")
    if not compiler:
        raise RuntimeError("XeLaTeX is required. Install TeX Live with texlive-xetex and texlive-latex-extra, or MacTeX.")
    with tempfile.TemporaryDirectory(prefix="cv-build-") as directory:
        work = Path(directory)
        (work / "CV.tex").write_text(tex, encoding="utf-8")
        command = [compiler, "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error", "CV.tex"]
        for _ in range(2):
            result = subprocess.run(command, cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if result.returncode:
                raise RuntimeError("XeLaTeX failed; the existing PDF was left untouched.\n" + result.stdout[-8000:] + result.stderr[-1000:])
        log = (work / "CV.log").read_text(encoding="utf-8", errors="replace")
        defects = re.findall(r"(?:Missing character:|Overfull \\[hv]box)[^\n]*", log)
        if defects:
            raise RuntimeError("CV layout or font validation failed; the existing PDF was left untouched.\n" + "\n".join(defects))
        pdf = (work / "CV.pdf").read_bytes()
        if not pdf.startswith(b"%PDF-") or len(pdf) < 1000:
            raise RuntimeError("XeLaTeX did not produce a valid nonempty PDF")
        if tex_output is not None:
            atomic_write(tex_output, tex.encode("utf-8"))
        atomic_write(output, pdf)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=ROOT / "_data/cv.json")
    parser.add_argument("--output", type=Path, default=ROOT / "build/CV.pdf")
    parser.add_argument("--tex-output", type=Path, help="Also save the generated, standalone LaTeX source")
    parser.add_argument("--updated", required=True, type=date.fromisoformat, metavar="YYYY-MM-DD", help="Explicit content update date shown in the PDF")
    parser.add_argument("--as-of", type=date.fromisoformat, metavar="YYYY-MM-DD", help="Date used to classify talks; defaults to --updated and must match the website build")
    args = parser.parse_args()
    if args.tex_output and args.tex_output.resolve() == args.output.resolve():
        parser.error("--output and --tex-output must be different files")
    if args.data.resolve() in {args.output.resolve(), args.tex_output.resolve() if args.tex_output else None}:
        parser.error("Generated output must not overwrite the input data")
    try:
        data = load_data(args.data)
        tex = make_tex(data, args.updated, ROOT / "templates/cv.tex", args.as_of)
        build(tex, args.output, args.tex_output)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        print(f"CV build failed: {error}", file=sys.stderr)
        return 1
    counts = ", ".join(f"{len(data[name])} {name}" for name in SECTIONS)
    print(f"Built {args.output} ({counts})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
