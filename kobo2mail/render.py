"""Render the email subject, HTML body and plain-text body."""

import re
from collections import Counter
from datetime import datetime
from html import escape
from string import Template

from .fields import build_entries, format_value


class _BlankMissing(dict):
    """Unknown $placeholders render as empty strings instead of staying literal."""

    def __missing__(self, key):
        return ""


def _identifier(text):
    return re.sub(r"\W", "_", text)


def placeholder_values(submission, cfg):
    """Plain-text values usable as $placeholders.

    Every scalar field is available as its full path with '/' replaced by '__'
    (contact/name -> $contact__name), and also by its bare name ($name) when that
    name is unique in the submission.
    """
    scalars = {k: v for k, v in submission.items() if not isinstance(v, (dict, list))}
    name_counts = Counter(_identifier(k.rsplit("/", 1)[-1]) for k in scalars)
    values = {}
    for path, value in scalars.items():
        text = format_value(path, value, cfg)
        values[_identifier(path.replace("/", "__"))] = text
        name = _identifier(path.rsplit("/", 1)[-1])
        if name_counts[name] == 1:
            values.setdefault(name, text)
    values["submission_id"] = str(submission.get("_id", ""))
    values["submitted_at"] = _format_time(submission.get("_submission_time"))
    return values


def _format_time(raw):
    if not raw:
        return ""
    try:
        moment = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return str(raw)
    return moment.strftime("%d %b %Y, %H:%M") + " UTC"


def _fill(text, values):
    return Template(text).safe_substitute(_BlankMissing(values))


# ---------------------------------------------------------------- HTML ---

_LABEL_STYLE = "font-size:12px;line-height:16px;color:#718096;text-transform:uppercase;letter-spacing:0.04em;"
_VALUE_STYLE = "font-size:15px;line-height:22px;color:#1a202c;padding-top:2px;word-break:break-word;"


def _html_value(text):
    return escape(text).replace("\n", "<br>")


def _rows_html(entries, color):
    rows = []
    for entry in entries:
        if entry["type"] == "section":
            rows.append(
                f'<tr><td style="padding:22px 0 6px;font-size:13px;font-weight:bold;'
                f'text-transform:uppercase;letter-spacing:0.06em;color:{color};'
                f'border-bottom:2px solid {color};">{escape(entry["label"])}</td></tr>'
            )
        elif entry["type"] == "field":
            rows.append(
                '<tr><td style="padding:10px 0;border-bottom:1px solid #edf2f7;">'
                f'<div style="{_LABEL_STYLE}">{escape(entry["label"])}</div>'
                f'<div style="{_VALUE_STYLE}">{_html_value(entry["value"])}</div></td></tr>'
            )
        else:  # repeat
            rows.append(
                f'<tr><td style="padding:22px 0 6px;font-size:13px;font-weight:bold;'
                f'text-transform:uppercase;letter-spacing:0.06em;color:{color};'
                f'border-bottom:2px solid {color};">{escape(entry["label"])}</td></tr>'
            )
            for index, item in enumerate(entry["items"], start=1):
                rows.append(
                    '<tr><td style="padding:10px 0 0;">'
                    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                    f'style="background:#f7fafc;border-left:3px solid {color};border-radius:4px;">'
                    '<tr><td style="padding:10px 16px 4px;">'
                    f'<div style="font-size:14px;font-weight:bold;color:#2d3748;">'
                    f'{escape(entry["label"])} {index}</div>'
                    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
                    f"{_rows_html(item, color)}</table>"
                    "</td></tr></table></td></tr>"
                )
    return "".join(rows)


def answers_table_html(entries, cfg):
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-collapse:collapse;">'
        f'{_rows_html(entries, escape(cfg["brand_color"]))}</table>'
    )


# ---------------------------------------------------------------- text ---

def _rows_text(entries, indent=""):
    lines = []
    for entry in entries:
        if entry["type"] == "section":
            lines += ["", f"{indent}== {entry['label']} =="]
        elif entry["type"] == "field":
            value = entry["value"].replace("\n", "\n" + indent + "  ")
            lines.append(f"{indent}{entry['label']}: {value}")
        else:
            lines += ["", f"{indent}== {entry['label']} =="]
            for index, item in enumerate(entry["items"], start=1):
                lines.append(f"{indent}{entry['label']} {index}")
                lines += _rows_text(item, indent + "  ")
    return lines


# ---------------------------------------------------------------- email ---

def render_email(submission, cfg, template_text):
    """Return (subject, html, text) for this submission."""
    values = placeholder_values(submission, cfg)
    entries = build_entries(submission, cfg)

    subject = " ".join(_fill(cfg["subject"], values).split())
    title = _fill(cfg["title"], values)
    intro = _fill(cfg["intro"], values)
    footer = _fill(cfg["footer"], values)

    logo_url = cfg["logo_url"]
    logo_block = (
        f'<img src="{escape(logo_url)}" alt="" height="40" style="display:block;height:40px;border:0;">'
        if logo_url else ""
    )
    html_values = {key: _html_value(value) for key, value in values.items()}
    html_values.update(
        title=_html_value(title),
        intro=_html_value(intro),
        footer=_html_value(footer),
        subject=_html_value(subject),
        brand_color=escape(cfg["brand_color"]),
        logo_block=logo_block,
        answers_table=answers_table_html(entries, cfg),
    )
    html = _fill(template_text, html_values)

    text_lines = [title, "", intro, ""] + _rows_text(entries) + ["", "--", footer]
    if values["submission_id"]:
        text_lines.append(f"Submission #{values['submission_id']} {values['submitted_at']}".rstrip())
    text = "\n".join(text_lines).strip() + "\n"
    return subject, html, text
