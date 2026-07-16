"""The Hush core, ported — spatio-temporal NR for the pipelines that make
noise worse (Pivot punch-ins, Rise super-resolution).

This is a faithful vectorized port of the reference implementation in
Hush-OpenNR `plugin/nr_core.h` (MIT, same author): the noise estimator
(fine + coarse |Laplacian| + |temporal diff| medians, brightness-dependent
gain curve), the hard-knee gated 3-frame temporal merge with Ghost Guard and
per-neighbour exposure offsets, the two-scale residual re-measure, and the
fine NLM spatial band (3x3 patches, bias-corrected, edge-aware Preserve
Detail). Constants and defaults match Hush v3.x.

Honestly NOT ported (they live in the plugin): hierarchical shift-search
motion tracking, the firefly zapper, Render Boost history, Deep Clean, the
medium/coarse/blotch EQ bands, deband, and the whole refine texture stack.
The report from every caller names this backend "hush-core" — never plain
"Hush".

Everything runs on float32 [0,1] YCbCr (BT.709 ratios, exactly rgb2ycc in
nr_core.h) and is deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# --- constants (nr_core.h, verbatim) -----------------------------------------
K_MEDIAN_CAL = 1.0 / (6.0 * 0.674490)        # Immerkaer, median
K_Q35_CAL = 1.0 / (6.0 * 0.453762)           # Immerkaer, Q35
K_MEDIAN_CAL_T = 1.0 / (0.674490 * 1.414214)  # |frame diff| median
K_Q20_CAL_T = 1.0 / (0.253347 * 1.414214)     # |frame diff| Q20
K_ABS_DIFF_BIAS = 1.128379                    # E|a-b| = 2 sigma / sqrt(pi)
K_NLM_H_LUMA = 1.15
K_NLM_H_CHROMA = 2.20
K_HIST_BINS = 256
K_HIST_SCALE_Y = 512.0
K_HIST_SCALE_C = 1024.0
K_LUMA_BINS = 16
K_LUMA_SUB = 64
K_LUMA_SUB_SCALE_Y = 128.0
K_LUMA_SUB_SCALE_C = 256.0
K_SIGMA_MIN = 1e-4
K_SIGMA_MAX = 0.25
K_EXP_BINS = 128
K_EXP_SCALE = 256.0
K_EXP_DEAD = 0.006

_LAP_KERNEL = None  # built lazily (numpy import stays optional at module load)


@dataclass
class HushParams:
    """Hush's own defaults (nr_core.h Params); master is the one-knob trim."""

    temporal_luma: float = 0.6
    temporal_chroma: float = 0.8
    motion_thresh: float = 0.4
    spatial_luma: float = 0.6
    spatial_chroma: float = 1.0
    preserve_detail: float = 0.35
    spatial_radius: int = 3
    eq_fine: float = 1.0
    master: float = 1.0
    ghost_guard: bool = True
    profile_adjust: float = 1.0


@dataclass
class Sigmas:
    sy: float; scb: float; scr: float          # input spatial family
    ty: float; tcb: float; tcr: float          # temporal gating
    gain_y: "object" = None                    # 16-bin brightness gains
    gain_c: "object" = None
    had_temporal: bool = False


# --- primitives ---------------------------------------------------------------

def _np():
    import numpy as np
    return np


def _lap(img):
    """The estimator's 3x3 Laplacian: 4c - 2(NSEW) + corners (Immerkaer mask)."""
    import cv2
    import numpy as np

    global _LAP_KERNEL
    if _LAP_KERNEL is None:
        _LAP_KERNEL = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], np.float32)
    return cv2.filter2D(img, -1, _LAP_KERNEL, borderType=cv2.BORDER_REPLICATE)


def _box3(img):
    import cv2
    return cv2.boxFilter(img, -1, (3, 3), borderType=cv2.BORDER_REPLICATE)


def bgr_to_ycc(bgr_u8):
    """uint8 BGR -> float32 (Y, Cb, Cr) planes, nr_core.h rgb2ycc (BT.709)."""
    np = _np()
    f = bgr_u8.astype(np.float32) * (1.0 / 255.0)
    b, g, r = f[..., 0], f[..., 1], f[..., 2]
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    cb = (b - y) * (1.0 / 1.8556)
    cr = (r - y) * (1.0 / 1.5748)
    return y, cb, cr


