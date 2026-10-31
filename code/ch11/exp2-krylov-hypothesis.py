"""
When does the Krylov hypothesis hold? -- chapter 11, the experiment in the
section of the same name.

From the scribe note of Junyeong Ahn for AI618 lecture 10, reproduced as
submitted. NumPy only. The printed output is in the .out.txt file beside
this one; the matplotlib plotting scripts are not included.
"""
import numpy as np
d, h = 64, 12                                  # ambient dim, dim of M
k = np.arange(d)
cols = [np.ones(d)/np.sqrt(d)]
for q in range(1, h//2 + 1):                   # low-frequency Fourier modes
    cols += [np.sqrt(2/d)*np.cos(2*np.pi*q*k/d),
             np.sqrt(2/d)*np.sin(2*np.pi*q*k/d)]
U = np.stack(cols[:h], 1); P = U @ U.T         # M = span(U)
abar = np.cumprod(1 - np.linspace(1e-4, 0.02, 1000))

def make_A(kind, rng):
    if kind == "blur":                         # circulant: B maps M into M
        dist = (k[:, None] - k[None, :] + d/2) % d - d/2
        A = np.exp(-0.5*dist**2/1.5**2)
        return A/A.sum(1, keepdims=True)
    keep = np.sort(rng.choice(d, d//2, replace=False))
    return np.eye(d)[keep]                     # random pixel mask

def cg(Bop, b, x, m):                          # eq. (cg), warm start x
    r = b - Bop(x); p = r.copy()
    for _ in range(m):
        Bp = Bop(p); a = (r @ r)/(p @ Bp); x = x + a*p; rn = r - a*Bp
        if rn @ rn < 1e-24: break
        p = rn + (rn @ rn)/(r @ r)*p; r = rn
    return x

def data_step(method, xh, a, A, y, par, m=5):
    if method == "dps":                        # Jacobian sqrt(a) P
        return xh - par*np.sqrt(a)*(P @ (A.T @ (A @ xh - y)))
    if method == "ddnm":                       # hard projection, eq. (ddnm)
        return xh + np.linalg.pinv(A, rcond=par) @ (y - A @ xh)
    if par == 0:                               # DDS, noiseless: B x = A^T y
        return cg(lambda v: A.T @ (A @ v), A.T @ y, xh, m)
    return cg(lambda v: v + par*(A.T @ (A @ v)), xh + par*(A.T @ y), xh, m)

def reconstruct(method, A, y, T, par, rng, m=5):
    ts = np.linspace(999, 0, T).round().astype(int)
    x = rng.normal(size=d); leak = []
    for i, t in enumerate(ts):
        a = abar[t]; an = abar[ts[i+1]] if i + 1 < T else 1.0
        xh = np.sqrt(a)*(P @ x)                # exact Tweedie
        eps = (x - np.sqrt(a)*xh)/np.sqrt(1 - a)
        xd = data_step(method, xh, a, A, y, par, m)
        dx = xd - xh; nd = max(np.linalg.norm(dx), 1e-12)
        leak.append(np.linalg.norm(dx - P @ dx)/nd)
        x = np.sqrt(an)*xd + np.sqrt(1 - an)*eps          # DDIM renoise
    return xd, np.mean(leak)

def evaluate(kind, method, T, par, sigma, n, seed, m=5):
    rng = np.random.default_rng(seed); err, lk = [], []
    for _ in range(n):
        A = make_A(kind, rng); x0 = U @ rng.normal(size=h)
        y = A @ x0 + sigma*rng.normal(size=A.shape[0])
        xr, l = reconstruct(method, A, y, T, par, rng, m)
        err.append(np.linalg.norm(xr - x0)/np.linalg.norm(x0)); lk.append(l)
    return np.array(err), np.array(lk)

GRID = {"dps": [0.1, 0.3, 1, 3, 10, 30],
        "ddnm": [0.9, 0.7, 0.5, 0.3, 0.1, 1e-2, 1e-4],
        "dds": [0.1, 0.25, 0.5, 2, 8, 32, 128, 512, 2048]}
NFE = [10, 20, 50, 100]                        # network calls, same for all
steps = lambda method, nfe: nfe//2 if method == "dps" else nfe

def tuned(kind, method, nfe, sigma):           # tune: seed 1, report: seed 2
    T = steps(method, nfe)
    def score(g):
        return evaluate(kind, method, T, g, sigma, 100, 1)[0].mean()
    g = min(GRID[method], key=score)
    return g, evaluate(kind, method, T, g, sigma, 200, 2)[0]
se = lambda v: v.std(ddof=1)/np.sqrt(len(v))
def table(sigma, full=True):
    R = {(k, m, n): tuned(k, m, n, sigma) for k in ("blur", "mask")
         for m in ("dps", "ddnm", "dds") for n in NFE}
    print(f"sigma_y = {sigma}; relative error, mean +- s.e. (200 problems)")
    print("operator       NFE=10        20            50            100")
    for kind in ("blur", "mask"):
        for m in ("dps", "ddnm", "dds"):
            row = "".join(f"  {R[kind, m, n][1].mean():.3f}+-"
                          f"{se(R[kind, m, n][1]):.3f}" for n in NFE)
            print(f"{kind} {m:5s}" + row)
        if full:                                   # paired differences
            for a, b in (("dds", "dps"), ("dds", "ddnm")):
                D = [R[kind, a, n][1] - R[kind, b, n][1] for n in NFE]
                row = "".join(f" {v.mean():+.4f}({se(v):.4f})" for v in D)
                print(f"{kind} {a}-{b:4s}" + row)
        for m in ("dps", "ddnm", "dds"):           # tuned parameters
            print(f"{kind} {m:5s} tuned:", [R[kind, m, n][0] for n in NFE])
    return R
R = table(0.02)
print("leakage of the data step, mean over steps and problems (T = 20)")
for kind in ("blur", "mask"):
    for sigma, par in ((0.0, 0), (0.02, 2)):
        L = [evaluate(kind, "dds", 20, par, sigma, 200, 3, m=m)[1].mean()
             for m in (1, 2, 5, 10)]
        print(f"{kind} DDS sigma={sigma}: m=1,2,5,10 ->", np.round(L, 3))
    for sigma in (0.0, 0.02):
        lk = evaluate(kind, "ddnm", 20, R[kind, "ddnm", 20][0], sigma,
                      200, 3)[1]
        print(f"{kind} DDNM sigma={sigma}: {lk.mean():.3f}")
e = evaluate("blur", "ddnm", 50, 1e-12, 0.02, 200, 2)[0]     # exact pinv
print(f"blur DDNM, exact pseudo-inverse: {e.mean():.0f}+-{se(e):.0f}")
table(0.1, full=False)
