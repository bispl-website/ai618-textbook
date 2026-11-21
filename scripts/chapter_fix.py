#!/usr/bin/env python3
"""The mechanical half of a chapter merge, done by machine.

`promote.py` seeds a chapter from the strongest scribe note and stops. What
follows is a merge by hand -- which material to fold in, what to prove, what
to cut -- and then a fixed list of chores that have nothing to do with
judgement and every time cost an editor a dozen turns:

* figures referenced as `.pdf`, which the HTML build does not take, so the
  published page shows a broken image while the PDF build is green;
* figures pulled in from another scribe's note, which `promote.py` never
  copied because it only copies the base note's;
* the `::: {#refs}` div every submission carries, which in a book with one
  bibliography puts a second reference list in the middle of the chapter;
* `promote.py`'s own Draft callout and its placeholder credit line of GitHub
  logins, which is not what the book credits people by;
* crossref labels that collide with a chapter already in the book. This is
  the one that does not announce itself: Quarto resolves a duplicate `@eq-dsm`
  to one of the two definitions, silently, and the chapter that loses is
  usually the earlier one. Chapter 14 arrived with thirteen such labels.
* non-ASCII characters, which the lualatex build fails on. Every chapter in
  the book is pure ASCII today and this keeps it that way.

None of that needs an editor and none of it needs a model. Default is a dry
run; `--apply` writes. Anything the script cannot do without a decision --
which prefix to rename a clashing label with, which notes actually fed the
merge -- it refuses rather than guesses, and says what to pass.

Usage:
    python scripts/chapter_fix.py --lecture 14
    python scripts/chapter_fix.py --lecture 14 --prefix reflow --apply
    python scripts/chapter_fix.py --lecture 14 --base yeonwoo378 \\
           --materials tejava317,finallyupper --apply
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from promote import chapter_for  # noqa: E402  (same directory, by design)

REPO = Path(__file__).resolve().parent.parent

# The crossref kinds Quarto resolves in this book. A fixed list, so that a
# citation key (`@lipman2024guide`) is never mistaken for a crossref.
KINDS = ("eq", "sec", "fig", "tbl", "def", "prp", "thm", "lem",
         "exm", "cor", "rem", "alg", "lst")
LABEL_DEF = re.compile(r"\{#(" + "|".join(KINDS) + r")-([A-Za-z0-9_-]+)")
LINK = re.compile(r"\]\(([^)\s]+)\)")
DRAFT_CALLOUT = re.compile(
    r"\n*::: *\{\.callout-important\}\s*\n#+ *Draft\n.*?\n::: *\n", re.S)
# `template.qmd` writes the div over two lines and every submission copies it,
# so the closing `:::` is on its own line; the one-line form also occurs.
REFS_DIV = re.compile(r"\n*(?:#+ *References *\n+)?::: *\{#refs\}\s*:::[ \t]*\n", re.I)
PLACEHOLDER_CREDIT = re.compile(
    r"\n*---\s*\n+\*Scribe notes for this lecture:[^\n]*\*\s*\n*\Z")
CREDIT = re.compile(r"\*Based on the scribe note of (.+?)\. Edited by [^*]+\*", re.S)
SEEDED_COMMENT = "DRAFT seeded by scripts/promote.py"


def roster_credits(scribe_repo: Path) -> dict[str, str]:
    """GitHub login -> the spelling the book credits that person by."""
    import yaml
    path = scribe_repo / "roster.yml"
    if not path.exists():
        raise SystemExit(
            f"no roster at {path}. It is the only record of how a scribe's "
            "name is spelled in print; a credit line guessed from a GitHub "
            "login is a misspelled name on a public page. Pass --scribe-repo.")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = {}
    for s in data.get("students") or []:
        if isinstance(s, dict) and s.get("github"):
            out[s["github"]] = (s.get("credit") or s.get("name") or "").strip()
    return out


def credit_line(base: str, materials: list[str], who: dict[str, str]) -> str:
    def name(login: str) -> str:
        n = who.get(login)
        if not n:
            raise SystemExit(
                f"{login} is not in the roster, so there is no spelling to "
                "credit them by. Check the login, or add them to roster.yml.")
        return n
    names = [name(m) for m in materials]
    if not names:
        tail = ""
    elif len(names) == 1:
        tail = f", with the materials from {names[0]}"
    else:
        tail = (", with the materials from "
                + ", ".join(names[:-1]) + f" and {names[-1]}")
    return (f"*Based on the scribe note of {name(base)}{tail}. "
            "Edited by Jong Chul Ye.*")


def other_labels(target: Path) -> dict[str, str]:
    """Every crossref label defined by a chapter other than this one."""
    out: dict[str, str] = {}
    for qmd in sorted((REPO / "chapters").glob("*.qmd")) + [REPO / "index.qmd"]:
        if not qmd.exists() or qmd.resolve() == target.resolve():
            continue
        for kind, rest in LABEL_DEF.findall(qmd.read_text(encoding="utf-8")):
            out.setdefault(f"{kind}-{rest}", qmd.name)
    return out


def rename_labels(text: str, labels: list[str], prefix: str) -> tuple[str, int]:
    n = 0
    for label in labels:
        kind, rest = label.split("-", 1)
        new = f"{kind}-{prefix}-{rest}"
        pat = re.compile(r"(\{#|@)" + re.escape(label) + r"(?![\w-])")
        text, k = pat.subn(lambda m: m.group(1) + new, text)
        n += k
    return text, n


def main() -> int:  # noqa: C901  (a checklist; splitting it hides the order)
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lecture", required=True, help="lecture number, e.g. 14")
    ap.add_argument("--scribe-repo", default="../ai618-scribe-2026f",
                    help="checkout holding roster.yml and the notes' figures")
    ap.add_argument("--prefix", help="rename clashing labels with this prefix, "
                                     "e.g. --prefix reflow gives eq-reflow-dsm")
    ap.add_argument("--base", help="GitHub login of the note the chapter is built on")
    ap.add_argument("--materials", default="",
                    help="comma-separated logins whose material was folded in")
    ap.add_argument("--apply", action="store_true", help="write the changes")
    args = ap.parse_args()

    lec = args.lecture if args.lecture.startswith("lec") else f"lec{int(args.lecture):02d}"
    chapter, _also, _note = chapter_for(lec)
    scribe_repo = (REPO / args.scribe_repo).resolve()
    text = original = chapter.read_text(encoding="utf-8")
    rel = chapter.relative_to(REPO)
    print(f"{rel}  ({lec})\n")

    fixed: list[str] = []
    blocking: list[str] = []

    # 1. promote.py's scaffolding ------------------------------------------
    text, k = DRAFT_CALLOUT.subn("\n", text)
    if k:
        fixed.append("removed the Draft callout")
    if SEEDED_COMMENT in text:
        blocking.append(
            "the comment promote.py seeded is still in the file. It names the "
            "merge sources and tells the editor what to do, and it ships in "
            "the page source -- replace it with the chapter's provenance "
            "comment before publishing.")

    # 2. the submission's own reference list --------------------------------
    text, k = REFS_DIV.subn("\n", text)
    if k:
        fixed.append("removed the `::: {#refs}` div (the book has one bibliography)")

    # 3. figures -------------------------------------------------------------
    figdir = REPO / "chapters" / "figures" / lec
    srcdir = scribe_repo / "lectures" / lec / "figures"
    refs = [p for p in LINK.findall(text) if p.startswith("figures/")]
    pdf_refs = [p for p in refs if p.lower().endswith(".pdf")]
    for p in pdf_refs:
        text = text.replace(p, p[:-4] + ".png")
    if pdf_refs:
        fixed.append(f"repointed {len(pdf_refs)} figure(s) from .pdf to .png "
                     "(the HTML build takes PNG only)")
    for p in refs:
        if p.lower().endswith(".svg"):
            blocking.append(f"{p} is an SVG; the PDF build does not take it")

    refs = [p for p in LINK.findall(text) if p.startswith("figures/")]
    for p in sorted(set(refs)):
        dest = REPO / "chapters" / p
        if dest.exists():
            continue
        name = Path(p).name
        cand = srcdir / name
        pdf = cand.with_suffix(".pdf")
        if cand.exists():
            if args.apply:
                figdir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(cand, dest)
            fixed.append(f"copied {name} from the scribe repo")
        elif name.lower().endswith(".png") and pdf.exists():
            try:
                import fitz  # pymupdf
            except ImportError:
                blocking.append(f"{name} exists only as a PDF and pymupdf is "
                                "not importable, so it cannot be rasterised")
                continue
            if args.apply:
                figdir.mkdir(parents=True, exist_ok=True)
                doc = fitz.open(pdf)
                doc[0].get_pixmap(dpi=300).save(dest)
                doc.close()
            fixed.append(f"rasterised {pdf.name} to {name} at 300 dpi")
        else:
            blocking.append(f"{p} is referenced and is in neither this "
                            f"repository nor {srcdir.name}/; the published "
                            "page would show a broken image")

    # 4. the credit line -----------------------------------------------------
    who = roster_credits(scribe_repo)
    text, k = PLACEHOLDER_CREDIT.subn("\n", text)
    if k:
        fixed.append("removed promote.py's placeholder credit line of logins")
    if args.base:
        mats = [m.strip() for m in args.materials.split(",") if m.strip()]
        line = credit_line(args.base, mats, who)
        text = CREDIT.sub("", text).rstrip()
        text = re.sub(r"\n+---\s*\Z", "", text).rstrip() + f"\n\n---\n\n{line}\n"
        fixed.append("wrote the credit line from the roster's spellings")
    else:
        m = CREDIT.search(text)
        if not m:
            blocking.append(
                "no credit line. Every chapter ends with one, after a `---`; "
                "pass --base LOGIN (and --materials) to have it written from "
                "the roster.")
        else:
            spelled = set(who.values())
            said = re.split(r",| and |with the materials from ",
                            m.group(1).replace("\n", " "))
            for part in (s.strip() for s in said):
                if part and part not in spelled:
                    blocking.append(
                        f"the credit line says {part!r}, which is not a "
                        "spelling in the roster -- check it before this goes "
                        "on a public page")
            if not text.rstrip().endswith(m.group(0).strip()):
                blocking.append("the credit line is not the last thing in the "
                                "chapter; at the top it reads as a byline")

    # 5. label clashes -------------------------------------------------------
    mine = {f"{k_}-{r}" for k_, r in LABEL_DEF.findall(text)}
    theirs = other_labels(chapter)
    clashes = sorted(mine & set(theirs))
    if clashes:
        if args.prefix:
            text, n = rename_labels(text, clashes, args.prefix)
            fixed.append(f"renamed {len(clashes)} clashing label(s) with "
                         f"'{args.prefix}' ({n} occurrences)")
        else:
            where = ", ".join(f"{c} (also in {theirs[c]})" for c in clashes[:6])
            blocking.append(
                f"{len(clashes)} label(s) are already defined elsewhere in the "
                f"book: {where}{' ...' if len(clashes) > 6 else ''}. Quarto "
                "resolves a duplicate silently, so one of the two chapters "
                "loses its reference. Pass --prefix to rename this chapter's.")

    # 6. non-ASCII -----------------------------------------------------------
    for i, line in enumerate(text.splitlines(), 1):
        for j, ch in enumerate(line, 1):
            if ord(ch) > 127:
                blocking.append(
                    f"non-ASCII {ch!r} (U+{ord(ch):04X}) at {rel}:{i}:{j}; "
                    "the lualatex build fails on it")
                break

    verb = "fixed   " if args.apply else "would fix"
    for f in fixed:
        print(f"  {verb} {f}")
    for b in blocking:
        print(f"  BLOCKING {b}")
    if not fixed and not blocking:
        print("  nothing to do.")

    if text != original:
        if args.apply:
            chapter.write_text(text, encoding="utf-8")
            print(f"\nwrote {rel}")
        else:
            print(f"\n{len(fixed)} change(s) not written. Re-run with --apply.")
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
