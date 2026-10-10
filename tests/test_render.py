import copy
import json
import unittest
from pathlib import Path

from kobo2mail.config import DEFAULT_FORM
from kobo2mail.mailer import build_message
from kobo2mail.render import placeholder_values, render_email, tint

ROOT = Path(__file__).resolve().parent.parent


def cfg(**overrides):
    base = copy.deepcopy(DEFAULT_FORM)
    base.update(overrides)
    return base


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.template = (ROOT / "templates" / "default.html").read_text(encoding="utf-8")
        self.sub = json.loads((ROOT / "examples" / "sample_submission.json").read_text(encoding="utf-8"))

    def test_placeholders(self):
        values = placeholder_values(self.sub, cfg())
        self.assertEqual(values["contact__name"], "Amina Diallo")
        self.assertEqual(values["name"], "Amina Diallo")
        self.assertEqual(values["submission_id"], "412345678")
        self.assertEqual(values["submitted_at"], "10 Oct 2026, 09:15 UTC")

    def test_subject_unknown_placeholder_is_blank(self):
        subject, _, _ = render_email(self.sub, cfg(subject="Hi $name $nope!"), self.template)
        self.assertEqual(subject, "Hi Amina Diallo !")

    def test_html_is_escaped_and_complete(self):
        _, html, text = render_email(self.sub, cfg(), self.template)
        self.assertIn("&lt;much&gt; better now &amp; we&#x27;re happy", html)
        self.assertNotIn("<much>", html)
        self.assertNotIn("$", html)
        self.assertIn("Household 1", html)
        self.assertIn("<much>", text)

    def test_title_placeholder_escaped(self):
        sub = dict(self.sub, **{"contact/name": "<b>Bob</b>"})
        _, html, _ = render_email(sub, cfg(title="Thanks $name"), self.template)
        self.assertIn("Thanks &lt;b&gt;Bob&lt;/b&gt;", html)

    def test_layout_hint_and_override(self):
        hinted = "<!-- kobo2mail: layout=columns -->$answers_table"
        _, html, _ = render_email(self.sub, cfg(), hinted)
        self.assertIn('width="38%"', html)
        _, html, _ = render_email(self.sub, cfg(layout="stacked"), hinted)
        self.assertNotIn('width="38%"', html)

    def test_tint(self):
        self.assertEqual(tint("#000000", 0.5), "#808080")
        self.assertEqual(tint("#fff"), "#ffffff")
        self.assertEqual(tint("not-a-color"), "#f7fafc")

    def test_button_and_vars(self):
        c = cfg(button_label="Call $org", button_url="https://x.org/?id=$submission_id",
                vars={"org": "ACME"})
        _, html, text = render_email(self.sub, c, "$button_block")
        self.assertIn('href="https://x.org/?id=412345678"', html)
        self.assertIn("Call ACME", html)
        self.assertIn("Call ACME: https://x.org/?id=412345678", text)

    def test_button_rejects_unsafe_url(self):
        c = cfg(button_label="Go", button_url="javascript:alert(1)")
        _, html, _ = render_email(self.sub, c, "$button_block")
        self.assertEqual(html, "")

    def test_all_templates_fully_substituted(self):
        c = cfg(button_label="Go", button_url="https://x.org")
        for path in sorted((ROOT / "templates").glob("*.html")):
            _, html, _ = render_email(self.sub, c, path.read_text(encoding="utf-8"))
            self.assertNotIn("$", html, path.name)
            self.assertIn("Household 2", html, path.name)

    def test_message_parts(self):
        subject, html, text = render_email(self.sub, cfg(), self.template)
        msg = build_message(sender="me@x.org", sender_name="Team", to="a@b.org",
                            subject=subject, text=text, html=html, bcc="archive@x.org")
        self.assertEqual(msg.get_content_type(), "multipart/alternative")
        self.assertEqual([p.get_content_type() for p in msg.iter_parts()], ["text/plain", "text/html"])
        self.assertEqual(msg["From"], "Team <me@x.org>")


if __name__ == "__main__":
    unittest.main()
