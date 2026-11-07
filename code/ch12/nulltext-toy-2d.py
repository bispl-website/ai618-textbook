"""
Null-text inversion in two dimensions -- chapter 12, the worked example in
"Null-text inversion: editing real images under guidance".

A four-component Gaussian mixture in the plane, for which the exact noise
predictor is available in closed form, so every claim of Mokady et al. can be
checked numerically without a trained network. Prints the four reconstruction
errors of the chapter's table.

From the scribe note of Tran Dinh Phu for AI618 lecture 11, reproduced as
submitted. Needs PyTorch. The plotting code for the figure is not included.
"""
import math
import torch
torch.set_default_dtype(torch.float64)

MU = torch.tensor([[2.0, 2.0], [2.5, -1.0], [-2.0, 1.5], [-1.5, -2.0]])
S = 0.5                                           # std of every component
CLASS = torch.tensor([0, 0, 1, 1])                # class of each component
# 'null embedding' phi = (four mixture logits, common shift of the means)
PHI0 = torch.cat([torch.log(torch.full((4,), 0.25)), torch.zeros(2)])
abar_all = torch.cumprod(1 - torch.linspace(1e-4, 0.02, 1000), 0)
ABAR = abar_all[torch.arange(0, 1000, 20)].tolist()   # 50-step DDIM grid

def eps_mix(x, a, logits, shift):
    """Exact E[eps | x_t = x] when x_0 follows a Gaussian mixture."""
    var = a * S**2 + (1 - a)
    diff = x[None] - math.sqrt(a) * (MU + shift[None])
    logp = logits - diff.pow(2).sum(1) / (2 * var)
    r = torch.softmax(logp, 0)
    return math.sqrt(1 - a) * (r[:, None] * diff).sum(0) / var

def eps_cond(x, a):                               # condition C = class 0
    logits = torch.where(CLASS == 0, PHI0[:4], torch.tensor(-math.inf))
    return eps_mix(x, a, logits, torch.zeros(2))

def eps_guided(x, a, w, phi):            # w eps(C) + (1 - w) eps(null)
    if w == 1.0:
        return eps_cond(x, a)
    return w * eps_cond(x, a) + (1 - w) * eps_mix(x, a, phi[:4], phi[4:])

def ddim(x, a_from, a_to, e):
    x0 = (x - math.sqrt(1 - a_from) * e) / math.sqrt(a_from)
    return math.sqrt(a_to) * x0 + math.sqrt(1 - a_to) * e

def invert(x0, w):
    traj = [x0]
    for i in range(len(ABAR) - 1):
        e = eps_guided(traj[-1], ABAR[i], w, PHI0)
        traj.append(ddim(traj[-1], ABAR[i], ABAR[i + 1], e))
    return traj

def sample(xT, w, phis=None):
    x = xT
    for i in range(len(ABAR) - 1, 0, -1):
        phi = PHI0 if phis is None else phis[i]
        x = ddim(x, ABAR[i], ABAR[i - 1], eps_guided(x, ABAR[i], w, phi))
    return x

def null_text(pivot, w, n_inner=10, lr=0.03):
    """Algorithm 1 of Mokady et al.: per-step null parameters."""
    phis, z, phi = {}, pivot[-1].clone(), PHI0.clone()
    for i in range(len(ABAR) - 1, 0, -1):
        phi = phi.clone().requires_grad_(True)
        opt = torch.optim.Adam([phi], lr=lr)
        for _ in range(n_inner):
            e = eps_guided(z, ABAR[i], w, phi)
            z_new = ddim(z, ABAR[i], ABAR[i - 1], e)
            loss = (z_new - pivot[i - 1]).pow(2).sum()
            if loss.item() < 1e-8:
                break
            opt.zero_grad(); loss.backward(); opt.step()
        phis[i] = phi = phi.detach()
        with torch.no_grad():
            e = eps_guided(z, ABAR[i], w, phi)
            z = ddim(z, ABAR[i], ABAR[i - 1], e)
    return phis

x0, w = torch.tensor([1.55, 2.45]), 7.5
piv = invert(x0, 1.0)
err = lambda x: (x - x0).norm().item()
print("(a)", err(sample(piv[-1], 1.0)))                 # 0.088
print("(b)", err(sample(invert(x0, w)[-1], w)))         # 0.266
print("(c)", err(sample(piv[-1], w)))                   # 1.251
print("(d)", err(sample(piv[-1], w, null_text(piv, w))))  # 0.003
