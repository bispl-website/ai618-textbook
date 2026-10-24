# DDIM material from the lecture 07 notes, waiting for chapter 6

Lecture 07 opens with the DDIM construction (slides 17-25), but the book puts
that construction next to DDPM in `@sec-ddim` of chapter 6, by the instructor's
decision of 2026-10-16. So when chapter 7 was merged on 2026-10-25 the DDIM
section came out of it: 1,556 words of `HaJunHyun`, plus these three figures.

Chapter 6 already covers every result that section covered, one for one, and
chapter 7 now cross-references chapter 6 instead:

| lecture 07 note | chapter 6 |
|---|---|
| Is the Markov property necessary? | `### Motivation: is the Markov property needed?` |
| A non-Markovian forward process | `### The non-Markovian forward family` |
| The marginals do not change | `## Marginal preservation` |
| The training objective | `@sec-ddim-objective` |
| The sampling step | `### The generative step`, `@sec-denoise-renoise` |
| The eta-parameterized family | `@sec-ddim-exact`, `## Reduction to DDPM` |
| accelerated sampling on a subsequence | `@sec-skip` |

So nothing is *missing* from the book. What is open is whether any of the
lecture 07 writing is better than what chapter 6 has, which is a question about
two finished texts and is deliberately left for a separate pass over chapter 6.
That pass should also weigh `deb-kit2`, whose DDIM half is 1,769 words and the
densest original work in that note -- it carries a worked two-step numerical
check and a justified correction to the slides' subscript.

Chapter 6's credit line must name the lecture 07 scribes whose material is used.

The figures here are referenced by no chapter and are kept only for that pass:

- `HaJunHyun-slide18-graphical.pdf` -- DDPM and DDIM graphical models, slide 18
- `HaJunHyun-ddim-eta.pdf` -- the eta family on the two-mode example
- `HaJunHyun-slide24-decomposition.pdf` -- the geometry of one reverse step
