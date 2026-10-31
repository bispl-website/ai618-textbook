"""
Early stopping of conjugate gradient -- chapter 11, the experiment in the
section 'Early stopping of conjugate gradient'.

From the scribe note of Junyeong Ahn for AI618 lecture 10, reproduced as
submitted. NumPy only. The printed output is in the .out.txt file beside
this one; the matplotlib plotting scripts are not included.
"""
import numpy as np
n = 128; i = np.arange(n); t = i/n
dist = (i[:, None] - i[None, :] + n/2) % n - n/2
A = np.exp(-0.5*dist**2/2.0**2); A /= A.sum(1, keepdims=True)   # blur
Us, s, Vt = np.linalg.svd(A); B = A.T @ A

def problem(seed, sig=0.01):            # truth, data, Tweedie-like start
    rng = np.random.default_rng(seed)
    x = sum(rng.uniform(0.3, 1)*np.sin(2*np.pi*f*t + p)
            for f, p in zip(rng.integers(1, 4, 3), rng.uniform(0, 6.28, 3)))
    x = x + 0.6*(abs(t - rng.uniform(0.2, 0.8)) < 0.08)
    y = A @ x + sig*rng.normal(size=n)
    e = np.convolve(rng.normal(size=n), np.ones(9)/9, mode="same")
    return x, y, x + 0.056*np.linalg.norm(x)*e/np.linalg.norm(e)

def cg_path(y, xh, m=40):               # eq. (cg) on B x = A^T y
    x = xh.copy(); r = A.T @ y - B @ x; p = r.copy(); xs, rs = [x], [r]
    for _ in range(m):
        Bp = B @ p; a = (r @ r)/(p @ Bp); x = x + a*p
        rn = r - a*Bp; p = rn + (rn @ rn)/(r @ r)*p; r = rn
        xs.append(x); rs.append(r)
    return np.array(xs), np.array(rs)

def project(y, xh, rcond):              # eq. (ddnm), truncated pinv
    w = np.where(s >= rcond*s[0], 1/s, 0.0)
    return xh + Vt.T @ (w*(Us.T @ (y - A @ xh)))

rel = lambda x, x0: np.linalg.norm(x - x0, axis=-1)/np.linalg.norm(x0)
def evaluate(seeds, sig=0.01):
    E, R, O = [], [], []
    for sd in seeds:
        x, y, xh = problem(sd, sig); xs, rs = cg_path(y, xh)
        E.append(rel(xs, x))
        R.append(np.linalg.norm(y - xs @ A.T, axis=1)/np.linalg.norm(y))
        u = rs/np.linalg.norm(rs, axis=1, keepdims=True)
        G = np.abs(u @ u.T) - np.eye(len(u))
        O.append([G[:L+1, :L+1].max() for L in (5, 10, 20, 30, 40)])
    return np.array(E), np.array(R), np.array(O)

tune, test = range(0, 50), range(100, 300)
grid = list(np.linspace(0.95, 0.05, 19)) + list(np.geomspace(3e-2, 1e-12, 22))
def tr(seeds, rho, sig=0.01):
    return np.array([rel(project(y, xh, rho), x) for x, y, xh in
                     (problem(sd, sig) for sd in seeds)])
rho = min(grid, key=lambda r: tr(tune, r).mean())   # tune: seeds 0-49
l_star = int(np.argmin(evaluate(tune)[0].mean(0)))
E, R, O = evaluate(test)                      # report on seeds 100-299
se = lambda v: v.std(0, ddof=1)/np.sqrt(len(v))
def show(name, v): print(f"{name:26s} {v.mean():9.4f} +- {se(v):.4f}")
show("start x_hat", E[:, 0])
show("exact pseudo-inverse", tr(test, 1e-12))
show(f"truncated SVD (rho={rho:g})", tr(test, rho))
show("CG, l = 5", E[:, 5]); show(f"CG, l* = {l_star}", E[:, l_star])
show("CG, l = 40", E[:, 40])
print("mean error, l=0..6:", np.round(E.mean(0)[:7], 4))
print("mean residual, l=0,5,40:", np.round(R.mean(0)[[0, 5, 40]], 3))
print("max |cos| of residuals, L=5,10,20,30,40 (median):")
print("  ", " ".join("%.2g" % v for v in np.median(O, 0)))
d = E[:, l_star] - tr(test, rho)                      # paired difference
print(f"CG(l*) minus truncated SVD: {d.mean():+.4f} +- {se(d):.4f}")
print("noise   l*  CG(l*)  CG(l=5)  rho*  truncated SVD")      # sensitivity
for sig in (0.003, 0.01, 0.03):
    r = min(grid, key=lambda r: tr(tune, r, sig).mean())
    l = int(np.argmin(evaluate(tune, sig)[0].mean(0)))
    Es = evaluate(test, sig)[0]
    print(f"{sig:5.3f} {l:4d} {Es[:, l].mean():7.4f} {Es[:, 5].mean():8.4f}"
          f" {r:5g} {tr(test, r, sig).mean():9.4f}")