def ycc_to_bgr(y, cb, cr):
    np = _np()
    r = y + 1.5748 * cr
    b = y + 1.8556 * cb
    g = (y - 0.2126 * r - 0.0722 * b) * (1.0 / 0.7152)
    out = np.stack([b, g, r], axis=-1)
    return np.clip(out * 255.0 + 0.5, 0, 255).astype(np.uint8)


def _hist_quantile(vals_u32, nbins, scale, num, den):
    """(bin + 0.5)/scale at the num/den quantile — exactly histQuantile."""
    np = _np()
    if vals_u32.size == 0:
        return 0.0
    h = np.bincount(vals_u32, minlength=nbins)
    total = int(vals_u32.size)
    target = (total * num + den - 1) // den
    cum = np.cumsum(h)
    b = int(np.searchsorted(cum, target))
    b = min(b, nbins - 1)
    return (b + 0.5) / scale


def _quant(a, scale, nbins):
    np = _np()
    return np.clip((a * scale).astype(np.int64), 0, nbins - 1)


def _smooth01(t):
    np = _np()
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _block2(img):
    """2x2 forward block mean: B[y,x] = mean of img[y:y+2, x:x+2] (blockMeanYCC)."""
    import cv2
    import numpy as np

    p = cv2.copyMakeBorder(img, 0, 1, 0, 1, cv2.BORDER_REPLICATE)
    return 0.25 * (p[:-1, :-1] + p[:-1, 1:] + p[1:, :-1] + p[1:, 1:])


def _lap_stride2(img):
    """3x3 Laplacian with +/-2 spacing (the coarse band's kernel)."""
    import cv2
    import numpy as np

    k = np.zeros((5, 5), np.float32)
    k[2, 2] = 4.0
    k[0, 2] = k[4, 2] = k[2, 0] = k[2, 4] = -2.0
    k[0, 0] = k[0, 4] = k[4, 0] = k[4, 4] = 1.0
    return cv2.filter2D(img, -1, k, borderType=cv2.BORDER_REPLICATE)


# --- stage 1: input estimator (estimateInput) ----------------------------------

