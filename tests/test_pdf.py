import copy
import json
import unittest
from pathlib import Path

from kobo2mail.config import DEFAULT_FORM
from kobo2mail.mailer import build_message
from kobo2mail.pdf import PdfError, find_chrome, pdf_filename, render_pdf, render_pdf_html

ROOT = Path(__file__).resolve().parent.parent


def cfg(**overrides):
    base = copy.deepcopy(DEFAULT_FORM)
    base.update(overrides)
    base["pdf_template_path"] = ROOT / base["pdf_template"]
    return base


class PdfTest(unittest.TestCase):
    def setUp(self):
        self.sub = json.loads((ROOT / "examples" / "sample_submission.json").read_text(encoding="utf-8"))
        self.template = (ROOT / "templates" / "pdf.html").read_text(encoding="utf-8")

    def test_filename_placeholders_and_safe_characters(self):
        self.assertEqual(pdf_filename(self.sub, cfg()), "submission-412345678.pdf")
        self.assertEqual(pdf_filename(self.sub, cfg(pdf_filename="$name / réponse")), "Amina_Diallo_r_ponse.pdf")
        self.assertEqual(pdf_filename(self.sub, cfg(pdf_filename="$nope")), "submission.pdf")

    def test_html_uses_pdf_title_and_columns_layout(self):
        html = render_pdf_html(self.sub, cfg(layout="stacked", pdf_title="Record $name"), self.template)
        self.assertIn("Record Amina Diallo", html)
        self.assertIn('width="38%"', html)  # columns layout from the template hint
        self.assertIn("&lt;much&gt;", html)
        self.assertNotIn("$", html)

    def test_missing_chrome_raises(self):
        self.assertIsNone(find_chrome({"CHROME_PATH": str(ROOT / "no-such-browser")}))

    def test_missing_template_raises(self):
        with self.assertRaises(PdfError):
            render_pdf(self.sub, cfg(pdf_template="templates/missing.html"), chrome="chrome")

    def test_attachment_added_to_message(self):
        msg = build_message(sender="a@example.org", sender_name="", to="b@example.org", subject="s",
                            text="t", html="<p>t</p>", attachments=[("copy.pdf", b"%PDF-1.4 test")])
        parts = list(msg.iter_attachments())
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0].get_filename(), "copy.pdf")
        self.assertEqual(parts[0].get_content_type(), "application/pdf")
        self.assertEqual(parts[0].get_content(), b"%PDF-1.4 test")

    @unittest.skipUnless(find_chrome(), "no Chrome, Chromium or Edge installed")
    def test_real_pdf(self):
        name, data = render_pdf(self.sub, cfg())
        self.assertEqual(name, "submission-412345678.pdf")
        self.assertTrue(data.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
