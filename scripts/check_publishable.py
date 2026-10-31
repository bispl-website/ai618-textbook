#!/usr/bin/env python3
"""Refuse to publish grading detail.

The book is public; the grades are not. Every chapter carries a provenance
comment saying which note it was built from and what was merged in, and that
comment is written during the merge, when the grade records are open on the
same screen. Twice now a score has travelled with it: `Myungjo Kwak (95.0 of
100)` shipped in chapter 9's page source on 2026-10-26 and `Kiet Nguyen (97.0
of 100)` in chapter 10's on 2026-10-30. An HTML comment is not hidden -- it is
served verbatim to every reader, and by then caches and archives have it.

Nothing caught either one. The build is green whether or not a grade is in the
output, which is the whole failure class: the artefact is wrong and the
pipeline is happy. So this runs over what will actually be served, not over
the sources, and fails the build before the deploy step can reach Pages.

Two tiers, because the book talks about grading on purpose. `index.qmd`
describes the rubric and the process, the chapter stubs say a lecture is "not
yet written and graded", and a figure caption in chapter 5 says images "are
scored by PSNR". None of that is a leak, and a check that flags it would be
switched off within a week. What a leak looks like is grading detail attached
to a person or a submission: a number out of a rubric total, a field name from
a grade record, a judgement credited to "the grader", a path into the private
repository.

  leak    -- exits 1. The deploy must not happen.
  review  -- printed, exits 0. Shapes that are usually innocent and
             occasionally not: an integer out of 100, a small fraction that
             happens to match a criterion's total, an HTML comment that
             mentions grading at all.

If a leak pattern genuinely has to ship -- a chapter quoting a benchmark
"out of 100" -- put `publishable-ok` on the same line, in the comment or in
the source. Those are listed separately and have to be defended in review;
they are not silent.

Usage:
    python scripts/check_publishable.py                 # _book if built, else sources
    python scripts/check_publishable.py --built _book
    python scripts/check_publishable.py --sources
    python scripts/check_publishable.py --both
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Grading words that are fine in the book's own prose about the course, and a
# smell inside an HTML comment, which is where the editor's working notes end
# up.
GRADING_WORDS = re.compile(
    r"\b(?:grade[ds]?|grading|rubric|scored?|scores|marks?|criteri(?:on|a))\b", re.I)

# The same words inside an HTML comment, minus the ones this book uses for
# other things. "Score" alone is the commonest word in a book about score-based
# models; it means something here only when it carries a number.
COMMENT_WORDS = re.compile(
    r"\b(?:grade[ds]?|grading|rubric|criteri(?:on|a))\b"
    r"|\bscored?\s+\d|\bscore of \d|\bout of \d|\bmarks?\s+(?:of|for)\s+\d", re.I)

# A score out of a rubric total, a grade-record field, a judgement credited to
# the grader, or a path into the private side of the pipeline.
LEAK = [
    ("score out of 100",
     re.compile(r"\b\d{1,3}\.\d\s*(?:/|of|out of)\s*100\b")),
    ("score out of 100",
     re.compile(r"\b\d{1,3}\s*(?:/|out of)\s*100\b")),
    ("grade-record field",
     re.compile(r"\b(?:technical_correctness|figures_and_formatting"
                r"|derivations_and_reproducibility|coverage_gaps"
                r"|suspected_errors|english_fluency_flag|needs_human_attention"
                r"|disagreement_signal|single_pass|graded_by|raised_by_passes"
                r"|submission_id)\b")),
    ("judgement credited to the grader",
     re.compile(r"\bgraders?\b", re.I)),
    ("marks moved",
     re.compile(r"\bre-?scored\b"
                r"|\bpoints?\s+(?:withheld|restored|deducted)\b"
                r"|\bmarked down\b"
                r"|\bdeduct(?:ed|ion|ions)\b"
                r"|\blate(?:ness)?\s+penalt(?:y|ies)\b"
                r"|\bdiscretionary adjustment\b", re.I)),
    ("private path or repository",
     re.compile(r"adjustments\.md|ai618-grades-2026f"
                r"|\.verdict\.json|\blec\d\d-[0-9a-f]{6}\b")),
]

# Usually innocent. A criterion-sized fraction is a leak only when a grading
# word is on the line with it; on its own it is arithmetic.
REVIEW = [
    ("count out of 100, probably prose",
     re.compile(r"\b\d{1,3}\s*of\s*100\b")),
    ("fraction matching a rubric total",
     re.compile(r"\b\d{1,2}\s*/\s*(?:25|20|15)\b")),
]
RUBRIC_TOTAL = REVIEW[1][1]

# What turns a criterion-sized fraction from arithmetic into a score: the name
# of a criterion, or of the person who applied it, on the same line.
CRITERION_CONTEXT = re.compile(
    r"\b(?:coverage|exposition|rubric|criteri(?:on|a)|grade[rds]?|grading"
    r"|technical correctness|figures and formatting|derivations)\b", re.I)

COMMENT = re.compile(r"<!--(.*?)-->", re.S)
# Quarto's own layout comments: <!-- content -->, <!-- sidebar -->, <!-- main -->.
STRUCTURAL = re.compile(r"^[\w /-]{0,40}$")


def pdf_text(pdf: Path) -> str | None:
    """The PDF is published too. Comments never reach it, but visible prose does."""
    if shutil.which("pdftotext"):
        out = subprocess.run(["pdftotext", str(pdf), "-"],
                             capture_output=True, text=True)
        if out.returncode == 0:
            return out.stdout
    try:
        import fitz  # pymupdf
    except ImportError:
        return None
    with fitz.open(pdf) as doc:
        return "\n".join(page.get_text() for page in doc)


def targets(args) -> tuple[list[Path], list[str]]:
    built = Path(args.built) if args.built else REPO / "_book"
    have_built = (built / "index.html").is_file()
    want_built = args.both or args.built or (not args.sources and have_built)
    want_sources = args.both or args.sources or not want_built

    paths, notes = [], []
    if want_built:
        if not have_built:
            notes.append(f"! {built} holds no index.html -- nothing built to check")
        else:
            paths += sorted(built.rglob("*.html"))
            paths += sorted(built.rglob("*.pdf"))
            notes.append(f"built output: {built}")
    if want_sources:
        paths += [REPO / "index.qmd", REPO / "references.qmd", REPO / "README.md"]
        paths += sorted((REPO / "chapters").glob("*.qmd"))
        notes.append("sources: index.qmd, references.qmd, README.md, chapters/*.qmd")
        if not want_built:
            notes.append("! sources only. The served page is what matters; "
                         "run `quarto render` first, or pass --both.")
    return [p for p in paths if p.exists()], notes


def scan(path: Path) -> tuple[list, list, list]:
    """Return (leaks, reviews, allowed) as (line_no, label, line) triples."""
    if path.suffix == ".pdf":
        text = pdf_text(path)
        if text is None:
            return [], [("-", "pdf text not extractable "
                         "(no pdftotext, no pymupdf) -- not checked", path.name)], []
    else:
        text = path.read_text(errors="replace")

    leaks, reviews, allowed = [], [], []
    for n, line in enumerate(text.splitlines(), 1):
        hit = False
        for label, pat in LEAK:
            if pat.search(line):
                hit = True
                (allowed if "publishable-ok" in line else leaks).append(
                    (n, label, line.strip()))
        for label, pat in REVIEW:
            if not pat.search(line) or "publishable-ok" in line:
                continue
            # A rubric-sized fraction beside a criterion's name is a score, not
            # arithmetic. Otherwise leave it for a human to glance at -- and say
            # nothing at all about a line that is already a leak.
            if pat is RUBRIC_TOTAL and CRITERION_CONTEXT.search(line):
                leaks.append((n, "criterion score", line.strip()))
            elif not hit:
                reviews.append((n, label, line.strip()))

    # An HTML comment is served to every reader. Anything in one that talks
    # about grading is the editor's working notes left in the output.
    if path.suffix in (".html", ".qmd"):
        for m in COMMENT.finditer(text):
            body = m.group(1).strip()
            if STRUCTURAL.match(body) or not COMMENT_WORDS.search(body):
                continue
            if "publishable-ok" in body:
                continue
            n = text.count("\n", 0, m.start()) + 1
            word = COMMENT_WORDS.search(body).group(0)
            reviews.append((n, f"comment mentions \"{word}\" and ships to "
                               "the page source", body.replace("\n", " ")[:120]))
    return leaks, reviews, allowed


def report(title: str, rows: list, limit: int = 200) -> None:
    print(f"\n{title}")
    if not rows:
        print("  none")
        return
    for path, n, label, line in rows[:limit]:
        where = path.relative_to(REPO) if REPO in path.parents else path
        print(f"  {where}:{n}  [{label}]")
        print(f"      {line[:150]}")
    if len(rows) > limit:
        print(f"  ... and {len(rows) - limit} more")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Fail if grading detail would be published.")
    ap.add_argument("--built", metavar="DIR",
                    help="built output to check (default: _book when it exists)")
    ap.add_argument("--sources", action="store_true",
                    help="check the .qmd sources instead of the built output")
    ap.add_argument("--both", action="store_true")
    ap.add_argument("--quiet", action="store_true",
                    help="print nothing when the check passes with no reviews")
    args = ap.parse_args()

    paths, notes = targets(args)
    leaks, reviews, allowed = [], [], []
    for p in paths:
        l, r, a = scan(p)
        leaks += [(p, *row) for row in l]
        reviews += [(p, *row) for row in r]
        allowed += [(p, *row) for row in a]

    quiet = args.quiet and not leaks and not reviews
    if not quiet:
        print(f"checked {len(paths)} files")
        for note in notes:
            print(f"  {note}")
        report("leaks -- grading detail in publishable output", leaks)
        report("review -- probably innocent, read them", reviews)
        if allowed:
            report("marked publishable-ok -- defend these in review", allowed)

    if leaks:
        print(f"\nFAIL: {len(leaks)} leak(s). Do not push. The grades live in "
              "ai618-grades-2026f and nowhere else.")
        return 1
    if not quiet:
        print("\nOK: no grading detail in the output."
              + (f" {len(reviews)} line(s) to read." if reviews else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
