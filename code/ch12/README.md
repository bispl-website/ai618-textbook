# Chapter 12 -- the worked examples

The experiments of *Diffusion Model Applications: Image Editing* (chapter 12),
from the scribe note of Tran Dinh Phu for AI618 lecture 11, reproduced as
submitted.

| file | what it computes | needs | run time |
|:--|:--|:--|:--|
| `nulltext-toy-2d.py` | null-text inversion on a 2-D Gaussian mixture with exact noise predictors; prints the four reconstruction errors of the chapter's table | PyTorch | seconds, CPU |
| `asyrp-shift-coefficients.py` | the coefficient of a noise shift in the next DDIM state, for a shift in the predicted image alone and in both terms, on grids of 1000, 50, 20 and 10 steps | NumPy | instant |

Expected output of the first is `(a) 0.088`, `(b) 0.266`, `(c) 1.251`,
`(d) 0.003`; of the second, `1000 0.0068`, `50 0.1248`, `20 0.2786`,
`10 0.4866`.

The chapter prints the exact mixture predictor that the first script is built
around, in the section *How the worked examples were run*. The attention
processor behind the chapter's two Stable Diffusion figures is not included;
that section describes its settings.

The plotting scripts are not included.
