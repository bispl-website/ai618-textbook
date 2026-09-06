# Generative Models and Unsupervised Learning

An open textbook built from the scribe notes of **KAIST AI618**. One Quarto
source, rendered to [HTML](https://bispl-website.github.io/ai618-textbook/) and PDF.

Licensed **CC BY 4.0** — share and adapt, including commercially, with
attribution.

## Where the chapters come from

Students in AI618 write up one lecture each. Three or four write up the same
lecture independently, the notes are graded against a published rubric, and the
strongest becomes the base for a chapter here. The notes themselves live in a
separate private repository (`ai618-scribe-2026f`) — private, because students
scribing the same lecture would otherwise read each other's drafts.

Chapters are **merged, not copied.** With only a handful of write-ups per
lecture, the best one still has holes; the grading pass produces an explicit
list of them, and `scripts/promote.py` turns that list into a merge worksheet.

```bash
# after a lecture has been graded in the scribe repository
python scripts/promote.py --lecture 07 --scribe-repo ../ai618-scribe-2026f
```

That writes `drafts/lec07-merge.md` (ranking, gap union, suspected errors — git
-ignored, it contains per-student detail) and seeds `chapters/ch07.qmd` from the
top note with a TODO at every gap. Both are starting points; a human does the
merge.

## Building

```bash
quarto render          # both formats into _book/
quarto preview         # live HTML preview while editing
```

The PDF build needs a LaTeX installation — `quarto install tinytex` if you do
not have one.

**Always build both formats before pushing.** Raw HTML, SVG figures, and
non-ASCII characters render fine in HTML and break the PDF, which is why the
scribe repository rejects all three at submission time. If you write a chapter
by hand, the same three rules apply.

## Layout

```
_quarto.yml              book definition, both output formats
index.qmd                preface
chapters/chNN.qmd        one per lecture; stubs until promoted
references.bib           shared bibliography — cite into it, not inline
figures/                 figures used across chapters; PDF or PNG, no SVG
drafts/                  merge worksheets (git-ignored)
scripts/promote.py       grades -> merge worksheet + seeded chapter
```

## Contributing

Corrections from outside the course are welcome. Open an issue or a pull
request; if you are reporting a mathematical error, quote the statement and say
why it is wrong.
