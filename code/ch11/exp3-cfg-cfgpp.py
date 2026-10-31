"""
CFG and CFG++ with exact scores -- chapter 11, the experiment in the section of
the same name.

From the scribe note of Junyeong Ahn for AI618 lecture 10, reproduced as
submitted. NumPy only. The printed output is in the .out.txt file beside
this one; the matplotlib plotting scripts are not included.
"""
import numpy as np
s, C = 0.35, 0                       # component spread, chosen component
ang = np.deg2rad([90, 210, 330])
MU = 2.0*np.stack([np.cos(ang), np.sin(ang)], 1)        # three modes
abar_all = np.cumprod(1 - np.linspace(1e-4, 0.02, 1000))
abar = lambda t: 1.0 if t < 0 else abar_all[t]
TS = np.linspace(999, 0, 50).round().astype(int)        # 50 DDIM steps

def eps_cond(x, ab):                 # exact noise prediction, condition c
    v = ab*s*s + 1 - ab
    return np.sqrt(1 - ab)*(x - np.sqrt(ab)*MU[C])/v

def eps_unc(x, ab):                  # exact noise prediction, mixture
    v = ab*s*s + 1 - ab
    d = x[:, None, :] - np.sqrt(ab)*MU[None]
    d2 = (d**2).sum(-1)
    w = np.exp(-(d2 - d2.min(1, keepdims=True))/(2*v))
    w /= w.sum(1, keepdims=True)
    return np.sqrt(1 - ab)*(w[..., None]*d).sum(1)/v

def sample(mode, k, x=None, N=2000, seed=0):
    """mode 'cfg' (scale omega) or 'pp' (CFG++, scale lambda)."""
    if x is None:
        x = np.random.default_rng(seed).normal(size=(N, 2))
    xhats = []
    for i, t in enumerate(TS):
        ab = abar(t)
        abn = abar(TS[i+1]) if i + 1 < len(TS) else 1.0
        e0, ec = eps_unc(x, ab), eps_cond(x, ab)
        e = e0 + k*(ec - e0)
        xh = (x - np.sqrt(1 - ab)*e)/np.sqrt(ab)        # Tweedie estimate
        xhats.append(xh)
        x = np.sqrt(abn)*xh + np.sqrt(1 - abn)*(e if mode == "cfg" else e0)
    return x, np.array(xhats)

def invert(x0, mode, k):
    """DDIM inversion, eq. (ddim-inv): eps(x_t) ~ eps(x_{t-1})."""
    x = x0.copy(); up = TS[::-1]                        # t = 0 -> 999
    for i in range(len(up) - 1):
        ap, ab = abar(up[i]), abar(up[i+1])
        e0 = eps_unc(x, ap) if up[i] > 0 else 0*x
        ec = eps_cond(x, ap) if up[i] > 0 else 0*x
        e = e0 + k*(ec - e0)
        xh = (x - np.sqrt(1 - ap)*(e if mode == "cfg" else e0))/np.sqrt(ap)
        x = np.sqrt(ab)*xh + np.sqrt(1 - ab)*e
    return x

def metrics(mode, k, seed):
    x, xh = sample(mode, k, seed=seed)
    st = np.linalg.norm(np.diff(xh, axis=0), axis=2)    # (49, N)
    rec, _ = sample(mode, k, x=invert(x, mode, k))      # re-sample
    return [np.linalg.norm(x.mean(0) - MU[C]), x.std(0).mean(),
            st.sum(0).mean(), st.max(0).mean(),
            np.linalg.norm(rec - x, axis=1).mean()]

SETTINGS = [("w=1", "cfg", 1), ("CFG w=3", "cfg", 3),
            ("CFG w=7.5", "cfg", 7.5), ("CFG w=12.5", "cfg", 12.5),
            ("CFG++ l=0.3", "pp", 0.3), ("CFG++ l=0.6", "pp", 0.6),
            ("CFG++ l=1", "pp", 1.0)]
if __name__ == "__main__":
    print("setting      overshoot  std    path  max-jump  inv-error")
    out = {}; worst = 0; res = {}
    for name, mode, k in SETTINGS:
        M = np.array([metrics(mode, k, sd) for sd in range(5)])
        m, e = M.mean(0), M.std(0, ddof=1)/np.sqrt(5)   # mean, s.e.
        out[name] = [m.tolist(), e.tolist()]
        print(f"{name:12s}" + "".join(f" {a:8.3f}" for a in m))
        worst = max(worst, e.max()); res[name] = M
    print(f"largest standard error over seeds: {worst:.3f}")
    W = [1, 1.5, 2, 3, 4, 5, 6, 7.5, 9, 10, 12.5]       # dense CFG grid
    dense = {w: np.array([metrics("cfg", w, sd) for sd in range(5)])
             for w in W}
    ov = np.array([dense[w][:, 0].mean() for w in W])
    print("inversion error, CFG++ minus CFG interpolated at equal overshoot:")
    for n in list(res)[4:]:
        d = np.array([res[n][s, 4] - np.interp(res[n][s, 0], ov,
                      [dense[w][s, 4] for w in W]) for s in range(5)])
        print(f"  {n}: {d.mean():+.4f} +- {d.std(ddof=1)/np.sqrt(5):.4f}")
    import json; json.dump(out, open("exp3.json", "w"))