def estimate_sigmas(cur_bgr, partner_bgr=None, adjust: float = 1.0) -> Sigmas:
    """Fine + coarse Laplacian medians, temporal-diff median/Q20, gains."""
    np = _np()
    y, cb, cr = bgr_to_ycc(cur_bgr)
    H, W = y.shape

    lap_y, lap_cb, lap_cr = _lap(y), _lap(cb), _lap(cr)
    # sampling grid: odd x, odd y in [1, W-1)
    sl = (slice(1, H - 1, 2), slice(1, W - 1, 2))
    ay, acb, acr = np.abs(lap_y[sl]), np.abs(lap_cb[sl]), np.abs(lap_cr[sl])
    live = ~((ay == 0) & (acb == 0) & (acr == 0))   # v3.1 flat-sample skip
    ay, acb, acr = ay[live], acb[live], acr[live]
    y_s = y[sl][live]
    total_f = int(ay.size)

    sig = Sigmas(sy=0.02, scb=0.02, scr=0.02, ty=0.02, tcb=0.02, tcr=0.02,
                 gain_y=np.ones(K_LUMA_BINS, np.float32),
                 gain_c=np.ones(K_LUMA_BINS, np.float32))
    if total_f < 64:
        return sig

    qy = _quant(ay, K_HIST_SCALE_Y, K_HIST_BINS)
    qcb = _quant(acb, K_HIST_SCALE_C, K_HIST_BINS)
    qcr = _quant(acr, K_HIST_SCALE_C, K_HIST_BINS)
    sy_fine = _hist_quantile(qy, K_HIST_BINS, K_HIST_SCALE_Y, 1, 2) * K_MEDIAN_CAL
    scb_fine = _hist_quantile(qcb, K_HIST_BINS, K_HIST_SCALE_C, 1, 2) * K_MEDIAN_CAL
    scr_fine = _hist_quantile(qcr, K_HIST_BINS, K_HIST_SCALE_C, 1, 2) * K_MEDIAN_CAL

    # coarse: 2x2 block means, stride-2 Laplacian, every other sample (stride 4)
    slc = (slice(1, H - 1, 4), slice(1, W - 1, 4))
    l2y = _lap_stride2(_block2(y))[slc]
    l2cb = _lap_stride2(_block2(cb))[slc]
    l2cr = _lap_stride2(_block2(cr))[slc]
    live2 = ~((l2y == 0) & (l2cb == 0) & (l2cr == 0))
    a2y, a2cb, a2cr = np.abs(l2y[live2]), np.abs(l2cb[live2]), np.abs(l2cr[live2])
    sy_coarse = scb_coarse = scr_coarse = 0.0
    if a2y.size >= 64:
        sy_coarse = 2.0 * _hist_quantile(_quant(a2y, K_HIST_SCALE_Y, K_HIST_BINS),
                                         K_HIST_BINS, K_HIST_SCALE_Y, 1, 2) * K_MEDIAN_CAL
        scb_coarse = 2.0 * _hist_quantile(_quant(a2cb, K_HIST_SCALE_C, K_HIST_BINS),
                                          K_HIST_BINS, K_HIST_SCALE_C, 1, 2) * K_MEDIAN_CAL
        scr_coarse = 2.0 * _hist_quantile(_quant(a2cr, K_HIST_SCALE_C, K_HIST_BINS),
                                          K_HIST_BINS, K_HIST_SCALE_C, 1, 2) * K_MEDIAN_CAL

    lap_sy = max(sy_fine, 0.9 * sy_coarse)
    lap_scb = max(scb_fine, 0.9 * scb_coarse)
    lap_scr = max(scr_fine, 0.9 * scr_coarse)

    ty, tcb, tcr = lap_sy, lap_scb, lap_scr
    if partner_bgr is not None:
        py, pcb, pcr = bgr_to_ycc(partner_bgr)
        dy = np.abs((py - y)[sl][live])
        dcb = np.abs((pcb - cb)[sl][live])
        dcr = np.abs((pcr - cr)[sl][live])
        if dy.size >= 64:
            def t_est(d, scale):
                q = _quant(d, scale, K_HIST_BINS)
                med = _hist_quantile(q, K_HIST_BINS, scale, 1, 2) * K_MEDIAN_CAL_T
                q20 = _hist_quantile(q, K_HIST_BINS, scale, 1, 5) * K_Q20_CAL_T
                return (med if med <= 1.4 * q20 else q20)

            cand_y = t_est(dy, K_HIST_SCALE_Y)
            cand_cb = t_est(dcb, K_HIST_SCALE_C)
            cand_cr = t_est(dcr, K_HIST_SCALE_C)
            if 0.0015 < cand_y <= 3.5 * lap_sy:
                ty = cand_y
            if 0.0015 < cand_cb <= 3.5 * lap_scb:
                tcb = cand_cb
            if 0.0015 < cand_cr <= 3.5 * lap_scr:
                tcr = cand_cr
            sig.had_temporal = True

    adj = float(np.clip(adjust, 0.25, 6.0))
    cl = lambda v: float(np.clip(v, K_SIGMA_MIN, K_SIGMA_MAX))
    sig.sy = cl(max(lap_sy, 0.85 * ty) * adj)
    sig.scb = cl(max(lap_scb, 0.85 * tcb) * adj)
    sig.scr = cl(max(lap_scr, 0.85 * tcr) * adj)
    sig.ty, sig.tcb, sig.tcr = cl(ty * adj), cl(tcb * adj), cl(tcr * adj)

    # brightness-dependent gains: per-luma-bin Q35 vs the global Q35 reference
    q35_ref_y = _hist_quantile(qy, K_HIST_BINS, K_HIST_SCALE_Y, 7, 20) * K_Q35_CAL
    q35_ref_c = 0.5 * (_hist_quantile(qcb, K_HIST_BINS, K_HIST_SCALE_C, 7, 20) +
                       _hist_quantile(qcr, K_HIST_BINS, K_HIST_SCALE_C, 7, 20)) * K_Q35_CAL
    lb = np.clip((y_s * K_LUMA_BINS).astype(np.int64), 0, K_LUMA_BINS - 1)
    sub_y = _quant(ay, K_LUMA_SUB_SCALE_Y, K_LUMA_SUB)
    sub_cb = _quant(acb, K_LUMA_SUB_SCALE_C, K_LUMA_SUB)
    sub_cr = _quant(acr, K_LUMA_SUB_SCALE_C, K_LUMA_SUB)
    gy = np.ones(K_LUMA_BINS, np.float32)
    gc = np.ones(K_LUMA_BINS, np.float32)
    for b in range(K_LUMA_BINS):
        m = lb == b
        cy = int(m.sum())
        if cy >= 200 and q35_ref_y > 1e-6:
            sb = _hist_quantile(sub_y[m], K_LUMA_SUB, K_LUMA_SUB_SCALE_Y, 7, 20) * K_Q35_CAL
            w = cy / (cy + 2000.0)
            gy[b] = np.clip(1.0 + w * (sb / q35_ref_y - 1.0), 0.6, 2.2)
        cc = 2 * cy  # both chroma channels feed the curve
        if cc >= 200 and q35_ref_c > 1e-6:
            subs = np.concatenate([sub_cb[m], sub_cr[m]])
            sb = _hist_quantile(subs, K_LUMA_SUB, K_LUMA_SUB_SCALE_C, 7, 20) * K_Q35_CAL
            w = cc / (cc + 4000.0)
            gc[b] = np.clip(1.0 + w * (sb / q35_ref_c - 1.0), 0.6, 2.2)
    # physically smooth curves: 3-tap smoothing
    for b in range(K_LUMA_BINS):
        b0, b1 = max(b - 1, 0), min(b + 1, K_LUMA_BINS - 1)
        sig.gain_y[b] = 0.25 * gy[b0] + 0.5 * gy[b] + 0.25 * gy[b1]
        sig.gain_c[b] = 0.25 * gc[b0] + 0.5 * gc[b] + 0.25 * gc[b1]
    return sig


