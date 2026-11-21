#!/usr/bin/env python3
"""Render the book and refuse to pass on a warning that reaches the reader.

`quarto render` exits 0 with a broken chapter in `_book/`. The failures this
book has actually shipped or nearly shipped all looked like a green build:

* `[WARNING] Citeproc: citation slides not found` -- a scribe note cited the
  lecture deck by a key this repository does not define. Quarto renders the
  citation as a bare `[?]` and exits 0. Chapter 14 was rendered, checked and
  about to be pushed with it; it was caught by reading the log by eye, which
  is not a control.
* A figure referenced as `.pdf`. The PDF build is happy, the HTML build does
  not take it, and the published page shows a broken image.
* An unresolved crossref. Quarto writes `?eq-foo` into the page and carries on.
* Grading detail in the output, which `check_publishable.py` exists for and
  which nothing ran automatically before the push.
* A render of one format at a time, which clears `_book/` first: `--to html`
  followed by `--to pdf` leaves no `index.html` and Pages serves a 404 from a
  green build. So this always renders both in one pass, as `_quarto.yml` says.

Every one of those is a grep. This runs the render, greps it, greps what the
render produced, then runs the publishable check, and exits non-zero if any of
them has something to say. Nothing here needs judgement; what needed judgement
was deciding the citation key, once.

Usage:
    python scripts/render_gate.py                  # render, then gate
    python scripts/render_gate.py --skip-render    # gate the build already in _book/
    python scripts/render_gate.py --log saved.log  # gate a saved render log
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BOOK = REPO / "_book"
HOME = Path.home()

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\r")
RENDERING = re.compile(r"\[\s*\d+/\d+\]\s+(\S+\.qmd)")
CITEPROC = re.compile(r"Citeproc: citation (\S+) not found")
KINDS = ("eq", "sec", "fig", "tbl", "def", "prp", "thm", "lem",
         "exm", "cor", "rem", "alg", "lst")
UNRESOLVED = re.compile(r"\?(" + "|".join(KINDS) + r")-[A-Za-z0-9_-]+")
IMG = re.compile(r'<img[^>]+src="([^"]+)"')


def render(log_path: Path) -> int:
    """One `quarto render`, both formats, streamed to the log and the screen."""
    env = dict(os.environ)
    env["QUARTO_SHARE_PATH"] = str(HOME / "miniforge3" / "share" / "quarto")
    env["PATH"] = os.pathsep.join([
        str(HOME / ".TinyTeX" / "bin" / "x86_64-linux"),
        str(HOME / "miniforge3" / "bin"), env.get("PATH", "")])
    print("rendering both formats; the PDF pass takes a few minutes")
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.Popen(["quarto", "render"], cwd=REPO, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1)
        for line in proc.stdout:
            log.write(line)
            clean = ANSI.sub("", line).rstrip()
            if RENDERING.search(clean) or "Output created" in clean \
                    or "WARNING" in clean or "ERROR" in clean:
                print(f"  {clean}")
        return proc.wait()


def gate_log(log_path: Path) -> list[str]:
    bad: list[str] = []
    if not log_path.exists():
        return [f"no render log at {log_path}"]
    current = "(before the first chapter)"
    saw_output = False
    # A missing citation is reported once per chapter pass and again in the
    # pandoc pass that builds the PDF, where no chapter is being named any
    # more -- the same key twice is one defect, so key them.
    missing_cites: dict[str, str] = {}
    for raw in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = ANSI.sub("", raw).strip()
        m = RENDERING.search(line)
        if m:
            current = m.group(1)
        if line.startswith("pandoc") or "Rendering PDF" in line:
            current = "(pdf pass)"
        if "Output created" in line:
            saw_output = True
        cp = CITEPROC.search(line)
        if cp:
            missing_cites.setdefault(cp.group(1), current)
        elif "[WARNING]" in line or "[ERROR]" in line:
            bad.append(f"{current}: {line}")
    for key, where in missing_cites.items():
        bad.append(f"{where}: cites `@{key}`, which is not in references.bib. "
                   "The page renders it as [?].")
    if not saw_output:
        bad.append(f"{log_path.name} never says 'Output created', so the "
                   "render did not finish")
    return bad


def gate_build() -> list[str]:
    bad: list[str] = []
    if not (BOOK / "index.html").exists():
        return [f"{BOOK.name}/index.html is missing; Pages would serve a 404"]

    pages = sorted(BOOK.glob("*.html")) + sorted((BOOK / "chapters").glob("*.html"))
    for page in pages:
        html = page.read_text(encoding="utf-8", errors="replace")
        for ref in sorted(set(UNRESOLVED.findall(html))):
            bad.append(f"{page.name}: unresolved crossref `?{ref}-...`")
        for src in sorted(set(IMG.findall(html))):
            if src.startswith(("http://", "https://", "data:")):
                continue
            if not (page.parent / src).exists():
                bad.append(f"{page.name}: <img src=\"{src}\"> is not in the build")

    pdfs = list(BOOK.glob("*.pdf"))
    if not pdfs:
        bad.append("no PDF in the build; _quarto.yml declares one")
    else:
        pdf = pdfs[0]
        mb = pdf.stat().st_size / 1e6
        try:
            try:
                import pymupdf
            except ImportError:
                import fitz as pymupdf
            doc = pymupdf.open(pdf)
            print(f"  PDF {pdf.name}: {doc.page_count} pages, {mb:.1f} MB")
            doc.close()
        except ImportError:
            print(f"  PDF {pdf.name}: {mb:.1f} MB (pymupdf absent, no page count)")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--skip-render", action="store_true",
                    help="gate the build already in _book/")
    ap.add_argument("--log", help="gate this render log instead of rendering")
    ap.add_argument("--log-out", default="render.log",
                    help="where to write the render log (default: render.log)")
    args = ap.parse_args()

    log_path = Path(args.log) if args.log else (REPO / args.log_out)
    if not args.skip_render and not args.log:
        rc = render(log_path)
        if rc != 0:
            print(f"\nquarto render exited {rc}; see {log_path}")
            return 1

    failures: list[str] = []
    print("\n--- render log ---")
    log_bad = gate_log(log_path)
    for b in log_bad:
        print(f"  BLOCKING {b}")
    if not log_bad:
        print("  clean.")
    failures += log_bad

    print("--- built output ---")
    build_bad = [] if args.log and not BOOK.exists() else gate_build()
    for b in build_bad:
        print(f"  BLOCKING {b}")
    if not build_bad:
        print("  clean.")
    failures += build_bad

    print("--- publishable check ---")
    check = REPO / "scripts" / "check_publishable.py"
    proc = subprocess.run([sys.executable, str(check), "--both"],
                          cwd=REPO, capture_output=True, text=True)
    tail = [l for l in proc.stdout.splitlines() if l.strip()][-6:]
    for line in tail:
        print(f"  {line}")
    if proc.returncode != 0:
        failures.append("check_publishable.py refused the output")

    print()
    if failures:
        print(f"{len(failures)} blocking issue(s). Do not push.")
        return 1
    print("gate passed: the build is clean and carries no grading detail.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
