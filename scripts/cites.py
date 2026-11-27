"""Reconcile a merged chapter's citation keys with references.bib.

A scribe note carries its own bibliography in its front matter, under keys its
author chose -- `@cm`, `@meanflow`, `@slides`. `promote.py` keeps the body and
drops the front matter, so a chapter merged from three notes cites twenty keys
this book does not define, and Quarto renders every one of them as `[?]` and
exits 0. Chapter 17 reached the render gate that way with 22 of them.

For each key the chapter cites and `references.bib` does not have:

1. find the entry in the lecture's notes (their `references:` front matter);
2. if the book already holds the same work -- same arXiv id, same DOI, or the
   same title -- rewrite the citation to the book's key. `@cm` becomes
   `@song2023consistency`; a note's `@slides` becomes the deck's
   `@lecture-slides-*` entry;
3. otherwise append the note's entry to references.bib, as BibTeX, under the
   note's key;
4. a key found nowhere is blocking: nothing can be guessed for it.

Called from chapter_fix.py, which owns the dry run / --apply switch.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import yaml

KINDS = ("eq", "sec", "fig", "tbl", "def", "prp", "thm", "lem",
         "exm", "cor", "rem", "alg", "lst")
CITE = re.compile(r"(?<![\w@.])@([A-Za-z0-9_][\w:.#$%&+?<>~/-]*[A-Za-z0-9_])")
FENCE = re.compile(r"(?ms)^```.*?^```[ \t]*$")
COMMENT = re.compile(r"(?s)<!--.*?-->")
INLINE_CODE = re.compile(r"`[^`\n]*`")
BIB_ENTRY = re.compile(r"(?m)^@(\w+)\s*\{\s*([^,\s]+)\s*,")
ARXIV = re.compile(r"(\d{4}\.\d{4,5})")


def cited_keys(text: str) -> list[str]:
    body = FENCE.sub("", COMMENT.sub("", text))
    body = INLINE_CODE.sub("", body)
    out = []
    for k in CITE.findall(body):
        if k.split("-", 1)[0] in KINDS and "-" in k:
            continue
        if k not in out:
            out.append(k)
    return out


def norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())


def words(t: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (t or "").lower()) if len(w) > 2}


def bib_index(bib: str) -> dict[str, dict]:
    """key -> {title, arxiv, doi} for every entry in references.bib."""
    out: dict[str, dict] = {}
    starts = [m for m in BIB_ENTRY.finditer(bib)]
    for i, m in enumerate(starts):
        chunk = bib[m.start(): starts[i + 1].start() if i + 1 < len(starts) else len(bib)]

        def field(name: str) -> str:
            f = re.search(rf"(?im)^\s*{name}\s*=\s*[{{\"](.+?)[}}\"]\s*,?\s*$", chunk)
            return f.group(1) if f else ""
        ax = ARXIV.search(field("eprint") + " " + field("url") + " " + field("journal"))
        out[m.group(2)] = {"type": m.group(1).lower(),
                           "title": field("title").replace("{", "").replace("}", ""),
                           "arxiv": ax.group(1) if ax else "",
                           "doi": field("doi").lower()}
    return out


def note_items(scribe: Path, lec: str) -> dict[str, list[dict]]:
    """id -> the CSL items the lecture's notes define under it."""
    out: dict[str, list[dict]] = {}
    for qmd in sorted((scribe / "lectures" / lec / "submissions").glob("*.qmd")):
        text = qmd.read_text(encoding="utf-8")
        m = re.match(r"(?s)---\n(.*?)\n---\n", text)
        if not m:
            continue
        try:
            fm = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            continue
        for it in fm.get("references") or []:
            if isinstance(it, dict) and it.get("id"):
                it = dict(it, _from=qmd.stem)
                out.setdefault(str(it["id"]), []).append(it)
    return out


def item_arxiv(it: dict) -> str:
    blob = " ".join(str(it.get(k, "")) for k in ("URL", "url", "arxiv", "note",
                                                  "container-title", "number"))
    m = ARXIV.search(blob)
    return m.group(1) if m else ""


