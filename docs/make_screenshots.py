"""Regenerate the README screenshots in docs/assets (dev only: needs Chrome and Pillow).

    python docs/make_screenshots.py [--chrome PATH]
"""
import argparse, json, subprocess, sys, tempfile
from html import escape
from pathlib import Path

from PIL import Image, ImageChops

parser = argparse.ArgumentParser()
parser.add_argument("--chrome", default=r"C:\Program Files\Google\Chrome\Application\chrome.exe")
ARGS = parser.parse_args()
ROOT = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp())
sys.path.insert(0, str(ROOT))
from kobo2mail.config import form_config, load_config  # noqa: E402
from kobo2mail.render import render_email  # noqa: E402

CHROME = ARGS.chrome
OUT = ROOT / "docs" / "assets"
OUT.mkdir(parents=True, exist_ok=True)

sub = json.loads((ROOT / "examples/sample_submission.json").read_text(encoding="utf-8"))
cfg = form_config(load_config(ROOT / "config.json"), sub)
cfg["button_label"], cfg["button_url"] = "Contact the team", "mailto:team@example.org"


def shot(html_path, png_path, width, height, scale=1.5):
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    f"--force-device-scale-factor={scale}", f"--window-size={width},{height}",
                    f"--screenshot={png_path}", html_path.as_uri()],
                   check=True, capture_output=True)


def trim_bottom(png_path, pad=24):
    img = Image.open(png_path).convert("RGB")
    bg = Image.new("RGB", img.size, img.getpixel((2, img.height - 2)))
    bbox = ImageChops.difference(img, bg).getbbox()
    if bbox:
        img = img.crop((0, 0, img.width, min(img.height, bbox[3] + pad)))
    img.save(png_path, optimize=True)


rendered = {}
for path in sorted((ROOT / "templates").glob("*.html")):
    _, html, _ = render_email(sub, cfg, path.read_text(encoding="utf-8"))
    rendered[path.stem] = html
    page = TMP / f"{path.stem}.html"
    page.write_text(html, encoding="utf-8")
    png = OUT / f"template-{path.stem}.png"
    shot(page, png, 680, 1500)
    trim_bottom(png)
    print("wrote", png.name, Image.open(png).size)

# Phone mockup of the modern template.
phone = TMP / "phone.html"
phone.write_text(f"""<!DOCTYPE html><html><body style="margin:0;background:transparent;">
<div style="width:375px;height:760px;margin:20px;border:12px solid #1a202c;border-radius:44px;overflow:hidden;
box-shadow:0 20px 40px rgba(0,0,0,.25);background:#fff;">
<iframe srcdoc="{escape(rendered['modern'], quote=True)}" style="width:375px;height:760px;border:0;"></iframe>
</div></body></html>""", encoding="utf-8")
png = OUT / "phone-modern.png"
subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1.5",
                "--default-background-color=00000000", "--window-size=440,840",
                f"--screenshot={png}", phone.as_uri()], check=True, capture_output=True)
img = Image.open(png)
img.save(png, optimize=True)
print("wrote", png.name, img.size)