# --- stage 2: temporal merge (hard-knee gate + Ghost Guard) ---------------------

def _exposure_offset(yc, yn):
    """v3.5 P1: median signed luma diff on a stride-4 grid, with deadzone."""
    np = _np()
    H, W = yc.shape
    d = (yn - yc)[1:H - 1:4, 1:W - 1:4].ravel()
    if d.size < 64:
        return 0.0
    q = np.clip(((d + 0.25) * K_EXP_SCALE).astype(np.int64), 0, K_EXP_BINS - 1)
    h = np.bincount(q, minlength=K_EXP_BINS)
    target = (d.size + 1) // 2
    mbin = int(np.searchsorted(np.cumsum(h), target))
    mbin = min(mbin, K_EXP_BINS - 1)
    o = (mbin + 0.5) / K_EXP_SCALE - 0.25
    return float(o) if abs(o) >= K_EXP_DEAD else 0.0


def _temporal_merge(cur, neighbors, sig: Sigmas, p: HushParams):
    """cur/neighbors are (y, cb, cr) tuples. Returns merged (y, cb, cr, effN)."""
    np = _np()
    yc, cbc, crc = cur
    m_low = min(p.master, 1.0)
    m_high = max(p.master, 1.0)
    tl = float(np.clip(p.temporal_luma * m_low, 0.0, 1.25))
    tc = float(np.clip(p.temporal_chroma * m_low, 0.0, 1.25))
    thr_mul = 0.4 + 2.6 * float(np.clip(p.motion_thresh, 0.0, 1.5)) \
        + 0.8 * (m_high - 1.0)
    lo_y = K_ABS_DIFF_BIAS * sig.ty
    lo_cb = K_ABS_DIFF_BIAS * sig.tcb
    lo_cr = K_ABS_DIFF_BIAS * sig.tcr
    inv_span_y = 1.0 / (thr_mul * sig.ty)
    inv_span_cb = 1.0 / (thr_mul * sig.tcb)
    inv_span_cr = 1.0 / (thr_mul * sig.tcr)
    lo_s = K_ABS_DIFF_BIAS * sig.ty
    inv_span_s = 1.0 / (0.5 * thr_mul * sig.ty)

    lb = np.clip((yc * K_LUMA_BINS).astype(np.int32), 0, K_LUMA_BINS - 1)
    gn_y = np.take(sig.gain_y, lb)
    gn_c = np.take(sig.gain_c, lb)

    acc_y, acc_cb, acc_cr = yc.copy(), cbc.copy(), crc.copy()
    sum_wy = np.ones_like(yc)
    sum_wy2 = np.ones_like(yc)
    sum_wcb = np.ones_like(yc)
    sum_wcr = np.ones_like(yc)

    for (yn, cbn, crn) in neighbors:
        off = _exposure_offset(yc, yn)
        yn_m = yn - off
        d_y = _box3(np.abs(yn_m - yc))
        sd_y = _box3(yn_m - yc)
        d_cb = _box3(np.abs(cbn - cbc))
        d_cr = _box3(np.abs(crn - crc))

        g_y = 1.0 - _smooth01((d_y - lo_y * gn_y) * inv_span_y / gn_y)
        if p.ghost_guard:
            g_y = g_y * (1.0 - _smooth01(
                (np.abs(sd_y) - lo_s * gn_y) * inv_span_s / gn_y))
        g_cb = 1.0 - _smooth01((d_cb - lo_cb * gn_c) * inv_span_cb / gn_c)
        g_cr = 1.0 - _smooth01((d_cr - lo_cr * gn_c) * inv_span_cr / gn_c)
        w_y = tl * g_y
        w_cb = tc * g_cb * g_y
        w_cr = tc * g_cr * g_y

        acc_y += w_y * yn_m
        acc_cb += w_cb * cbn
        acc_cr += w_cr * crn
        sum_wy += w_y
        sum_wy2 += w_y * w_y
        sum_wcb += w_cb
        sum_wcr += w_cr

    out_y = acc_y / sum_wy
    out_cb = acc_cb / sum_wcb
    out_cr = acc_cr / sum_wcr
    eff_n = (sum_wy * sum_wy) / sum_wy2
    return out_y, out_cb, out_cr, eff_n


