"""Regression checks for optional CV structure, including an actual PDF smoke test."""
from copy import deepcopy
from datetime import date
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import shutil

from build_cv import make_tex, build
from cv_structure import BUILTIN_TITLES, layout_sections, validate_structure
from prepare_build import ROOT, load_cv, validate_cv
from verify_build import normalized


def sample():
    data = deepcopy(load_cv(ROOT / "_data/cv.json"))
    data["customSections"] = [{"id": "service", "items": [{
        "id": "service-reviewer", "date": "2027", "title": "Journal reviewer 测试",
        "organization": "Example Society", "description": "Peer review & outreach.\nCommunity mentoring.",
    }]}]
    settings = [{"key": key, "title": title, "visible": True} for key, title in BUILTIN_TITLES.items()]
    settings[0]["visible"] = False
    settings.insert(0, {"key": "custom:service", "title": "Academic Service 学术服务", "visible": True})
    # Distinct renamed headings make PDF order and hiding observable.
    settings[1]["title"] = "Hidden Employment Sentinel"
    settings[2]["title"] = "Education Order Sentinel"
    data["cvLayout"] = {"sections": settings}
    return data


class StructureTests(unittest.TestCase):
    def test_legacy_defaults(self):
        data = deepcopy(load_cv(ROOT / "_data/cv.json"))
        data.pop("cvLayout", None)
        data.pop("customSections", None)
        self.assertEqual([s["key"] for s in layout_sections(data)], list(BUILTIN_TITLES))
        validate_structure(data)

    def test_render_order_hide_and_plain_text(self):
        data = sample()
        validate_cv(data)
        tex = make_tex(data, date(2026, 10, 5), ROOT / "templates/cv.tex")
        self.assertLess(tex.index(r"\cvsection{Academic Service 学术服务}"), tex.index(r"\cvsection{Education Order Sentinel}"))
        self.assertNotIn("Hidden Employment Sentinel", tex)
        self.assertNotIn("Senior Engineer", tex)
        self.assertIn(r"Peer review \& outreach.", tex)
        self.assertNotIn(r"\href", tex)
        self.assertNotIn("pandamology.github.io", tex)
        hidden = deepcopy(data)
        hidden["cvLayout"]["sections"][0]["visible"] = False
        hidden_tex = make_tex(hidden, date(2026, 10, 5), ROOT / "templates/cv.tex")
        self.assertNotIn("Journal reviewer", hidden_tex)
        self.assertEqual(len(hidden["customSections"][0]["items"]), 1)

    def test_invalid_structure_rejected(self):
        for mutation in (lambda d: d["cvLayout"]["sections"].pop(),
                         lambda d: d["cvLayout"]["sections"].append(d["cvLayout"]["sections"][0]),
                         lambda d: d["cvLayout"]["sections"][0].update(visible="false"),
                         lambda d: d["customSections"][0]["items"][0].update(title="")):
            data = sample()
            mutation(data)
            with self.assertRaises(ValueError):
                validate_structure(data)


def compile_smoke_pdf():
    data = sample()
    tex = make_tex(data, date(2026, 10, 5), ROOT / "templates/cv.tex")
    with tempfile.TemporaryDirectory(prefix="cv-structure-test-") as directory:
        output = Path(directory) / "CV.pdf"
        build(tex, output, None)
        content = subprocess.check_output(["pdftotext", "-enc", "UTF-8", str(output), "-"], text=True)
        assert "Hidden Employment Sentinel" not in content
        assert "学术服务" in normalized(content) and "测试" in normalized(content)
        assert content.index("Academic Service") < content.index("Education Order Sentinel")
        assert "Community mentoring." in content
        urls = subprocess.check_output(["pdfinfo", "-url", str(output)], text=True)
        assert "https://" not in urls and "mailto:" not in urls
        preview = ROOT / "build/structure-preview.pdf"
        preview.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(output, preview)
    print("Custom-section PDF compiled: headings ordered, hidden content absent, Chinese rendered, no links.")


if __name__ == "__main__":
    smoke = "--compile-pdf" in sys.argv
    if smoke:
        sys.argv.remove("--compile-pdf")
    result = unittest.main(exit=False)
    if not result.result.wasSuccessful():
        sys.exit(1)
    if smoke:
        compile_smoke_pdf()
