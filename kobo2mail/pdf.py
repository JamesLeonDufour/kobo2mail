"""Render the submission as a PDF with headless Chrome (preinstalled on GitHub's ubuntu runners).

No Python dependencies: the answers are rendered into templates/pdf.html with the same
fields, labels and placeholders as the email, then printed by Chrome, Chromium or Edge.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .render import _fill, placeholder_values, render_email

_CANDIDATES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge")
_WINDOWS_PATHS = (
    r"Google\Chrome\Application\chrome.exe",
    r"Microsoft\Edge\Application\msedge.exe",
)
_MAC_PATHS = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
)


class PdfError(RuntimeError):
    pass


def find_chrome(env=None):
    """Path of a Chromium-based browser: $CHROME_PATH, then PATH, then the usual install folders."""
    env = os.environ if env is None else env
    override = env.get("CHROME_PATH", "").strip()
    if override:
        return override if Path(override).is_file() else None
    for name in _CANDIDATES:
        found = shutil.which(name)
        if found:
            return found
    if sys.platform == "win32":
        roots = [env.get(k) for k in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
        for root in filter(None, roots):
            for relative in _WINDOWS_PATHS:
                path = Path(root) / relative
                if path.is_file():
                    return str(path)
    if sys.platform == "darwin":
        for path in _MAC_PATHS:
            if Path(path).is_file():
                return path
    return None


def pdf_filename(submission, cfg):
    """Attachment name from cfg['pdf_filename'] ($placeholders allowed), reduced to safe characters."""
    name = _fill(cfg["pdf_filename"], placeholder_values(submission, cfg))
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    if not name.lower().endswith(".pdf"):
        name = (name or "submission") + ".pdf"
    return name


def render_pdf_html(submission, cfg, template_text):
    """HTML for the PDF: the email rendering pipeline with the print template and pdf_title."""
    # layout="" lets the print template's own layout hint (columns) win over the email's.
    _, html, _ = render_email(submission, {**cfg, "title": cfg["pdf_title"], "layout": ""}, template_text)
    return html


def html_to_pdf(html, chrome, timeout=60):
    """Print HTML to PDF bytes. Raises PdfError naming the failure, never the content."""
    in_ci = os.environ.get("GITHUB_ACTIONS") == "true"
    with tempfile.TemporaryDirectory(prefix="kobo2mail-") as tmp:
        source, target = Path(tmp) / "submission.html", Path(tmp) / "submission.pdf"
        source.write_text(html, encoding="utf-8")
        command = [
            chrome,
            "--headless",
            "--disable-gpu",
            "--no-first-run",
            "--disable-extensions",
            f"--user-data-dir={Path(tmp) / 'profile'}",
            "--no-pdf-header-footer",
            "--print-to-pdf-no-header",  # older Chrome versions
            f"--print-to-pdf={target}",
        ]
        if in_ci:
            # Ubuntu 24.04 runners block Chrome's user-namespace sandbox; the page is our own escaped HTML.
            command.append("--no-sandbox")
        command.append(source.as_uri())
        try:
            subprocess.run(command, capture_output=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            raise PdfError(f"Chrome timed out after {timeout}s") from None
        except OSError as exc:
            raise PdfError(f"Could not start Chrome ({type(exc).__name__})") from None
        if not target.is_file() or target.stat().st_size == 0:
            raise PdfError("Chrome did not produce a PDF")
        return target.read_bytes()


def render_pdf(submission, cfg, chrome=None):
    """Return (filename, pdf_bytes) for this submission."""
    chrome = chrome or find_chrome()
    if not chrome:
        raise PdfError("No Chrome, Chromium or Edge found (set CHROME_PATH)")
    try:
        template_text = cfg["pdf_template_path"].read_text(encoding="utf-8")
    except OSError:
        raise PdfError(f"PDF template not found: {cfg['pdf_template']}") from None
    html = render_pdf_html(submission, cfg, template_text)
    return pdf_filename(submission, cfg), html_to_pdf(html, chrome)
