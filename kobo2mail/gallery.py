"""Render every template in templates/ with a sample submission into one comparison page.

    python -m kobo2mail.gallery [--submission FILE] [--config FILE] [--out gallery.html]
"""

import argparse
import json
import sys
from html import escape
from pathlib import Path

from .config import form_config, load_config
from .render import render_email, resolve_layout

DEMO_BUTTON = ("Contact the team", "mailto:team@example.org")


def build_gallery(submission, cfg, template_paths):
    if not cfg["button_label"]:
        cfg["button_label"], cfg["button_url"] = DEMO_BUTTON
    cards = []
    for path in template_paths:
        template_text = path.read_text(encoding="utf-8")
        _, html, _ = render_email(submission, cfg, template_text)
        doc = escape(html, quote=True)
        cards.append(f"""
<section>
  <h2>{escape(path.stem)} <small>templates/{escape(path.name)} &middot; layout: {resolve_layout(cfg, template_text)}</small></h2>
  <div class="frames">
    <iframe class="desktop" srcdoc="{doc}" title="{escape(path.stem)} desktop"></iframe>
    <iframe class="mobile" srcdoc="{doc}" title="{escape(path.stem)} mobile"></iframe>
  </div>
</section>""")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>kobo2mail templates</title>
<style>
  body {{ margin:0; padding:24px; background:#e2e8f0; font-family:system-ui,sans-serif; color:#1a202c; }}
  h1 {{ margin:0 0 4px; }} p {{ margin:0 0 24px; color:#4a5568; }}
  section {{ background:#fff; border-radius:10px; padding:16px 20px 20px; margin-bottom:28px; }}
  h2 {{ margin:0 0 12px; text-transform:capitalize; }} small {{ font-weight:normal; color:#718096; font-size:13px; text-transform:none; }}
  .frames {{ display:flex; gap:20px; align-items:flex-start; flex-wrap:wrap; }}
  iframe {{ border:1px solid #cbd5e0; border-radius:8px; height:1150px; background:#fff; }}
  .desktop {{ width:680px; max-width:100%; }} .mobile {{ width:375px; max-width:100%; }}
</style></head><body>
<h1>kobo2mail templates</h1>
<p>Sample submission rendered with your config. Set <code>"template"</code> in config.json to pick one.
The button is a demo unless <code>button_label</code>/<code>button_url</code> are configured.</p>
{''.join(cards)}
</body></html>"""


def main(argv=None):
    parser = argparse.ArgumentParser(prog="kobo2mail.gallery", description=__doc__.splitlines()[0])
    parser.add_argument("--submission", default="examples/sample_submission.json")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--templates", default="templates", help="Folder of .html templates")
    parser.add_argument("--out", default="gallery.html")
    args = parser.parse_args(argv)

    submission = json.loads(Path(args.submission).read_text(encoding="utf-8"))
    cfg = form_config(load_config(args.config), submission)
    cfg["layout"] = ""  # let each template's own layout hint apply
    templates = sorted(Path(args.templates).glob("*.html"))
    if not templates:
        print(f"No templates found in {args.templates}")
        return 1
    Path(args.out).write_text(build_gallery(submission, cfg, templates), encoding="utf-8")
    print(f"Gallery with {len(templates)} templates written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