def is_slides(key: str, it: dict) -> bool:
    blob = f"{key} {it.get('type', '')} {it.get('title', '')} {it.get('note', '')}".lower()
    return "slide" in blob or it.get("type") == "speech"


def match_existing(key: str, it: dict, idx: dict[str, dict]) -> str | None:
    ax, doi = item_arxiv(it), str(it.get("DOI", "")).lower()
    title = str(it.get("title", ""))
    for k, e in idx.items():
        if ax and e["arxiv"] == ax:
            return k
        if doi and e["doi"] == doi:
            return k
        if title and norm_title(e["title"]) == norm_title(title):
            return k
    if is_slides(key, it):
        want = words(title)
        best, score = None, 0.0
        for k, e in idx.items():
            if not k.startswith("lecture-slides"):
                continue
            got = words(e["title"])
            s = len(want & got) / max(1, len(want))
            if s > score:
                best, score = k, s
        if best and score >= 0.8:
            return best
    return None


def ascii(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    return s.encode("ascii", "ignore").decode("ascii")


def to_bibtex(key: str, it: dict) -> str:
    kind = {"paper-conference": "inproceedings", "article-journal": "article",
            "book": "book", "chapter": "incollection"}.get(it.get("type", ""), "misc")
    names = []
    for a in it.get("author") or []:
        if isinstance(a, dict) and a.get("literal"):
            names.append("{" + ascii(a["literal"]) + "}")
        elif isinstance(a, dict):
            names.append(ascii(f"{a.get('given', '')} {a.get('family', '')}".strip()))
        else:
            names.append(ascii(a))
    issued = it.get("issued") or {}
    year = ""
    if isinstance(issued, dict):
        year = issued.get("year") or ((issued.get("date-parts") or [[""]])[0][0])
    fields = [("author", " and ".join(n for n in names if n)),
              ("title", "{" + ascii(it.get("title", "")) + "}")]
    venue = ascii(it.get("container-title", ""))
    if venue:
        fields.append(("booktitle" if kind == "inproceedings" else "journal"
                       if kind == "article" else "howpublished", venue))
    fields.append(("year", str(year)))
    ax = item_arxiv(it)
    if ax:
        fields += [("eprint", ax), ("archivePrefix", "arXiv")]
    elif it.get("URL"):
        fields.append(("url", ascii(it["URL"])))
    if it.get("DOI"):
        fields.append(("doi", ascii(it["DOI"])))
    body = ",\n".join(f"  {k:<13} = {{{v}}}" for k, v in fields if v)
    return f"@{kind}{{{key},\n{body}\n}}\n"


def reconcile(text: str, lec: str, scribe: Path, bib: str
              ) -> tuple[str, str, list[str], list[str]]:
    """(new chapter text, BibTeX to append, fixed lines, blocking lines)."""
    idx = bib_index(bib)
    items = note_items(scribe, lec)
    fixed, blocking, append = [], [], []
    for key in cited_keys(text):
        if key in idx:
            continue
        cands = items.get(key) or []
        if not cands:
            blocking.append(f"cites `@{key}`, which is neither in references.bib "
                            "nor in any of this lecture's notes")
            continue
        it = cands[0]
        if len({norm_title(c.get('title', '')) for c in cands}) > 1:
            fixed.append(f"`@{key}` means different works in different notes; "
                         f"took {it['_from']}'s ({it.get('title', '')!s:.60})")
        to = match_existing(key, it, idx)
        if to:
            text = re.sub(r"(?<![\w@.])@" + re.escape(key) + r"(?![\w:.#$%&+?<>~/-]*[A-Za-z0-9_])",
                          "@" + to, text)
            fixed.append(f"cited `@{key}` as `@{to}`, the book's key for the same work")
        else:
            append.append(to_bibtex(key, it))
            idx[key] = {"type": "", "title": str(it.get("title", "")),
                        "arxiv": item_arxiv(it), "doi": ""}
            fixed.append(f"added `@{key}` to references.bib "
                         f"({ascii(it.get('title', ''))[:60]}, from {it['_from']})")
    bibtext = ""
    if append:
        bibtext = (f"\n% --- {lec} additions, from the scribe notes' own references "
                   "(scripts/cites.py) ---\n" + "\n".join(append))
    return text, bibtext, fixed, blocking