# --- stage 3: residual re-measure (two scales, floors) --------------------------

def _estimate_residual(ym, cbm, crm, eff_n, sig: Sigmas, adjust: float):
    np = _np()
    H, W = ym.shape
    sl = (slice(1, H - 1, 2), slice(1, W - 1, 2))
    ay = np.abs(_lap(ym)[sl])
    acb = np.abs(_lap(cbm)[sl])
    acr = np.abs(_lap(crm)[sl])
    live = ~((ay == 0) & (acb == 0) & (acr == 0))
    ay, acb, acr = ay[live], acb[live], acr[live]
    if ay.size < 64:
        return sig.sy, sig.scb, sig.scr, 1.0

    adj = float(np.clip(adjust, 0.25, 6.0))
    ry = _hist_quantile(_quant(ay, K_HIST_SCALE_Y, K_HIST_BINS),
                        K_HIST_BINS, K_HIST_SCALE_Y, 1, 2) * K_MEDIAN_CAL * adj
    rcb = _hist_quantile(_quant(acb, K_HIST_SCALE_C, K_HIST_BINS),
                         K_HIST_BINS, K_HIST_SCALE_C, 1, 2) * K_MEDIAN_CAL * adj
    rcr = _hist_quantile(_quant(acr, K_HIST_SCALE_C, K_HIST_BINS),
                         K_HIST_BINS, K_HIST_SCALE_C, 1, 2) * K_MEDIAN_CAL * adj

    # coarse residual on EVEN-aligned 2x2 blocks (4:2:0 blotch sits there)
    slc = (slice(0, H, 4), slice(0, W, 4))
    l2y = np.abs(_lap_stride2(_block2(ym))[slc]).ravel()
    l2cb = np.abs(_lap_stride2(_block2(cbm))[slc]).ravel()
    l2cr = np.abs(_lap_stride2(_block2(crm))[slc]).ravel()
    live2 = ~((l2y == 0) & (l2cb == 0) & (l2cr == 0))
    if int(live2.sum()) >= 64:
        ry_c = 2.0 * _hist_quantile(_quant(l2y[live2], K_HIST_SCALE_Y, K_HIST_BINS),
                                    K_HIST_BINS, K_HIST_SCALE_Y, 1, 2) * K_MEDIAN_CAL * adj
        rcb_c = 2.0 * _hist_quantile(_quant(l2cb[live2], K_HIST_SCALE_C, K_HIST_BINS),
                                     K_HIST_BINS, K_HIST_SCALE_C, 1, 2) * K_MEDIAN_CAL * adj
        rcr_c = 2.0 * _hist_quantile(_quant(l2cr[live2], K_HIST_SCALE_C, K_HIST_BINS),
                                     K_HIST_BINS, K_HIST_SCALE_C, 1, 2) * K_MEDIAN_CAL * adj
        ry = max(ry, 0.9 * ry_c)
        rcb = max(rcb, 0.9 * rcb_c)
        rcr = max(rcr, 0.9 * rcr_c)

    qn = np.clip(((eff_n[sl][live] - 1.0) * 8.0).astype(np.int64), 0, 63)
    eff_med = 1.0 + _hist_quantile(qn, 64, 8.0, 1, 2)  # decode: 1 + (bin+0.5)/8
    # floors: not less than the theoretical reduction, never above the input
    floor_y = 0.5 * sig.sy / np.sqrt(max(1.0, eff_med))
    floor_cb = 0.5 * sig.scb / np.sqrt(max(1.0, eff_med))
    floor_cr = 0.5 * sig.scr / np.sqrt(max(1.0, eff_med))
    ry = float(np.clip(max(ry, floor_y), K_SIGMA_MIN, max(sig.sy, K_SIGMA_MIN)))
    rcb = float(np.clip(max(rcb, floor_cb), K_SIGMA_MIN, max(sig.scb, K_SIGMA_MIN)))
    rcr = float(np.clip(max(rcr, floor_cr), K_SIGMA_MIN, max(sig.scr, K_SIGMA_MIN)))
    return ry, rcb, rcr, float(eff_med)


