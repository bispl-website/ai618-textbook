# Chapter 11 -- the three experiments

The experiments of *Accelerated Posterior Sampling and Classifier-Free
Guidance* (chapter 11), from the scribe note of Junyeong Ahn for AI618 lecture
10, reproduced as submitted. NumPy only; no other dependency, no GPU.

| file | experiment | run time on one CPU core |
|:--|:--|:--|
| `exp1-cg-early-stopping.py` | early stopping of conjugate gradient makes it a regulariser | about 3 s |
| `exp2-krylov-hypothesis.py` | where the Krylov hypothesis holds, and what leaving the tangent space costs | 4 to 9 minutes |
| `exp3-cfg-cfgpp.py` | CFG against CFG++ on a Gaussian mixture with exact scores | about 10 s |

Each `.out.txt` is the printed output of the file beside it, as it appears in
the chapter's tables. The matplotlib scripts that draw the chapter's figures
from these results are not included.

The chapter prints the conjugate-gradient loop itself, in the section *The
conjugate-gradient step in code*.
