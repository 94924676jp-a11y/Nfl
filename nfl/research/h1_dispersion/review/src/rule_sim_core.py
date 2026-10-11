"""Task 4: sampling behaviour of the frozen harm rules (decile MAE change <= +2 %, position <= +1 %)."""
import json, sys
import numpy as np, pandas as pd
sys.path.insert(0, '/tmp/claude-0/h1review/src')
from lib import *



def strata_changes(proj, cand, act, pos, idx):
    """% MAE change by pooled projection decile (deciles re-formed on these rows, by production proj)
    and by position, for the row subset idx."""
    p, c, a, ps = proj[idx], cand[idx], act[idx], pos[idx]
    ep, ec = np.abs(p - a), np.abs(c - a)
    order = np.argsort(p, kind='stable'); n = len(order)
    lab = np.empty(n, int)
    for k in range(10):
        lab[order[k * n // 10:(k + 1) * n // 10]] = k
    sp = np.bincount(lab, ep, 10); sc = np.bincount(lab, ec, 10)
    dec = (sc / sp - 1) * 100
    posc = np.array([(ec[ps == q].sum() / ep[ps == q].sum() - 1) * 100 for q in POS])
    return dec, posc


