"""
Symmetric and asymmetric shifts in DDIM -- chapter 12, the coefficients behind
Asyrp's cancellation result.

Evaluates the coefficient of a noise shift in the next state for a shift in
P_t alone and in both P_t and D_t, and their median ratio, on DDIM grids of
1000, 50, 20 and 10 steps.

From the scribe note of Tran Dinh Phu for AI618 lecture 11, reproduced as
submitted. Needs NumPy.
"""
import numpy as np

abar = np.cumprod(1 - np.linspace(1e-4, 0.02, 1000))   # cumulative alpha_t

for n in (1000, 50, 20, 10):
    g = np.arange(0, 1000, 1000 // n)
    a_t, a_p = abar[g[1:]], abar[g[:-1]]
    c_asym = -np.sqrt(a_p) * np.sqrt(1 - a_t) / np.sqrt(a_t)   # P_t only
    c_sym = np.sqrt(1 - a_p) + c_asym                          # P_t and D_t
    print(n, round(np.median(np.abs(c_sym) / np.abs(c_asym)), 4))
# 1000 0.0068 / 50 0.1248 / 20 0.2786 / 10 0.4866