# --- stage 4: fine NLM band (spatialNLM, NLM mode) ------------------------------

def _shift(img, dx, dy):
    """Clamped-border shift: result[p] = img[p + (dy,dx)] (tmpAt semantics)."""
    import cv2

    H, W = img.shape
    p = cv2.copyMakeBorder(img, abs(dy), abs(dy), abs(dx), abs(dx),
                           cv2.BORDER_REPLICATE)
    return p[abs(dy) + dy:abs(dy) + dy + H, abs(dx) + dx:abs(dx) + dx + W]


def _spatial_nlm(ym, cbm, crm, ry, rcb, rcr, sig: Sigmas, p: HushParams):
    np = _np()
    m_low = min(p.master, 1.0)
    m_high = max(p.master, 1.0)
    h_boost = m_high ** 1.2
    s_l = float(np.clip(p.spatial_luma, 0.0, 1.5))
    s_c = float(np.clip(p.spatial_chroma, 0.0, 1.5))
    eq_f = float(np.clip(p.eq_fine, 0.0, 3.0))
    eq_h = max(1.0, eq_f) ** 0.8
    a_y = float(np.clip(s_l * m_low * eq_f, 0.0, 1.0))
    a_c = float(np.clip(s_c * m_low * eq_f, 0.0, 1.0))
    if a_y <= 0.0 and a_c <= 0.0:
        return ym, cbm, crm
    over_l = 1.6 * (s_l - 1.0) ** 1.2 if s_l > 1.0 else 0.0
    over_c = 1.6 * (s_c - 1.0) ** 1.2 if s_c > 1.0 else 0.0
    h_mul_y = (0.6 + 1.4 * s_l ** 1.5 + over_l) * h_boost * eq_h
    h_mul_c = (0.6 + 1.4 * s_c ** 1.5 + over_c) * h_boost * eq_h
    pd = float(np.clip(p.preserve_detail, 0.0, 1.0))
    R = int(np.clip(p.spatial_radius, 1, 10))

    lb = np.clip((ym * K_LUMA_BINS).astype(np.int32), 0, K_LUMA_BINS - 1)
    sig_y = np.clip(ry * np.take(sig.gain_y, lb), 1e-5, 1.0).astype(np.float32)
    sig_cb = np.clip(rcb * np.take(sig.gain_c, lb), 1e-5, 1.0).astype(np.float32)
    sig_cr = np.clip(rcr * np.take(sig.gain_c, lb), 1e-5, 1.0).astype(np.float32)

    mean = _box3(ym)
    m2 = _box3(ym * ym)
    var = np.maximum(0.0, m2 - mean * mean)
    edginess = np.clip(np.sqrt(np.maximum(var - sig_y * sig_y, 0.0)) / (3.0 * sig_y),
                       0.0, 1.0)

    h_y = K_NLM_H_LUMA * sig_y * h_mul_y * (1.0 - pd * 0.85 * edginess)
    m_c = h_mul_c * (1.0 - pd * 0.50 * edginess)
    inv_hy2 = 1.0 / np.maximum(h_y * h_y, 1e-12)
    inv_hc2 = 1.0 / np.maximum(K_NLM_H_CHROMA * K_NLM_H_CHROMA * m_c * m_c, 1e-12)
    inv_scb2 = 1.0 / np.maximum(sig_cb * sig_cb, 1e-12)
    inv_scr2 = 1.0 / np.maximum(sig_cr * sig_cr, 1e-12)
    bias_y = 2.0 * sig_y * sig_y
    bias_cb = 2.0 * sig_cb * sig_cb
    bias_cr = 2.0 * sig_cr * sig_cr

    acc_y = np.zeros_like(ym)
    acc_cb = np.zeros_like(ym)
    acc_cr = np.zeros_like(ym)
    sum_wy = np.zeros_like(ym)
    sum_wc = np.zeros_like(ym)
    wy_max = np.zeros_like(ym)
    wc_max = np.zeros_like(ym)

    for dy in range(-R, R + 1):
        for dx in range(-R, R + 1):
            if dx == 0 and dy == 0:
                continue
            ys = _shift(ym, dx, dy)
            cbs = _shift(cbm, dx, dy)
            crs = _shift(crm, dx, dy)
            d_y2 = np.maximum(0.0, _box3((ym - ys) ** 2) - bias_y)
            d_cb2 = np.maximum(0.0, _box3((cbm - cbs) ** 2) - bias_cb)
            d_cr2 = np.maximum(0.0, _box3((crm - crs) ** 2) - bias_cr)
            d_c2n = 0.5 * (d_cb2 * inv_scb2 + d_cr2 * inv_scr2)
            w_y = np.exp(-d_y2 * inv_hy2)
            w_c = np.exp(-d_c2n * inv_hc2) * np.exp(-d_y2 * inv_hy2 * 0.25)
            acc_y += w_y * ys
            acc_cb += w_c * cbs
            acc_cr += w_c * crs
            sum_wy += w_y
            sum_wc += w_c
            np.maximum(wy_max, w_y, out=wy_max)
            np.maximum(wc_max, w_c, out=wc_max)

    wy_c = np.maximum(wy_max, 1e-4)
    wc_c = np.maximum(wc_max, 1e-4)
    y_f = (acc_y + wy_c * ym) / (sum_wy + wy_c)
    cb_f = (acc_cb + wc_c * cbm) / (sum_wc + wc_c)
    cr_f = (acc_cr + wc_c * crm) / (sum_wc + wc_c)

    return (ym + a_y * (y_f - ym),
            cbm + a_c * (cb_f - cbm),
            crm + a_c * (cr_f - crm))


