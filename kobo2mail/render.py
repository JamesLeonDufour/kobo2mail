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


LAYOUTS = ("stacked", "columns")
_LAYOUT_HINT = re.compile(r"<!--\s*kobo2mail:\s*layout\s*=\s*(\w+)\s*-->")


def _section_html(label, color, span):
    return (
        f'<tr><td colspan="{span}" style="padding:22px 0 6px;font-size:13px;font-weight:bold;'
        f'text-transform:uppercase;letter-spacing:0.06em;color:{color};'
        f'border-bottom:2px solid {color};">{escape(label)}</td></tr>'
    )


def _field_html(entry, layout):
    label, value = escape(entry["label"]), _html_value(entry["value"])
    if layout == "columns":
        return (
            '<tr><td width="38%" valign="top" style="padding:9px 12px 9px 0;'
            'border-bottom:1px solid #edf2f7;font-size:13px;line-height:20px;color:#718096;">'
            f'{label}</td><td valign="top" style="padding:9px 0;border-bottom:1px solid #edf2f7;'
            f'font-size:15px;line-height:20px;color:#1a202c;word-break:break-word;">{value}</td></tr>'
        )
    return (
        '<tr><td style="padding:10px 0;border-bottom:1px solid #edf2f7;">'
        f'<div style="{_LABEL_STYLE}">{label}</div>'
        f'<div style="{_VALUE_STYLE}">{value}</div></td></tr>'
    )


def _rows_html(entries, color, layout):
    span = 2 if layout == "columns" else 1
    rows = []
    for entry in entries:
        if entry["type"] == "section":
            rows.append(_section_html(entry["label"], color, span))
        elif entry["type"] == "field":
            rows.append(_field_html(entry, layout))
        else:  # repeat
            rows.append(_section_html(entry["label"], color, span))
            for index, item in enumerate(entry["items"], start=1):
                rows.append(
                    f'<tr><td colspan="{span}" style="padding:10px 0 0;">'
                    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                    f'style="background:#f7fafc;border-left:3px solid {color};border-radius:4px;">'
                    '<tr><td style="padding:10px 16px 4px;">'
                    f'<div style="font-size:14px;font-weight:bold;color:#2d3748;">'
                    f'{escape(entry["label"])} {index}</div>'
                    '<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
                    f"{_rows_html(item, color, layout)}</table>"
                    "</td></tr></table></td></tr>"
                )
    return "".join(rows)


def resolve_layout(cfg, template_text):
    """Config 'layout' wins; otherwise the template's <!-- kobo2mail: layout=... --> hint."""
    layout = cfg.get("layout") or ""
    if not layout:
        hint = _LAYOUT_HINT.search(template_text)
        layout = hint.group(1) if hint else "stacked"
    return layout if layout in LAYOUTS else "stacked"


def answers_table_html(entries, cfg, layout="stacked"):
    return (
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        'style="border-collapse:collapse;">'
        f'{_rows_html(entries, escape(cfg["brand_color"]), layout)}</table>'
    )


def tint(hex_color, amount=0.9):
    """Mix a #rrggbb color with white; used for soft backgrounds ($brand_tint)."""
    value = hex_color.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    try:
        rgb = [int(value[i:i + 2], 16) for i in (0, 2, 4)]
    except ValueError:
        return "#f7fafc"
    return "#" + "".join(f"{round(c + (255 - c) * amount):02x}" for c in rgb)


def button_html(cfg, values):
    label, url = _fill(cfg.get("button_label", ""), values), _fill(cfg.get("button_url", ""), values)
    if not (label and url.startswith(("https://", "http://", "mailto:"))):
        return ""
    color = escape(cfg["brand_color"])
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" style="margin:8px 0;"><tr>'
        f'<td style="border-radius:6px;background:{color};">'
        f'<a href="{escape(url)}" style="display:inline-block;padding:12px 24px;font-size:15px;'
        f'font-weight:bold;color:#ffffff;text-decoration:none;border-radius:6px;">{escape(label)}</a>'
        "</td></tr></table>"
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
    # Free-form template variables from config ("vars"), e.g. $org_name, $contact_phone.
    values.update({key: _fill(str(text), values) for key, text in cfg.get("vars", {}).items()})
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
        brand_tint=tint(cfg["brand_color"]),
        logo_block=logo_block,
        button_block=button_html(cfg, values),
        answers_table=answers_table_html(entries, cfg, resolve_layout(cfg, template_text)),
    )
    html = _fill(template_text, html_values)

    text_lines = [title, "", intro, ""] + _rows_text(entries)
    if html_values["button_block"]:
        text_lines += ["", f"{_fill(cfg['button_label'], values)}: {_fill(cfg['button_url'], values)}"]
    text_lines += ["", "--", footer]
    if values["submission_id"]:
        text_lines.append(f"Submission #{values['submission_id']} {values['submitted_at']}".rstrip())
    text = "\n".join(text_lines).strip() + "\n"
    return subject, html, text
