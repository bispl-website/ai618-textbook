#!/usr/bin/env python3
"""Find where a new chapter overlaps the chapters already in the book.

A lecture course doubles back on itself. DDIM is derived in one lecture and
used in the next; the score function turns up in four. So does the writing: a
scribe explains the thing their lecture needs, whether or not an earlier
chapter already explained it. Merged in without a look, the book says the same
thing twice in two notations, and the second telling is the one a reader trusts
least.

This narrows where to look. It reports three things, strongest signal first:

1. **Duplicate crossref labels.** Two chapters that both define `{#eq-ddim}`
   are a build problem, not a style problem -- Quarto resolves `@eq-ddim` to
   one of them and the other reference silently points at the wrong equation.
2. **Prose overlap, section by section.** Jaccard over 8-word shingles of prose
   only, the same measure `check_duplicates.py` uses on submissions, with the
   longest shared passage as evidence. Equations, code and headings are
   stripped: three people writing up the same mathematics *should* produce the
   same equations, and comparing those flags everything.
3. **Headings in common**, lowercased and stripped of their labels.

What it cannot see is the same idea in different words, which is most of the
real overlap. Treat a quiet report as "nothing mechanical to fix", not as
"nothing to merge".

Usage:
    python scripts/overlap.py --chapter chapters/ch07.qmd
    python scripts/overlap.py --candidate drafts/lec07-merged.qmd --before 07
    python scripts/overlap.py --chapter chapters/ch07.qmd --show-passages
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SHINGLE = 8
FLAG_JACCARD = 0.08          # chapters are longer than notes; flag earlier
FLAG_CONTAINMENT = 0.20
LABEL_RE = re.compile(r"\{#((?:sec|eq|fig|tbl|thm|lem|prp|cor|def|exm|alg)-[A-Za-z0-9_-]+)\}")
# Every chapter has these by design, so reporting them as overlap buries the
# one heading that actually says the same thing twice.
BOILERPLATE = {"(chapter head)", "overview", "notation", "summary",
               "connections and further reading", "exercises", "credit",
               "advanced topics", "further reading", "references"}


def prose(text: str) -> str:
    """Strip everything two chapters on neighbouring lectures must share."""
    if text.startswith("---"):
        lines = text.splitlines()
        for i in range(1, len(lines)):
            if lines[i].strip() in ("---", "..."):
                text = "\n".join(lines[i + 1:])
                break
    text = re.sub(r"<!--[\s\S]*?-->", " ", text)
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"\$\$[\s\S]*?\$\$", " ", text)
    text = re.sub(r"\\begin\{[a-zA-Z*]+\}[\s\S]*?\\end\{[a-zA-Z*]+\}", " ", text)
    text = re.sub(r"\$[^$\n]*\$", " ", text)
    text = re.sub(r"^\s*\|.*\|\s*$", " ", text, flags=re.M)
    text = re.sub(r"^\s*#+.*$", " ", text, flags=re.M)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"^\s*:::.*$", " ", text, flags=re.M)
    text = re.sub(r"[^a-zA-Z\s]", " ", text)
    return " ".join(text.lower().split())


def shingles(words: list[str]) -> set[tuple[str, ...]]:
    return {tuple(words[i:i + SHINGLE]) for i in range(max(0, len(words) - SHINGLE + 1))}


def compare(a: list[str], b: list[str]) -> tuple[float, float]:
    sa, sb = shingles(a), shingles(b)
    if not sa or not sb:
        return 0.0, 0.0
    shared = sa & sb
    return len(shared) / len(sa | sb), len(shared) / min(len(sa), len(sb))


def longest_passage(a: list[str], b: list[str]) -> str:
    sb = shingles(b)
    hits = [i for i in range(max(0, len(a) - SHINGLE + 1)) if tuple(a[i:i + SHINGLE]) in sb]
    if not hits:
        return ""
    runs, start = [], hits[0]
    for i in range(1, len(hits)):
        if hits[i] != hits[i - 1] + 1:
            runs.append((start, hits[i - 1] + SHINGLE))
            start = hits[i]
    runs.append((start, hits[-1] + SHINGLE))
    s, e = max(runs, key=lambda r: r[1] - r[0])
    return " ".join(a[s:e])


def sections(path: Path) -> list[tuple[str, str]]:
    """Split a chapter at its level-2 headings. Returns (heading, body)."""
    text = path.read_text()
    parts = re.split(r"^(##\s+.*)$", text, flags=re.M)
    out = [("(chapter head)", parts[0])] if parts[0].strip() else []
    for i in range(1, len(parts) - 1, 2):
        out.append((parts[i].lstrip("# ").strip(), parts[i + 1]))
    return out


def heading_key(h: str) -> str:
    return " ".join(LABEL_RE.sub("", h).lower().split())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--chapter", help="a chapter in the book, e.g. chapters/ch07.qmd")
    g.add_argument("--candidate", help="any .qmd not yet in the book")
    ap.add_argument("--before", help="compare against chapters up to this number "
                                     "(default: those before --chapter)")
    ap.add_argument("--show-passages", action="store_true",
                    help="print the longest shared passage for each flagged pair")
    args = ap.parse_args()

    cand = Path(args.chapter or args.candidate)
    if not cand.is_absolute():
        cand = REPO / cand
    if not cand.exists():
        sys.exit(f"no such file: {cand}")

    limit = args.before
    if limit is None and args.chapter:
        m = re.search(r"ch(\d+)", cand.stem)
        limit = m.group(1) if m else None
    others = []
    for p in sorted((REPO / "chapters").glob("ch*.qmd")):
        if p.resolve() == cand.resolve():
            continue
        m = re.search(r"ch(\d+)", p.stem)
        if limit is not None and m and int(m.group(1)) >= int(limit):
            continue
        if p.stat().st_size < 400:                 # an untouched stub
            continue
        others.append(p)
    if not others:
        print("no earlier chapters with content to compare against")
        return 0

    print(f"{cand.name} against {len(others)} earlier chapter(s): "
          f"{', '.join(p.stem for p in others)}\n")

    # 1. duplicate crossref labels
    cand_labels = set(LABEL_RE.findall(cand.read_text()))
    clashes = []
    for p in others:
        for lab in set(LABEL_RE.findall(p.read_text())) & cand_labels:
            clashes.append((lab, p.stem))
    if clashes:
        print("DUPLICATE CROSSREF LABELS -- fix these before rendering")
        for lab, where in sorted(clashes):
            print(f"  {{#{lab}}} also defined in {where}")
    else:
        print("crossref labels: no clashes")

    # 2. prose overlap, section by section
    cand_secs = [(h, prose(b).split()) for h, b in sections(cand)]
    other_secs = [(p.stem, h, prose(b).split()) for p in others for h, b in sections(p)]
    print("\nprose overlap (jaccard >= "
          f"{FLAG_JACCARD:.2f} or containment >= {FLAG_CONTAINMENT:.2f})")
    flagged = 0
    for h, words in cand_secs:
        if len(words) < 120:
            continue
        hits = []
        for ch, oh, ow in other_secs:
            if len(ow) < 120:
                continue
            j, c = compare(words, ow)
            if j >= FLAG_JACCARD or c >= FLAG_CONTAINMENT:
                hits.append((j, c, ch, oh, ow))
        for j, c, ch, oh, ow in sorted(hits, reverse=True)[:2]:
            flagged += 1
            print(f"  {h[:46]:<46} ~ {ch} / {oh[:34]:<34} "
                  f"jaccard {j:.2f}  containment {c:.2f}")
            if args.show_passages:
                print(f"      \"{longest_passage(words, ow)[:160]}\"")
    if not flagged:
        print("  nothing above the thresholds")

    # 3. headings in common
    cand_heads = {heading_key(h) for h, _ in cand_secs}
    common = sorted({(heading_key(oh), ch) for ch, oh, _ in other_secs
                     if heading_key(oh) in cand_heads
                     and heading_key(oh) not in BOILERPLATE})
    print("\nheadings in common (the book's standard sections left out)")
    if common:
        for h, ch in common:
            print(f"  \"{h}\" also a section of {ch}")
    else:
        print("  none")
    return 1 if clashes else 0


if __name__ == "__main__":
    sys.exit(main())
