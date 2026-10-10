import copy
import unittest

from kobo2mail.config import DEFAULT_FORM
from kobo2mail.fields import build_entries, find_recipient, format_value, humanize


def cfg(**overrides):
    base = copy.deepcopy(DEFAULT_FORM)
    base.update(overrides)
    return base


class HumanizeTest(unittest.TestCase):
    def test_last_segment(self):
        self.assertEqual(humanize("contact/phone_number"), "Phone number")
        self.assertEqual(humanize("first-name"), "First name")


class FormatValueTest(unittest.TestCase):
    def test_select_multiple_mapped(self):
        c = cfg(value_labels={"services": {"water": "Water point", "health": "Clinic"}})
        self.assertEqual(format_value("grp/services", "water health", c), "Water point, Clinic")

    def test_unmapped_choice_is_humanized(self):
        c = cfg(value_labels={"services": {"water": "Water point"}})
        self.assertEqual(format_value("services", "water new_school", c), "Water point, New school")

    def test_free_text_untouched(self):
        self.assertEqual(format_value("comments", "  keep_this as-is ", cfg()), "keep_this as-is")

    def test_none_and_bool(self):
        self.assertEqual(format_value("x", None, cfg()), "")
        self.assertEqual(format_value("x", True, cfg()), "Yes")


class FindRecipientTest(unittest.TestCase):
    def test_configured_field(self):
        self.assertEqual(find_recipient({"c/email": " a@b.org "}, "c/email"), "a@b.org")

    def test_invalid_address(self):
        self.assertIsNone(find_recipient({"email": "not an email"}, "email"))
        self.assertIsNone(find_recipient({"email": "a@b"}, "email"))

    def test_missing_field(self):
        self.assertIsNone(find_recipient({"other": "a@b.org"}, "email"))

    def test_autodetect(self):
        sub = {"name": "x", "respondent/e_mail": "x@y.com"}
        self.assertEqual(find_recipient(sub), "x@y.com")
        self.assertIsNone(find_recipient({"emailing_list": "x@y.com"}))


class BuildEntriesTest(unittest.TestCase):
    SUB = {
        "_id": 1,
        "start": "t",
        "contact/name": "Amina",
        "contact/email": "a@b.org",
        "age": "",
        "household": [
            {"household/member_name": "Moussa", "household/_index": "1"},
            {"household/member_name": ""},
        ],
        "meta/instanceID": "uuid:1",
    }

    def test_default_excludes_metadata_and_empty(self):
        entries = build_entries(self.SUB, cfg(group_headers=False))
        paths = [e["path"] for e in entries]
        self.assertEqual(paths, ["contact/name", "contact/email", "household"])

    def test_exclude_wins_over_include(self):
        c = cfg(include=["contact/*"], exclude=["contact/email"], group_headers=False)
        self.assertEqual([e["path"] for e in build_entries(self.SUB, c)], ["contact/name"])

    def test_repeat_children_follow_included_parent(self):
        c = cfg(include=["household"], group_headers=False)
        entries = build_entries(self.SUB, c)
        self.assertEqual(len(entries), 1)
        repeat = entries[0]
        self.assertEqual(repeat["type"], "repeat")
        # second row only had an empty value, so it is dropped
        self.assertEqual(len(repeat["items"]), 1)
        self.assertEqual(repeat["items"][0][0]["label"], "Member name")

    def test_group_headers(self):
        c = cfg(labels={"contact": "Your details"})
        entries = build_entries(self.SUB, c)
        self.assertEqual(entries[0], {"type": "section", "path": "contact", "label": "Your details"})

    def test_ungrouped_after_group_gets_header(self):
        sub = {"contact/name": "A", "age": "3", "household": [{"household/n": "x"}], "note": "y"}
        labels = [e["label"] for e in build_entries(sub, cfg()) if e["type"] == "section"]
        self.assertEqual(labels, ["Contact", "Other answers", "Other answers"])

    def test_labels_by_path_or_name(self):
        c = cfg(labels={"contact/name": "Full name", "member_name": "Name"}, group_headers=False)
        entries = build_entries(self.SUB, c)
        self.assertEqual(entries[0]["label"], "Full name")
        self.assertEqual(entries[2]["items"][0][0]["label"], "Name")

    def test_show_empty(self):
        c = cfg(hide_empty=False, group_headers=False)
        self.assertIn("age", [e["path"] for e in build_entries(self.SUB, c)])


if __name__ == "__main__":
    unittest.main()