# --- public API -----------------------------------------------------------------

def denoise_trio(prev_bgr, cur_bgr, next_bgr, params: Optional[HushParams] = None):
    """Denoise the middle frame of an aligned trio (uint8 BGR in and out).

    prev/next may be None (clip edges) — Hush's duplicate-frame semantics.
    Returns (out_bgr, info) with the measured sigmas in the info dict.
    """
    p = params or HushParams()
    cur = bgr_to_ycc(cur_bgr)
    partner = prev_bgr if prev_bgr is not None else next_bgr
    sig = estimate_sigmas(cur_bgr, partner, adjust=p.profile_adjust)

    neighbors = []
    for nb in (prev_bgr, next_bgr):
        neighbors.append(bgr_to_ycc(nb) if nb is not None else cur)
    ym, cbm, crm, eff_n = _temporal_merge(cur, neighbors, sig, p)
    ry, rcb, rcr, eff_med = _estimate_residual(ym, cbm, crm, eff_n, sig,
                                               p.profile_adjust)
    yo, cbo, cro = _spatial_nlm(ym, cbm, crm, ry, rcb, rcr, sig, p)

    info = {
        "backend": "hush-core",
        "sigma_y": round(sig.sy, 5), "sigma_c": round(0.5 * (sig.scb + sig.scr), 5),
        "temporal_sigma_y": round(sig.ty, 5),
        "residual_y": round(ry, 5), "eff_n_med": round(eff_med, 2),
        "had_temporal": sig.had_temporal,
    }
    return ycc_to_bgr(yo, cbo, cro), info


def denoise_frame(cur_bgr, params: Optional[HushParams] = None):
    """Spatial-only convenience (single stills / previews without neighbors)."""
    return denoise_trio(None, cur_bgr, None, params)
