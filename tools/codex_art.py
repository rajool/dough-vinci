#!/usr/bin/env python3
"""Codex art for Dough-Vinci: regenerates every drawing in src/art/ deterministically.

    python3 tools/codex_art.py              # writes src/art/ next to this tools/ folder
    python3 tools/codex_art.py --out DIR    # writes somewhere else

Standard library only. The contract of the output (ids, classes, groups, JSON) is tools/README.md;
the drawing rules are DESIGN.md. Every drawing is procedural with fixed seeds: ink contours are one to
three jittered, overlapping strokes with overshooting ends; hatching is left-handed (upper-left to
lower-right) on the shadow side of a light from the upper left; washes are several translucent,
slightly misregistered passes under a shared turbulence filter.
"""
import argparse
import bisect
import json
import math
import os
import random

TAU = math.tau
COARSE = 40.0         # shapes larger than this (user units) are written in whole units
PHI = (1 + 5 ** 0.5) / 2
HATCH = 42.0          # degrees below horizontal: Leonardo's left-handed "\" hatching
CROSS = -28.0         # second direction, used only in the darkest places


def _norm3(x, y, z):
    d = math.sqrt(x * x + y * y + z * z)
    return (x / d, y / d, z / d)


LIGHT = _norm3(-0.55, -0.6, 0.58)   # from the upper left, above the page


# --------------------------------------------------------------------------- path data

def _t(v):
    return int(round(v * 10))


def _ft(n):
    """Format an integer number of tenths with at most one decimal and no leading zero."""
    neg = n < 0
    n = abs(n)
    i, f = divmod(n, 10)
    if f:
        s = (str(i) if i else '') + '.' + str(f)
    else:
        s = str(i)
    return '-' + s if neg and s != '0' else s


class PathData:
    """Compact path data: absolute M, relative curves, one decimal, no drift from rounding.

    coarse=True rounds to whole units (used for large, soft shapes where a tenth is invisible)."""

    def __init__(self, coarse=False):
        self.coarse = coarse
        self.parts = []
        self.cur = (0, 0)
        self.start = (0, 0)
        self.last = ''

    def _emit(self, cmd, vals):
        s = ''
        first = True
        if cmd != self.last or cmd == 'M':
            s = cmd
        else:
            first = False
        for v in vals:
            t = _ft(v)
            if not first and not t.startswith('-'):
                s += ' '
            s += t
            first = False
        self.parts.append(s)
        self.last = cmd

    def _q(self, v):
        return int(round(v)) * 10 if self.coarse else _t(v)

    def M(self, x, y):
        p = (self._q(x), self._q(y))
        self._emit('M', p)
        self.cur = self.start = p

    def _rel(self, *xy):
        X, Y = self.cur
        out = []
        for i in range(0, len(xy), 2):
            out += [self._q(xy[i]) - X, self._q(xy[i + 1]) - Y]
        return out

    def c(self, x1, y1, x2, y2, x, y):
        self._emit('c', self._rel(x1, y1, x2, y2, x, y))
        self.cur = (self._q(x), self._q(y))

    def s(self, x2, y2, x, y):
        self._emit('s', self._rel(x2, y2, x, y))
        self.cur = (self._q(x), self._q(y))

    def q(self, x1, y1, x, y):
        self._emit('q', self._rel(x1, y1, x, y))
        self.cur = (self._q(x), self._q(y))

    def l(self, x, y):
        self._emit('l', self._rel(x, y))
        self.cur = (self._q(x), self._q(y))

    def z(self):
        self.parts.append('z')
        self.last = 'z'
        self.cur = self.start

    def __str__(self):
        return ''.join(self.parts)


def catmull(pd, pts, closed=False):
    """Append a smooth Catmull-Rom spline through pts (as cubic Beziers) to pd."""
    n = len(pts)
    if n >= 2 and pd.coarse is None:
        b = bbox(pts)
        pd.coarse = max(b[2] - b[0], b[3] - b[1]) > COARSE
    if n < 2:
        return pd
    pd.M(*pts[0])
    if n == 2:
        pd.l(*pts[1])
        return pd
    if closed:
        ext = [pts[-1]] + list(pts) + list(pts[:2])
        segs = n
    else:
        ext = [pts[0]] + list(pts) + [pts[-1]]
        segs = n - 1
    for i in range(segs):
        p0, p1, p2, p3 = ext[i:i + 4]
        # Catmull-Rom tangents are continuous, so every segment after the first is a smooth 's'
        if i == 0:
            pd.c(p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6,
                 p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6, p2[0], p2[1])
        else:
            pd.s(p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6, p2[0], p2[1])
    if closed:
        pd.z()
    return pd


def spline(pts, closed=False):
    return str(catmull(PathData(None), pts, closed))


# --------------------------------------------------------------------------- geometry

def rot(p, a, c=(0.0, 0.0)):
    s, co = math.sin(a), math.cos(a)
    x, y = p[0] - c[0], p[1] - c[1]
    return (c[0] + x * co - y * s, c[1] + x * s + y * co)


def xform(pts, dx=0.0, dy=0.0, a=0.0, s=1.0, sy=None):
    sy = s if sy is None else sy
    out = []
    for x, y in pts:
        x, y = x * s, y * sy
        x, y = rot((x, y), a)
        out.append((x + dx, y + dy))
    return out


def ellipse(cx, cy, rx, ry, a=0.0, n=48, a0=0.0, a1=TAU, endpoint=False):
    out = []
    m = n if not endpoint else n - 1
    for i in range(n):
        t = a0 + (a1 - a0) * i / max(m, 1)
        p = (rx * math.cos(t), ry * math.sin(t))
        p = rot(p, a)
        out.append((cx + p[0], cy + p[1]))
    return out


def superellipse(cx, cy, rx, ry, p, a0, a1, n):
    out = []
    for i in range(n):
        t = a0 + (a1 - a0) * i / (n - 1)
        c, s = math.cos(t), math.sin(t)
        x = math.copysign(abs(c) ** (2 / p), c)
        y = math.copysign(abs(s) ** (2 / p), s)
        out.append((cx + rx * x, cy + ry * y))
    return out


def smooth_poly(ctrl, closed=True, per=8):
    """Dense polyline through control points (Catmull-Rom sampled)."""
    n = len(ctrl)
    ext = ([ctrl[-1]] + list(ctrl) + list(ctrl[:2])) if closed else ([ctrl[0]] + list(ctrl) + [ctrl[-1]])
    segs = n if closed else n - 1
    out = []
    for i in range(segs):
        p0, p1, p2, p3 = ext[i:i + 4]
        for k in range(per):
            t = k / per
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
    if not closed:
        out.append(ctrl[-1])
    return out


def area(pts):
    a = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        a += x0 * y1 - x1 * y0
    return a / 2


def bbox(pts, pad=0.0):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)


class Poly:
    """A closed polygon with a fast inside test (bbox prefilter)."""

    def __init__(self, pts, holes=()):
        self.pts = list(pts)
        self.holes = [list(h) for h in holes]
        self.bb = bbox(self.pts)

    @staticmethod
    def _inside(pts, x, y):
        inside = False
        j = len(pts) - 1
        for i in range(len(pts)):
            xi, yi = pts[i]
            xj, yj = pts[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi:
                inside = not inside
            j = i
        return inside

    def __contains__(self, p):
        x, y = p
        b = self.bb
        if x < b[0] or x > b[2] or y < b[1] or y > b[3]:
            return False
        if not self._inside(self.pts, x, y):
            return False
        return not any(self._inside(h, x, y) for h in self.holes)


class Curve:
    """Arc-length parametrised polyline (closed curves wrap, open ones extrapolate)."""

    def __init__(self, pts, closed=False):
        P = list(pts)
        if closed:
            P = P + [P[0]]
        self.P = P
        self.closed = closed
        cum = [0.0]
        for a, b in zip(P, P[1:]):
            cum.append(cum[-1] + math.dist(a, b))
        self.cum = cum
        self.L = cum[-1]
        self.out = (-1 if area(list(pts)) > 0 else 1) if closed else 1

    def at(self, s):
        P, cum, L = self.P, self.cum, self.L
        if self.closed:
            s %= L
        elif s < 0 or s > L:
            a, b = (P[0], P[1]) if s < 0 else (P[-1], P[-2])
            d = math.dist(a, b) or 1.0
            e = -s if s < 0 else s - L
            return (a[0] + (a[0] - b[0]) / d * e, a[1] + (a[1] - b[1]) / d * e)
        i = min(max(bisect.bisect_right(cum, s) - 1, 0), len(P) - 2)
        seg = (cum[i + 1] - cum[i]) or 1.0
        t = (s - cum[i]) / seg
        return (P[i][0] + (P[i + 1][0] - P[i][0]) * t, P[i][1] + (P[i + 1][1] - P[i][1]) * t)

    def normal(self, s, h=1.5):
        x0, y0 = self.at(s - h)
        x1, y1 = self.at(s + h)
        dx, dy = x1 - x0, y1 - y0
        d = math.hypot(dx, dy) or 1.0
        return (-dy / d * self.out, dx / d * self.out)


def wobble(rng, amp, scales=(90.0, 34.0, 15.0)):
    ph = [rng.uniform(0, TAU) for _ in scales]
    ws = [1.0, 0.5, 0.25][:len(scales)]
    tot = sum(ws)
    return lambda s: amp * sum(w * math.sin(TAU * s / l + p) for w, l, p in zip(ws, scales, ph)) / tot


def harmonics(rng, terms):
    ph = [rng.uniform(0, TAU) for _ in terms]
    return lambda t: sum(a * math.sin(f * t + p) for (f, a), p in zip(terms, ph))


def noise2(rng, n=5, scale=60.0):
    """Cheap smooth 2D noise in [-1, 1]: a sum of plane waves with random directions."""
    waves = []
    for k in range(n):
        a = rng.uniform(0, TAU)
        f = TAU / (scale * rng.uniform(0.6, 1.4) / (1 + 0.6 * k))
        waves.append((math.cos(a) * f, math.sin(a) * f, rng.uniform(0, TAU), 1 / (1 + k)))
    tot = sum(w[3] for w in waves)
    return lambda x, y: sum(w * math.sin(fx * x + fy * y + p) for fx, fy, p, w in waves) / tot


# --------------------------------------------------------------------------- ink, hatching, washes

def decimate(run, seg):
    out = [run[0]]
    acc = 0.0
    for a, b in zip(run, run[1:]):
        acc += math.dist(a, b)
        if acc >= seg:
            out.append(b)
            acc = 0.0
    if out[-1] != run[-1]:
        if math.dist(out[-1], run[-1]) < seg * 0.35 and len(out) > 2:
            out[-1] = run[-1]
        else:
            out.append(run[-1])
    return out


def split_runs(pts, occluders):
    if not occluders:
        return [pts]
    runs, cur = [], []
    for p in pts:
        if any(p in o for o in occluders):
            if len(cur) > 1:
                runs.append(cur)
            cur = []
        else:
            cur.append(p)
    if len(cur) > 1:
        runs.append(cur)
    return runs


def ink(pts, closed, rng, passes=2, wob=0.8, drift=1.3, over=None, part=(0.3, 0.7),
        occluders=(), seg=None, step=2.0, minlen=4.0):
    """One to three hand-drawn strokes along a contour: wobbling, overlapping, overshooting."""
    c = Curve(pts, closed)
    L = c.L
    if L < 1:
        return []
    seg = seg or max(2.5, min(15.0, L / 16))
    out = []
    for k in range(passes):
        if k == 0:
            if closed:
                s0 = rng.uniform(0, L)
                o = min(L * 0.07, 16.0) if over is None else over
                s1 = s0 + L + o * rng.uniform(0.5, 1.0)
            else:
                o = min(L * 0.04, 7.0) if over is None else over
                s0 = -o * rng.uniform(0.0, 1.0)
                s1 = L + o * rng.uniform(0.2, 1.0)
        else:
            frac = rng.uniform(*part)
            if closed:
                s0 = rng.uniform(0, L)
            else:
                s0 = rng.uniform(0, 1 - frac) * L
            s1 = s0 + frac * L
        base = rng.uniform(-1, 1) * drift * (0.35 if k == 0 else 1.0)
        ramp = drift * rng.choice((-1, 1)) if (k == 0 and closed) else 0.0
        w = wobble(rng, wob, (max(L / 3, 40.0), 34.0, 15.0))
        n = max(2, int((s1 - s0) / step))
        fine = []
        for j in range(n + 1):
            u = j / n
            s = s0 + (s1 - s0) * u
            off = base + ramp * u + w(s)
            x, y = c.at(s)
            nx, ny = c.normal(s)
            fine.append((x + nx * off, y + ny * off))
        for run in split_runs(fine, occluders):
            ln = sum(math.dist(a, b) for a, b in zip(run, run[1:]))
            if ln >= minlen:
                out.append(decimate(run, seg))
    return out


def hatch(rng, box, test, spacing=6.0, angle=HATCH, jitter=2.5, minlen=5.0, step=1.4, bow=1.2, trim=0.25):
    """Parallel hatch segments inside box where test(x, y, r) holds (r: a per-line random 0..1)."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    half = math.hypot(x1 - x0, y1 - y0) / 2 + 2
    segs = []
    t = -half + rng.uniform(0, spacing)
    while t < half:
        a = math.radians(angle + rng.uniform(-jitter, jitter))
        dx, dy = math.cos(a), math.sin(a)
        nx, ny = -dy, dx
        ox, oy = cx + nx * t, cy + ny * t
        r = rng.random()
        # clip the line to the box (Liang-Barsky) to sample only inside it
        lo, hi = -half, half
        for p, q in ((-dx, ox - x0), (dx, x1 - ox), (-dy, oy - y0), (dy, y1 - oy)):
            if abs(p) < 1e-9:
                if q < 0:
                    lo, hi = 1, 0
            else:
                v = q / p
                if p < 0:
                    lo = max(lo, v)
                else:
                    hi = min(hi, v)
        run = None
        s = lo
        while s <= hi:
            x, y = ox + dx * s, oy + dy * s
            if test(x, y, r):
                if run is None:
                    run = [s, s]
                else:
                    run[1] = s
            elif run is not None:
                segs.append((ox, oy, dx, dy, run))
                run = None
            s += step
        if run is not None:
            segs.append((ox, oy, dx, dy, run))
        t += spacing * rng.uniform(0.8, 1.2)
    out = []
    for ox, oy, dx, dy, (s0, s1) in segs:
        ln = s1 - s0
        if ln < minlen:
            continue
        s0 += rng.uniform(0, trim) * ln * 0.5
        s1 -= rng.uniform(0, trim) * ln * 0.5
        p0 = (ox + dx * s0, oy + dy * s0)
        p1 = (ox + dx * s1, oy + dy * s1)
        b = rng.uniform(-1, 1) * min(bow, (s1 - s0) * 0.05)
        mid = ((p0[0] + p1[0]) / 2 - dy * b, (p0[1] + p1[1]) / 2 + dx * b)
        out.append((p0, mid, p1))
    return out


def hatch_d(seg):
    p0, m, p1 = seg
    ln = math.dist(p0, p1)
    pd = PathData(ln > 10)
    pd.M(*p0)
    if ln < 16:
        pd.l(*p1)
    else:   # quadratic through the bowed midpoint
        pd.q(2 * m[0] - (p0[0] + p1[0]) / 2, 2 * m[1] - (p0[1] + p1[1]) / 2, p1[0], p1[1])
    return str(pd)


def jitter_closed(pts, rng, spread, grow=0.0, shift=(0.0, 0.0), seg=8.0):
    c = Curve(pts, True)
    L = c.L
    w = wobble(rng, spread, (max(L / 3.2, 30.0), max(min(L / 7, 60.0), 14.0), 13.0))
    n = max(6, int(L / seg))
    s0 = rng.uniform(0, L)
    out = []
    for j in range(n):
        s = s0 + L * j / n
        x, y = c.at(s)
        nx, ny = c.normal(s)
        off = grow + w(s)
        out.append((x + nx * off + shift[0], y + ny * off + shift[1]))
    return out


def wash(name, pts, rng, passes=((0.8, 1.6), (0.38, 2.6), (0.22, 3.4)), shift=2.2, holes=(), seg=None,
         grow=0.0):
    """Translucent, misregistered watercolour passes over a closed shape (with optional holes)."""
    holes = list(holes) or list(getattr(pts, 'holes', ()))
    L = Curve(pts, True).L
    seg = seg or max(3.0, min(22.0, L / 28))
    out = []
    for op, spread in passes:
        sh = (rng.gauss(0, shift), rng.gauss(0, shift))
        g = grow + rng.uniform(-0.6, 0.9) * spread * 0.6
        body = jitter_closed(pts, rng, spread, g, sh, seg)
        bb = bbox(body)
        pd = PathData(max(bb[2] - bb[0], bb[3] - bb[1]) > 14)   # washes are soft: whole units suffice
        catmull(pd, body, True)
        sign = area(body) > 0
        for h in holes:
            hl = Curve(h, True).L
            hp = jitter_closed(h, rng, min(spread, 1.2), 0.0, sh, max(2.5, min(seg, hl / 10)))
            if (area(hp) > 0) == sign:          # holes wind the other way (nonzero fill)
                hp = hp[::-1]
            catmull(pd, hp, True)
        out.append((name, _fo(op), str(pd)))
    return out


def merge_washes(items):
    """One <path> per run of consecutive passes with the same colour and opacity."""
    out = []
    run = None
    for it in items:
        if isinstance(it, str):
            out.append(it)
            run = None
            continue
        name, op, d = it
        if run is not None and run[0] == name and run[1] == op:
            run[2].append(d)
        else:
            run = [name, op, [d]]
            out.append(run)
    return [f'<path class="wash wash-{r[0]}" fill-opacity="{r[1]}" d="{"".join(r[2])}"/>' if isinstance(r, list) else r
            for r in out]


def _fo(v):
    s = ('%.2f' % v).rstrip('0').rstrip('.')
    return s[1:] if s.startswith('0.') else s


class Ring(list):
    """A closed outline that carries its holes (a band running all the way round)."""
    holes = ()


def band(contour, width_fn, min_w=0.6, outward=False):
    """A crescent polygon along the part of a closed contour where width_fn(point, normal) > min_w."""
    c = Curve(contour, True)
    n = len(contour)
    L = c.L
    ws = []
    for i in range(n):
        s = c.cum[i]
        p = c.at(s)
        nx, ny = c.normal(s)
        ws.append((p, (nx, ny), width_fn(p, (nx, ny))))
    # find the start of a run (a point with w <= min_w followed by w > min_w)
    start = next((i for i in range(n) if ws[i][2] <= min_w and ws[(i + 1) % n][2] > min_w), None)
    if start is None:
        if all(w[2] > min_w for w in ws):
            ring_ = Ring(w[0] for w in ws)
            sg = 1 if outward else -1
            ring_.holes = [[(p[0] + sg * nx * w, p[1] + sg * ny * w) for p, (nx, ny), w in ws]]
            return ring_
        return None
    outer, inner = [], []
    i = (start + 1) % n
    while ws[i][2] > min_w and len(outer) < n:
        p, (nx, ny), w = ws[i]
        outer.append(p)
        sg = 1 if outward else -1
        inner.append((p[0] + sg * nx * w, p[1] + sg * ny * w))
        i = (i + 1) % n
    if len(outer) < 3:
        return None
    _ = L
    return outer + inner[::-1]


# --------------------------------------------------------------------------- SVG assembly

class Layer:
    def __init__(self, cls):
        self.cls = cls
        self.items = []
        self.n = 0

    def stroke(self, d, cls=None):
        self.items.append(f'<path class="{cls or self.cls}" pathLength="1" style="--i:{self.n}" d="{d}"/>')
        self.n += 1

    def strokes(self, runs, cls=None):
        for r in runs:
            if len(r) >= 2:
                self.stroke(spline(r), cls)

    def hatches(self, segs, cls='art-hatch'):
        for s in segs:
            self.stroke(hatch_d(s), cls)

    def raw(self, items):
        self.items.extend(items)


def wash_filter(fid, seed, scale=7.0, freq=0.022, blur=0.45, grain=0.55):
    return (
        f'<filter id="{fid}" x="-6%" y="-6%" width="112%" height="112%" color-interpolation-filters="sRGB">'
        f'<feTurbulence type="fractalNoise" baseFrequency="{freq}" numOctaves="3" seed="{seed}" result="n"/>'
        f'<feDisplacementMap in="SourceGraphic" in2="n" scale="{scale}" xChannelSelector="R" yChannelSelector="G" result="d"/>'
        f'<feGaussianBlur in="d" stdDeviation="{blur}" result="b"/>'
        f'<feTurbulence type="fractalNoise" baseFrequency="{grain}" numOctaves="2" seed="{seed + 3}" result="g"/>'
        '<feColorMatrix in="g" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0.5 0 0 0 0.74" result="ga"/>'
        '<feComposite in="b" in2="ga" operator="in" result="p"/>'
        '<feMorphology in="p" operator="erode" radius="1.4" result="e"/>'
        '<feComposite in="p" in2="e" operator="arithmetic" k2="1" k3="-1" result="rim"/>'
        '<feColorMatrix in="rim" values="0.5 0 0 0 0 0 0.45 0 0 0 0 0 0.4 0 0 0 0 0 0.7 0" result="rimd"/>'
        '<feMerge><feMergeNode in="p"/><feMergeNode in="rimd"/></feMerge>'
        '</filter>')


def svg_root(view, cls, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}" class="{cls}" aria-hidden="true" '
            f'focusable="false">{body}</svg>\n')


def group(attrs, items, n=None):
    # stroke groups carry fill="none" once; every stroke path inherits it
    nn = f' fill="none" style="--n:{n}"' if n is not None else ''
    return f'<g {attrs}{nn}>' + ''.join(merge_washes(items)) + '</g>'


# --------------------------------------------------------------------------- the pizza

def mushroom_outline(rng):
    """The classic mushroom-slice silhouette in local units (about 64 x 52, cap up, stem down)."""
    j = lambda v: v + rng.uniform(-0.45, 0.45)
    cap = [(32 * math.cos(t), 2 + 25 * math.sin(t)) for t in (math.pi + math.pi * k / 20 for k in range(21))]
    right = [(32.3, 4.6), (30.6, 7.6), (27, 9.2), (21, 9.9), (15, 10.1), (11.2, 10.9), (10.7, 15.5), (10.2, 21),
             (9.5, 25.8), (7.2, 28.2), (0, 28.9)]
    left = [(-x, y) for x, y in right[::-1][1:]]
    pts = [(j(x), j(y)) for x, y in cap[1:-1] + right + left]
    return smooth_poly(pts, True, 3)


def mushroom_pocket(side):
    """The dark gill pocket under the cap on one side of the stem (local units)."""
    arc = [(side * 23 * -math.cos(t), 3 - 15.5 * math.sin(t)) for t in (1.092 * k / 6 for k in range(7))]
    arc = [(side * abs(x), y) if side > 0 else (-abs(x), y) for x, y in arc]
    return arc + [(side * 10.6, 10.8), (side * 15, 10), (side * 21, 9.8), (side * 27, 9.1), (side * 29, 6.4),
                  (side * 25.5, 3.8)]


def mushroom_gills(side):
    out = []
    for k in range(1, 4):
        t = 1.092 * k / 4
        a = (side * abs(23 * math.cos(t)), 3 - 15.5 * math.sin(t))
        u = (side * (26.5 - 15 * k / 4), 9.4)
        out.append([a, ((a[0] + u[0]) / 2 + side * 0.4, (a[1] + u[1]) / 2), u])
    return out

def build_pizza():
    rng = random.Random(1452)          # the year Leonardo was born
    cx, cy = 500.0, 500.0
    R = 392.0                          # Vitruvian construction circle
    S = 1.65 * R                       # side of the square, standing on the circle's lowest point
    RP = S / 2                         # the pizza's own circle is inscribed in the square's width
    sx0, sx1, sy1 = cx - S / 2, cx + S / 2, cy + R
    sy0 = sy1 - S

    con = Layer('art-construction')
    hat = Layer('art-hatch')
    lin = Layer('art-line')
    washes = []

    # ---------------- construction: circle, square, axes, golden arcs, compass ticks
    def cline(p, q, ext=(14, 14)):
        dx, dy = q[0] - p[0], q[1] - p[1]
        d = math.hypot(dx, dy)
        ux, uy = dx / d, dy / d
        a = (p[0] - ux * ext[0], p[1] - uy * ext[0])
        b = (q[0] + ux * ext[1], q[1] + uy * ext[1])
        pts = [(a[0] + (b[0] - a[0]) * k / 20, a[1] + (b[1] - a[1]) * k / 20) for k in range(21)]
        con.strokes(ink(pts, False, rng, passes=1, wob=0.35, over=0, seg=60))

    con.strokes(ink(ellipse(cx, cy, R, R, n=180), True, rng, passes=1, wob=0.3, drift=0.5, over=26, seg=55))
    con.strokes(ink(ellipse(cx, cy, R + 11, R + 11, n=180), True, rng, passes=1, wob=0.25, drift=0.4, over=10, seg=55))
    cline((sx0, sy0), (sx1, sy0), (rng.uniform(14, 26), rng.uniform(14, 26)))
    cline((sx1, sy0), (sx1, sy1), (rng.uniform(14, 26), rng.uniform(14, 26)))
    cline((sx1, sy1), (sx0, sy1), (rng.uniform(14, 26), rng.uniform(14, 26)))
    cline((sx0, sy1), (sx0, sy0), (rng.uniform(14, 26), rng.uniform(14, 26)))
    cline((cx - R - 30, cy), (cx + R + 30, cy), (12, 12))
    cline((cx, cy - R - 30), (cx, sy1), (12, 34))
    # golden-ratio arcs from the square's bottom corners: they meet (almost exactly) at the centre
    g = S / PHI
    for corner, sign in (((sx0, sy1), 1), ((sx1, sy1), -1)):
        ccx = corner[0] + sign * g
        a0 = math.pi if sign == 1 else 0.0
        a1 = 1.5 * math.pi if sign == 1 else -0.5 * math.pi
        pts = ellipse(ccx, sy1, g, g, n=60, a0=a0, a1=a1, endpoint=True)
        con.strokes(ink(pts, False, rng, passes=1, wob=0.3, over=8, seg=50))
    con.strokes(ink(ellipse(cx, cy, RP, RP, n=160), True, rng, passes=1, wob=0.25, drift=0.4, over=12, seg=50))
    # golden section ticks on the square's base and the vertical axis
    for x in (sx0 + g, sx1 - g):
        cline((x, sy1 - 9), (x, sy1 + 9), (0, 0))
    for y in (sy1 - g, sy0 + g):
        cline((cx - 9, y), (cx + 9, y), (0, 0))
    # a measured radius with its angle arc, as in a geometry study
    ang = math.radians(-58)
    cline((cx, cy), (cx + R * math.cos(ang), cy + R * math.sin(ang)), (0, 10))
    con.strokes(ink(ellipse(cx, cy, 62, 62, n=24, a0=ang, a1=0, endpoint=True), False, rng, passes=1, wob=0.2,
                    over=3, seg=8))
    # compass point at the centre
    con.strokes(ink(ellipse(cx, cy, 5, 5, n=16), True, rng, passes=1, wob=0.1, drift=0.2, over=2, seg=3))
    # compass ticks: one path per rank (sub-paths grow together)
    for rank in (0, 1, 2):
        pd = PathData()
        for k in range(72):
            deg = k * 5
            r = 2 if deg % 45 == 0 else (1 if deg % 15 == 0 else 0)
            if r != rank:
                continue
            ln = (11, 18, 30)[r]
            a = math.radians(deg) + rng.uniform(-0.002, 0.002)
            r0 = R - (0 if r == 0 else 6)
            pd.M(cx + r0 * math.cos(a), cy + r0 * math.sin(a))
            pd.l(cx + (R + ln) * math.cos(a), cy + (R + ln) * math.sin(a))
        con.stroke(str(pd))

    # ---------------- the pizza's own shapes (polar)
    lump = harmonics(rng, [(2, 2.5), (7, 2.2), (11, 3.0), (17, 2.0), (29, 1.0)])
    lump2 = harmonics(rng, [(5, 1.2), (13, 1.6)])

    def r_out(t):
        return RP - 2 + lump(t) + 2.2 * (abs(math.sin(6.5 * t + 0.7)) - 0.6) + lump2(t) * 0.5

    rin_n = harmonics(rng, [(3, 3.0), (9, 2.6), (19, 1.6)])

    def r_in(t):
        return RP - 42 + rin_n(t) + 0.4 * lump(t)

    ch_n = harmonics(rng, [(4, 5.0), (7, 4.2), (13, 3.0), (23, 1.6)])

    def r_ch(t):
        v = RP - 64 + ch_n(t) + 4.5 * max(0.0, math.sin(11 * t + 1.3)) ** 6
        return min(v, r_in(t) - 6)

    def polar(fn, n=360, dr=0.0):
        return [(cx + (fn(t) + dr) * math.cos(t), cy + (fn(t) + dr) * math.sin(t))
                for t in (TAU * i / n for i in range(n))]

    def pol(x, y):
        dx, dy = x - cx, y - cy
        return math.hypot(dx, dy), math.atan2(dy, dx)

    outer = polar(r_out)
    inner = polar(r_in)
    cheese = polar(r_ch)

    # ---------------- toppings
    items = []

    def far_enough(p, rad, kinds, factor):
        for it in items:
            if it['kind'] in kinds and math.dist(p, it['c']) < (rad + it['r']) * factor:
                return False
        return True

    def best_candidate(rad, maxr, kinds, factor, k=14):
        best, bestd = None, -1
        for _ in range(400):
            rr = maxr * math.sqrt(rng.random())
            th = rng.uniform(0, TAU)
            p = (cx + rr * math.cos(th), cy + rr * math.sin(th))
            if not far_enough(p, rad, kinds, factor):
                continue
            d = min([math.dist(p, it['c']) - it['r'] for it in items] + [maxr - rr + rad + 30])
            if d > bestd:
                best, bestd = p, d
            k -= 1
            if k <= 0:
                break
        return best

    solid = ('pep', 'mush')
    for i in range(12):
        r = rng.uniform(30.5, 35)
        p = best_candidate(r, 248 - r, solid, 1.08)
        if p:
            items.append({'kind': 'pep', 'c': p, 'r': r})
    for i in range(8):
        p = best_candidate(38, 206, solid, 1.0)
        if p:
            items.append({'kind': 'mush', 'c': p, 'r': 38})
    # three pepperoni overlapping a neighbour, as on a real pizza
    peps = [it for it in items if it['kind'] == 'pep']
    added = 0
    for base in sorted(peps, key=lambda it: rng.random()):
        if added == 3:
            break
        r = rng.uniform(30.5, 34)
        for _ in range(60):
            a = rng.uniform(0, TAU)
            d = (r + base['r']) * rng.uniform(0.66, 0.8)
            p = (base['c'][0] + d * math.cos(a), base['c'][1] + d * math.sin(a))
            if math.dist(p, (cx, cy)) > 248 - r:
                continue
            if all(math.dist(p, it['c']) > (r + it['r']) * 0.98 for it in items if it is not base):
                items.append({'kind': 'pep', 'c': p, 'r': r, 'over': True})
                added += 1
                break
    for i in range(8):
        p = best_candidate(30, 222, ('pep', 'mush', 'onion'), 0.8)
        if p:
            items.append({'kind': 'onion', 'c': p, 'r': 30})
    for i in range(8):
        p = best_candidate(38, 214, ('pep', 'mush', 'pepper', 'onion'), 0.72) or best_candidate(36, 218, ('pepper', 'mush'), 0.6)
        if p:
            items.append({'kind': 'pepper', 'c': p, 'r': 38})
    order = {'pep': 0, 'mush': 1, 'onion': 2, 'pepper': 3}
    items.sort(key=lambda it: (order[it['kind']], it.get('over', False)))

    # shapes for every topping
    for it in items:
        x, y = it['c']
        k = it['kind']
        if k == 'pep':
            r = it['r']
            hw = harmonics(rng, [(3, 0.022), (5, 0.014), (2, 0.012)])
            it['poly'] = [(x + r * (1 + hw(t)) * math.cos(t), y + r * (1 + hw(t)) * math.sin(t))
                          for t in (TAU * i / 72 for i in range(72))]
            it['shape'] = Poly(it['poly'])
        elif k == 'mush':
            s = rng.uniform(1.12, 1.3)
            a = rng.uniform(0, TAU)
            ctrl = mushroom_outline(rng)
            it['local'] = (x, y, a, s)
            it['poly'] = xform(ctrl, x, y, a, s)
            it['shape'] = Poly(it['poly'])
            it['r'] = 34 * s
        elif k == 'onion':
            ro = rng.uniform(19, 29)
            wdt = rng.uniform(5.6, 7.2)
            full = rng.random() < 0.55
            a0 = rng.uniform(0, TAU)
            span = TAU if full else rng.uniform(math.radians(150), math.radians(250))
            ex = rng.uniform(0.9, 1.1)
            it.update(ro=ro, ri=ro - wdt, full=full, a0=a0, span=span, ex=ex, rot=rng.uniform(0, TAU))

            def ring(rr, n, a0=a0, span=span, x=x, y=y, ex=ex, rt=it['rot'], full=full):
                m = n if full else n
                return [rot((x + rr * ex * math.cos(a0 + span * i / (m if full else m - 1)),
                             y + rr / ex * math.sin(a0 + span * i / (m if full else m - 1))), 0)
                        for i in range(m)]
            it['outer'] = ring(ro, 48)
            it['inner'] = ring(ro - wdt, 44)
            if full:
                it['shape'] = Poly(it['outer'], [it['inner']])
            else:
                # rounded cut ends
                e1 = [((it['outer'][-1][0] + it['inner'][-1][0]) / 2 + (it['outer'][-1][0] - it['outer'][-2][0]) * 0.3,
                       (it['outer'][-1][1] + it['inner'][-1][1]) / 2 + (it['outer'][-1][1] - it['outer'][-2][1]) * 0.3)]
                e0 = [((it['outer'][0][0] + it['inner'][0][0]) / 2 - (it['outer'][1][0] - it['outer'][0][0]) * 0.3,
                       (it['outer'][0][1] + it['inner'][0][1]) / 2 - (it['outer'][1][1] - it['outer'][0][1]) * 0.3)]
                it['poly'] = it['outer'] + e1 + it['inner'][::-1] + e0
                it['shape'] = Poly(it['poly'])
            it['r'] = ro
        elif k == 'pepper':
            rr = rng.uniform(44, 66)
            ln = rng.uniform(78, 98)
            wdt = rng.uniform(9.5, 12.5)
            span = ln / rr
            a = rng.uniform(0, TAU)
            # arc centre so that the strip's middle sits at the item centre
            ac = (x - rr * math.cos(a), y - rr * math.sin(a))
            n = 26
            outer_a = [(ac[0] + rr * math.cos(a - span / 2 + span * i / (n - 1)),
                        ac[1] + rr * math.sin(a - span / 2 + span * i / (n - 1))) for i in range(n)]
            taper = [1 - 0.45 * abs(2 * i / (n - 1) - 1) ** 3 for i in range(n)]
            inner_a = [(ac[0] + (rr - wdt * taper[i]) * math.cos(a - span / 2 + span * i / (n - 1)),
                        ac[1] + (rr - wdt * taper[i]) * math.sin(a - span / 2 + span * i / (n - 1))) for i in range(n)]
            it.update(ac=ac, rr=rr, span=span, a=a, wdt=wdt, outer=outer_a, inner=inner_a)
            ends = []
            p_o, p_i = outer_a[-1], inner_a[-1]
            cap1 = [((p_o[0] + p_i[0]) / 2 + (p_o[0] - outer_a[-2][0]) * 0.35, (p_o[1] + p_i[1]) / 2 + (p_o[1] - outer_a[-2][1]) * 0.35)]
            p_o, p_i = outer_a[0], inner_a[0]
            cap0 = [((p_o[0] + p_i[0]) / 2 - (outer_a[1][0] - p_o[0]) * 0.35, (p_o[1] + p_i[1]) / 2 - (outer_a[1][1] - p_o[1]) * 0.35)]
            _ = ends
            it['poly'] = outer_a + cap1 + inner_a[::-1] + cap0
            it['shape'] = Poly(it['poly'])
            it['r'] = ln / 2

    def occluders_of(i):
        it = items[i]
        return [o['shape'] for o in items[i + 1:] if math.dist(o['c'], it['c']) < o['r'] + it['r'] + 6]

    # ---------------- washes (bottom to top)
    inner_under = polar(r_in, 200, dr=-5)
    washes += wash('crust', polar(r_out, 220), rng, ((0.85, 1.6), (0.4, 2.8)), holes=[inner_under], seg=40)
    # crust shadow side (outer, lower right) and inner wall (upper left)
    def crust_band_w(p, n):
        _, t = pol(*p)
        return 15 * max(0.0, math.cos(t - math.radians(48))) ** 1.4
    b = band(polar(r_out, 220, dr=0.5), crust_band_w)
    if b:
        washes += wash('crust-dark', b, rng, ((0.42, 2.2), (0.24, 3.4)), seg=16)
    b2 = band(polar(r_in, 200, dr=-2), lambda p, n: 9 * max(0.0, math.cos(pol(*p)[1] - math.radians(225))) ** 1.6)
    if b2:
        washes += wash('crust-dark', b2, rng, ((0.36, 1.8),), seg=14)
    washes += wash('sauce', polar(r_in, 200, dr=1.5), rng, ((0.88, 1.4), (0.4, 2.6)),
                   holes=[polar(r_ch, 200, dr=-4)], seg=32)
    washes += wash('cheese', cheese, rng, ((0.9, 1.8), (0.36, 2.8), (0.24, 4.0)), seg=26)
    # the crown of the crust catches the light on the upper left
    hlb = band(polar(lambda t: (r_out(t) + r_in(t)) / 2 + 4, 200),
               lambda p, n: 9 * max(0.0, math.cos(pol(*p)[1] - math.radians(222))) ** 1.3)
    if hlb:
        washes += wash('cheese', hlb, rng, ((0.38, 2.6),), seg=18)
    # blisters on the crust
    blisters = []
    for _ in range(22):
        t = rng.uniform(0, TAU)
        rr = rng.uniform(r_in(t) + 9, r_out(t) - 7)
        p = (cx + rr * math.cos(t), cy + rr * math.sin(t))
        br = rng.uniform(2.4, 6.5)
        blisters.append((p, br))
        washes += wash('crust-dark', ellipse(p[0], p[1], br * 1.3, br, rng.uniform(0, TAU), 7), rng,
                       ((0.55, 0.8),), seg=max(3.0, br * 1.6))
    # browned spots on the cheese (leopard browning)
    for _ in range(18):
        for _try in range(40):
            rr = 250 * math.sqrt(rng.uniform(0.15, 1))
            t = rng.uniform(0, TAU)
            p = (cx + rr * math.cos(t), cy + rr * math.sin(t))
            if rr < r_ch(t) - 12:
                break
        sr = rng.uniform(6, 16)
        blob = [(p[0] + sr * (1 + 0.3 * math.sin(3 * a + sr)) * math.cos(a),
                 p[1] + sr * 0.8 * (1 + 0.25 * math.sin(2 * a + sr)) * math.sin(a)) for a in (TAU * i / 12 for i in range(12))]
        washes += wash('char', blob, rng, ((0.32 if rng.random() < 0.6 else 0.46, 1.4),), seg=8)

    # toppings, kind by kind, pass by pass (one merged path per pass)
    for kind in ('pep', 'mush', 'onion', 'pepper'):
        group_ = [it for it in items if it['kind'] == kind]
        off = 5.0 if kind in ('pep', 'mush') else 3.4
        for it in group_:
            # the topping's soft cast shadow on what lies beneath (light from the upper left)
            sh = band(it['poly'] if 'poly' in it else it['outer'],
                      lambda p, n, off=off: off * max(0.0, n[0] * 0.7071 + n[1] * 0.7071) ** 0.8, outward=True)
            if sh:
                washes += wash('char', sh, rng, ((0.42, 0.6),), shift=0.3, seg=12)
        if kind == 'pep':
            for op, spread, sh_ in ((0.94, 1.0, 1.2), (0.4, 1.6, 1.4)):
                for it in group_:
                    washes += wash('pepperoni', it['poly'], rng, ((op, spread),), shift=sh_, seg=17)
            for it in group_:
                x, y = it['c']
                rim_i = [(x + (px - x) * 0.8 + 1.2, y + (py - y) * 0.8 + 1.2) for px, py in it['poly']]
                washes += wash('pepperoni', it['poly'], rng, ((0.6, 0.8),), shift=0.6, holes=[rim_i], seg=17)
            for it in group_:   # dark specks of spice in the slices
                x, y = it['c']
                for _ in range(3):
                    a = rng.uniform(0, TAU)
                    d = rng.uniform(0, it['r'] * 0.6)
                    sp = (x + d * math.cos(a), y + d * math.sin(a))
                    washes += wash('char', ellipse(sp[0], sp[1], rng.uniform(1.5, 2.4), rng.uniform(1.0, 1.7),
                                                   rng.uniform(0, TAU), 5), rng, ((0.7, 0.2),), shift=0.1, seg=3)
        elif kind == 'mush':
            for op, spread in ((0.92, 1.0), (0.4, 1.6)):
                for it in group_:
                    washes += wash('mushroom', it['poly'], rng, ((op, spread),), shift=1.0, seg=11)
            for it in group_:
                x, y, a, s = it['local']
                for side in (-1, 1):
                    pocket = xform(smooth_poly(mushroom_pocket(side), True, 3), x, y, a, s)
                    washes += wash('char', pocket, rng, ((0.42, 0.5),), shift=0.4, seg=6)
            for it in group_:
                x, y, a, s = it['local']
                b3 = band(it['poly'], lambda p, n, x=x, y=y, s=s: 3.2 if math.dist(p, (x, y)) > 18 * s else 0.0)
                if b3:
                    washes += wash('crust-dark', b3, rng, ((0.28, 0.6),), shift=0.4, seg=8)
        elif kind == 'onion':
            for op, spread in ((0.9, 0.7),):
                for it in group_:
                    holes = [it['inner']] if it['full'] else ()
                    pts = it['outer'] if it['full'] else it['poly']
                    washes += wash('onion', pts, rng, ((op, spread),), shift=0.7, holes=holes, seg=13)
        else:
            for op, spread in ((0.94, 0.8),):
                for it in group_:
                    washes += wash('pepper', it['poly'], rng, ((op, spread),), shift=0.8, seg=10)
            for it in group_:
                skin = it['outer'] + [(it['ac'][0] + (it['rr'] - 4) * math.cos(it['a'] + it['span'] / 2 - it['span'] * i / 25),
                                       it['ac'][1] + (it['rr'] - 4) * math.sin(it['a'] + it['span'] / 2 - it['span'] * i / 25))
                                      for i in range(26)]
                washes += wash('pepper', skin, rng, ((0.45, 0.5),), shift=0.4, seg=10)

    # ---------------- hatching
    nz = noise2(rng, 5, 70)
    # eight faint slice cuts, broken where the knife skipped
    t0 = rng.uniform(0, TAU / 8)
    for k in range(8):
        t = t0 + k * TAU / 8 + rng.uniform(-0.02, 0.02)
        r1 = r_in(t) - 6
        pieces = []
        r = rng.uniform(6, 14)
        while r < r1:
            ln = rng.uniform(70, 150)
            e = min(r + ln, r1)
            pieces.append((r, e))
            r = e + rng.uniform(5, 12)
        for a, e in pieces:
            bend = rng.uniform(-0.006, 0.006)
            pts = [(cx + rr * math.cos(t + bend * (rr - a) / 40), cy + rr * math.sin(t + bend * (rr - a) / 40))
                   for rr in (a + (e - a) * j / 6 for j in range(7))]
            hat.strokes(ink(pts, False, rng, passes=1, wob=0.4, over=0, seg=30))

    # cast shadow of the pizza on the table (lower right) and its darkest core
    def cast_w(t):
        return 22 * max(0.0, math.cos(t - math.radians(46))) ** 1.8

    def in_cast(x, y, r):
        d, t = pol(x, y)
        ro = r_out(t)
        return ro + 2 < d < ro + cast_w(t) * (0.9 + 0.08 * nz(x, y))

    hat.hatches(hatch(rng, (cx - 20, cy - 20, cx + RP + 40, cy + RP + 40), in_cast, spacing=6.8, minlen=5,
                      trim=0.12))

    def in_cast_dark(x, y, r):
        d, t = pol(x, y)
        ro = r_out(t)
        return ro + 2 < d < ro + cast_w(t) * 0.5 and math.cos(t - math.radians(46)) > 0.6

    hat.hatches(hatch(rng, (cx - 20, cy - 20, cx + RP + 40, cy + RP + 40), in_cast_dark, spacing=7,
                      angle=CROSS, minlen=4, trim=0.1))

    # the crust as a torus lit from the upper left
    def crust_shade(x, y):
        d, t = pol(x, y)
        ro, ri = r_out(t), r_in(t)
        s = (d - ri) / (ro - ri)
        if s < 0 or s > 1:
            return -1
        phi = math.pi * s
        ux, uy = (x - cx) / d, (y - cy) / d
        nr, nzz = -math.cos(phi), math.sin(phi)
        lam = ux * nr * LIGHT[0] + uy * nr * LIGHT[1] + nzz * LIGHT[2]
        return (1 - lam) / 2

    def in_crust(x, y, r):
        v = crust_shade(x, y)
        return v > 0.6 + 0.1 * nz(x * 1.7, y * 1.7) + 0.1 * (r - 0.5)

    hat.hatches(hatch(rng, (cx - RP - 6, cy - RP - 6, cx + RP + 6, cy + RP + 6), in_crust, spacing=8.4, minlen=6))

    def in_crust_dark(x, y, r):
        return crust_shade(x, y) > 0.8 + 0.05 * nz(x, y)

    hat.hatches(hatch(rng, (cx - RP - 6, cy - RP - 6, cx + RP + 6, cy + RP + 6), in_crust_dark, spacing=7.5,
                      angle=CROSS, minlen=4))

    # the crust's own shadow falling on the sauce, upper left
    def in_rim_shadow(x, y, r):
        d, t = pol(x, y)
        w = 16 * max(0.0, math.cos(t - math.radians(225))) ** 1.5
        return r_in(t) - w * (0.7 + 0.3 * r) < d < r_in(t) - 1

    hat.hatches(hatch(rng, (cx - RP, cy - RP, cx + 40, cy + 40), in_rim_shadow, spacing=7.4, minlen=6))

    # toppings: the cup of each pepperoni, the cast shadows of everything
    for i, it in enumerate(items):
        x, y = it['c']
        occ = [o['shape'] for o in items[i + 1:] if math.dist(o['c'], it['c']) < o['r'] + it['r'] + 10]
        k = it['kind']
        if k == 'pep':
            r = it['r']

            def cup(px, py, rr, x=x, y=y, r=r, occ=occ):
                return (math.dist((px, py), (x, y)) < r * 0.8 and
                        math.dist((px, py), (x + r * 0.3, y + r * 0.3)) > r * 0.8 and
                        not any((px, py) in o for o in occ))

            hat.hatches(hatch(rng, (x - r, y - r, x + r, y + r), cup, spacing=7.8, minlen=5, bow=0.6))
        if k == 'mush':
            mx, my, a, s = it['local']
            for side in (-1, 1):
                for g in mushroom_gills(side):
                    pts = xform(g, mx, my, a, s)
                    if not any(pp in o for o in occ for pp in pts):
                        hat.stroke(spline(pts))
            stem = xform([(-3.5, 12), (-3, 20), (-2.6, 27)], mx, my, a, s)
            stem2 = xform([(3.2, 13), (3.6, 21)], mx, my, a, s)
            for st in (stem, stem2):
                if not any(pp in o for o in occ for pp in st):
                    hat.stroke(spline(st))

    # ---------------- ink contours
    lin.strokes(ink(outer, True, rng, passes=3, wob=1.1, drift=1.7, part=(0.35, 0.6), seg=16))
    lin.strokes(ink(inner, True, rng, passes=2, wob=0.9, drift=1.4, part=(0.25, 0.5), seg=17))
    occ_all = [it['shape'] for it in items]
    lin.strokes(ink(cheese, True, rng, passes=2, wob=1.0, drift=1.8, part=(0.3, 0.55), seg=14, occluders=occ_all))
    for i, it in enumerate(items):
        occ = occluders_of(i)
        k = it['kind']
        x, y = it['c']
        if k == 'pep':
            r = it['r']
            lin.strokes(ink(it['poly'], True, rng, passes=2, wob=0.5, drift=0.9, part=(0.25, 0.45), occluders=occ,
                            seg=11))
            a0 = math.radians(rng.uniform(95, 130))
            lip = ellipse(x + 0.6, y + 0.6, r * 0.8, r * 0.8, 0, 30, a0, a0 + math.radians(rng.uniform(190, 230)), True)
            lin.strokes(ink(lip, False, rng, passes=1, wob=0.35, over=1.5, occluders=occ, seg=8))
        elif k == 'mush':
            mx, my, a, s = it['local']
            lin.strokes(ink(it['poly'], True, rng, passes=2, wob=0.45, drift=0.8, part=(0.3, 0.5), occluders=occ,
                            seg=8))
            for side in (-1, 1):
                arc = xform(mushroom_pocket(side)[:7], mx, my, a, s)
                lin.strokes(ink(arc, False, rng, passes=1, wob=0.25, over=1.0, occluders=occ, seg=5))
        elif k == 'onion':
            if it['full']:
                lin.strokes(ink(it['outer'], True, rng, passes=1, wob=0.35, drift=0.7, over=6, occluders=occ, seg=6))
                lin.strokes(ink(it['inner'], True, rng, passes=1, wob=0.3, drift=0.6, over=4, occluders=occ, seg=6))
                mid = [((po[0] + pi_[0]) / 2, (po[1] + pi_[1]) / 2) for po, pi_ in zip(it['outer'][::2], it['inner'][::2])]
                lin.strokes(ink(mid[:rng.randint(6, 12)], False, rng, passes=1, wob=0.2, over=0, occluders=occ, seg=6),
                            'art-hatch')
            else:
                lin.strokes(ink(it['poly'], True, rng, passes=2, wob=0.35, drift=0.7, part=(0.3, 0.5),
                                occluders=occ, seg=6))
        elif k == 'pepper':
            lin.strokes(ink(it['poly'], True, rng, passes=2, wob=0.4, drift=0.8, part=(0.35, 0.6), occluders=occ,
                            seg=7))
            n = len(it['outer'])
            a_, b_ = int(n * rng.uniform(0.1, 0.3)), int(n * rng.uniform(0.6, 0.9))
            skin = [(it['ac'][0] + (it['rr'] - 2.6) * math.cos(it['a'] - it['span'] / 2 + it['span'] * j / (n - 1)),
                     it['ac'][1] + (it['rr'] - 2.6) * math.sin(it['a'] - it['span'] / 2 + it['span'] * j / (n - 1)))
                    for j in range(a_, b_)]
            lin.strokes(ink(skin, False, rng, passes=1, wob=0.2, over=0, occluders=occ, seg=7), 'art-hatch')

    # bubbles in the melted cheese and blisters on the crust
    bubbles = 0
    tries = 0
    while bubbles < 7 and tries < 600:
        tries += 1
        rr = 240 * math.sqrt(rng.random())
        t = rng.uniform(0, TAU)
        p = (cx + rr * math.cos(t), cy + rr * math.sin(t))
        br = rng.uniform(3.5, 8)
        if rr > r_ch(t) - br - 6 or any(math.dist(p, it['c']) < it['r'] + br + 4 for it in items):
            continue
        bubbles += 1
        lin.strokes(ink(ellipse(p[0], p[1], br, br * 0.82, rng.uniform(0, TAU), 14), True, rng, passes=1,
                        wob=0.15, drift=0.3, over=1.5, seg=3.5))
        washes += wash('char', ellipse(p[0] + br * 0.25, p[1] + br * 0.25, br * 1.05, br * 0.9, 0, 10), rng,
                       ((0.3, 0.4),), shift=0.3, seg=3)
    for p, br in sorted(blisters, key=lambda b: -b[1])[:7]:
        lin.strokes(ink(ellipse(p[0], p[1], br * 1.2, br * 0.9, rng.uniform(0, TAU), 12), True, rng, passes=1,
                        wob=0.12, drift=0.25, over=1.0, seg=3.5))

    # ---------------- anchors (spread around the drawing)
    def pick(kind, target_deg):
        best = None
        for it in items:
            if it['kind'] != kind:
                continue
            dx, dy = it['c'][0] - cx, it['c'][1] - cy
            d = math.hypot(dx, dy)
            score = abs(math.remainder(math.atan2(dy, dx) - math.radians(target_deg), TAU)) + abs(d - 150) / 300
            if best is None or score < best[0]:
                best = (score, it)
        return best[1]

    anchors = {}
    t = math.radians(-62)
    anchors['crust'] = (cx + (r_out(t) + r_in(t)) / 2 * math.cos(t), cy + (r_out(t) + r_in(t)) / 2 * math.sin(t))
    t = math.radians(158)
    anchors['sauce'] = (cx + (r_in(t) + r_ch(t)) / 2 * math.cos(t), cy + (r_in(t) + r_ch(t)) / 2 * math.sin(t))
    pp = pick('pep', 215)
    anchors['pepperoni'] = pp['c']
    mm = pick('mush', 300)
    anchors['mushroom'] = xform([(0, -8)], *mm['local'][:3], mm['local'][3])[0]
    gp = pick('pepper', 35)
    mid = gp['outer'][len(gp['outer']) // 2]
    anchors['pepper'] = (mid[0] + (gp['ac'][0] - mid[0]) * gp['wdt'] / 2 / gp['rr'],
                         mid[1] + (gp['ac'][1] - mid[1]) * gp['wdt'] / 2 / gp['rr'])
    on = pick('onion', 120)
    o0, i0 = on['outer'][len(on['outer']) // 3], on['inner'][len(on['inner']) // 3]
    anchors['onion'] = ((o0[0] + i0[0]) / 2, (o0[1] + i0[1]) / 2)
    # cheese: the open cheese point farthest from every topping, near a target direction
    best = None
    for _ in range(3000):
        rr = 230 * math.sqrt(rng.random())
        t = rng.uniform(0, TAU)
        p = (cx + rr * math.cos(t), cy + rr * math.sin(t))
        if rr > r_ch(t) - 20:
            continue
        clear = min(math.dist(p, it['c']) - it['r'] for it in items)
        others = min(math.dist(p, q) for q in anchors.values())
        score = min(clear, 30) + min(others, 120) * 0.3
        if best is None or score > best[0]:
            best = (score, p)
    anchors['cheese'] = best[1]
    anchors = {k: (round(v[0], 1), round(v[1], 1)) for k, v in anchors.items()}
    order_names = ['crust', 'sauce', 'cheese', 'pepperoni', 'pepper', 'onion', 'mushroom']
    dots = [f'<circle class="art-dot" r="5" data-note="{k}" cx="{_ft(_t(anchors[k][0]))}" cy="{_ft(_t(anchors[k][1]))}"/>'
            for k in order_names]

    body = ('<defs>' + wash_filter('pz-washfx', 11) + '</defs>'
            + group('id="pz-construction" class="art-group art-group--construction"', con.items, con.n)
            + group('id="pz-wash" class="art-group art-group--wash" filter="url(#pz-washfx)"', washes)
            + group('id="pz-hatch" class="art-group art-group--hatch"', hat.items, hat.n)
            + group('id="pz-line" class="art-group art-group--line"', lin.items, lin.n)
            + group('id="pz-anchors"', dots))
    svg = svg_root('0 0 1000 1000', 'codex-art codex-art--pizza', body)
    meta = {'viewBox': [0, 0, 1000, 1000], 'anchors': {k: list(anchors[k]) for k in order_names}}
    stats = {'construction': con.n, 'wash': len(washes), 'hatch': hat.n, 'line': lin.n,
             'toppings': {k: sum(1 for it in items if it['kind'] == k) for k in order}}
    return svg, meta, stats


# --------------------------------------------------------------------------- the burger

LAYERS = ['heel', 'patty-low', 'cheese-low', 'patty-top', 'cheese-top', 'pickles', 'sauce', 'crown']


def build_burger():
    rng = random.Random(1519)          # the year of the Codex Atlanticus' last pages
    CX = 500.0
    nz = noise2(rng, 5, 50)
    L = {k: {'wash': [], 'hatch': Layer('art-hatch'), 'line': Layer('art-line'), 'shapes': []} for k in LAYERS}

    def noisy(pts, rng, amp, scales=(60.0, 23.0, 9.0)):
        c = Curve(pts, True)
        w = wobble(rng, amp, scales)
        out = []
        for i in range(len(pts)):
            s = c.cum[i]
            x, y = pts[i]
            nx, ny = c.normal(s)
            o = w(s)
            out.append((x + nx * o, y + ny * o))
        return out

    # ---------------- crown: a tall glossy dome
    top = superellipse(CX, 480, 293, 190, 2.35, math.pi, TAU, 70)          # left -> over the top -> right
    bot = superellipse(CX, 480, 293, 11, 5.0, 0.0, math.pi, 40)[1:-1]      # right -> under -> left
    crown = noisy(top + bot, rng, 1.6)
    crown_poly = Poly(crown)
    L['crown']['shapes'].append(crown)

    # ---------------- heel
    htop = superellipse(CX, 648, 280, 47, 9.0, math.pi, TAU, 50)
    hbot = superellipse(CX, 648, 280, 50, 3.0, 0.0, math.pi, 50)[1:-1]
    heel = noisy(htop + hbot, rng, 1.3)
    heel_poly = Poly(heel)
    L['heel']['shapes'].append(heel)

    # ---------------- patties: thin, wide, with a lacy, crisp brim that overhangs the bun
    def patty(yc, r):
        hw = 292.0
        tn = wobble(r, 1.8, (36.0, 13.0, 5.5))
        bn = wobble(r, 1.3, (50.0, 19.0, 7.0))
        sag = r.uniform(-2.5, 2.5)
        n = 110
        topl, botl = [], []
        for i in range(n + 1):
            u = -1 + 2 * i / n
            x = CX + hw * u
            T = 25 * (1 - abs(u) ** 7) ** 0.6 + 9
            ym = yc + sag * (1 - u * u)
            topl.append((x, ym - T * 0.53 + tn(x) * (0.7 + abs(u)) + r.uniform(-0.7, 0.7)))
            botl.append((x, ym + T * 0.47 + bn(x) * (0.6 + abs(u)) + r.uniform(-0.4, 0.4)))

        def brim(direction, p_top, p_bot):
            length = r.uniform(20, 30)
            curl = r.uniform(-7, 4)
            m = 9
            tops, bots = [], []
            for j in range(1, m + 1):
                f = j / m
                x = p_top[0] + direction * length * f
                yc_ = (p_top[1] + p_bot[1]) / 2 + curl * f * f
                th = (p_bot[1] - p_top[1]) * (1 - 0.6 * f) * (0.75 + 0.25 * math.sin(j * 2.1 + direction)) + 0.8
                bump = 1.6 if j % 2 else -0.6
                tops.append((x + r.uniform(-0.8, 0.8), yc_ - th / 2 - bump + r.uniform(-1.2, 0.6)))
                bots.append((x + r.uniform(-0.8, 0.8), yc_ + th / 2 + bump * 0.7 + r.uniform(-0.6, 1.2)))
            base = ((tops[-1][0] + bots[-1][0]) / 2, (tops[-1][1] + bots[-1][1]) / 2)
            tip = []
            for k in range(3):
                a = -0.9 + 0.9 * k + r.uniform(-0.25, 0.25)
                ln_ = r.uniform(2.5, 6.5)
                tip.append((base[0] + direction * ln_ * math.cos(a), base[1] + ln_ * math.sin(a)))
                if k < 2:
                    tip.append((base[0] + direction * r.uniform(0, 2.5), base[1] - 1.5 + 2.6 * k + r.uniform(-0.6, 0.6)))
            return tops, tip, bots

        rt, rtip, rb = brim(1, topl[-1], botl[-1])
        lt, ltip, lb = brim(-1, topl[0], botl[0])
        outline = topl + rt + rtip + rb[::-1] + botl[::-1] + lb + ltip[::-1] + lt[::-1]
        k = 6   # the crisp brims, with a little of the body's edge
        brims = [topl[-k:] + rt + rtip + rb[::-1] + botl[-k:][::-1], botl[:k] + lb + ltip[::-1] + lt[::-1] + topl[:k][::-1]]
        holes = []
        for side in (-1, 1):
            tries = 0
            while tries < 40 and len([h for h in holes if (h[0][0] - CX) * side > 0]) < 6:
                tries += 1
                u = side * r.uniform(0.78, 0.985)
                i = int(round((u + 1) / 2 * n))
                y0, y1 = topl[i][1], botl[i][1]
                hr = r.uniform(1.4, 2.8)
                if y1 - y0 < 2 * hr + 5:
                    continue
                hy = r.uniform(y0 + hr + 2.2, y1 - hr - 2.2)
                hx = CX + hw * u
                if any(math.dist((hx, hy), (sum(p[0] for p in h) / len(h), sum(p[1] for p in h) / len(h))) < 9
                       for h in holes):
                    continue
                holes.append(ellipse(hx, hy, hr * r.uniform(1.2, 1.9), hr, r.uniform(-0.4, 0.4), 10))
        return outline, topl, botl, holes, brims

    pt_out, pt_top, pt_bot, pt_holes, pt_brims = patty(540.0, random.Random(7))
    pl_out, pl_top, pl_bot, pl_holes, pl_brims = patty(581.0, random.Random(19))

    # ---------------- cheese slices: a thin slab with melted corners and drips over the patty
    def cheese(ytop, x0, x1, tongues, drips, r):
        n = 140
        topl, botl = [], []
        tw = wobble(r, 0.8, (50.0, 17.0, 7.0))
        for i in range(n + 1):
            u = i / n
            x = x0 + (x1 - x0) * u
            droop = 5 * (abs(2 * u - 1) ** 6)
            topl.append((x, ytop + droop + tw(x) * 0.5))
            hang = 0.0
            for xc, w, h, skew in tongues:
                d = (x - xc) / w
                if abs(d) < 1:
                    ds = d - skew * (1 - d * d) * 0.6
                    prof = max(0.0, 1 - ds * ds) ** 1.5
                    hang = max(hang, h * prof * (1 + 0.06 * math.sin(d * 9 + xc)))
            for xc, w, h in drips:
                d = (x - xc) / w
                if abs(d) < 1:
                    hang = max(hang, h * math.cos(d * math.pi / 2) ** 2.2)
            botl.append((x, ytop + 8.5 + droop + hang + tw(x + 40) * 0.6))
        outline = topl + [(x1 + 2.5, ytop + 9.5)] + botl[::-1] + [(x0 - 2.5, ytop + 9.5)]
        drops = [ellipse(xc, ytop + 8.5 + h - w * 0.15, w * 0.78, w * 0.9, 0, 14) for xc, w, h in drips if h > 20]
        return outline, drops

    ct, ct_drops = cheese(515.0, 238.0, 763.0, [(330, 30, 26, 0.3), (588, 42, 33, -0.25)],
                          [(614, 7, 50), (462, 6, 16), (742, 8, 22)], random.Random(5))
    cl, cl_drops = cheese(556.0, 232.0, 769.0, [(420, 46, 29, 0.2), (690, 30, 22, -0.3)],
                          [(272, 7, 31), (540, 6, 15)], random.Random(9))

    # ---------------- pickles: three crinkle-cut slices, nearly edge-on, tilted
    pickles = []
    for (px, py, ang, rx) in ((352, 509.5, -0.08, 66), (500, 507.5, 0.06, 70), (648, 510, -0.05, 65)):
        n = 72
        pts = []
        for i in range(n):
            t = TAU * i / n
            crinkle = 1 + 0.04 * math.sin(16 * t) * (abs(math.cos(t)) ** 0.3)
            pts.append(rot((px + rx * crinkle * math.cos(t), py + 11.5 * crinkle * math.sin(t)), ang, (px, py)))
        pickles.append((pts, (px, py, ang, rx)))

    # ---------------- sauce under the crown, dripping over the pickles
    sauce_drips = [(300, 9, 24), (612, 8, 36), (724, 7, 16), (450, 6, 12)]
    n = 110
    s_top, s_bot = [], []
    sw = wobble(rng, 1.4, (40.0, 13.0, 6.0))
    for i in range(n + 1):
        u = i / n
        x = 236 + (764 - 236) * u
        s_top.append((x, 483 + sw(x) * 0.3))
        hang = 0.0
        for xc, w, h in sauce_drips:
            d = (x - xc) / w
            if abs(d) < 1:
                hang = max(hang, h * math.cos(d * math.pi / 2) ** 2.2)
        s_bot.append((x, 499 + sw(x) + hang + 1.6 * math.sin(u * 7)))
    sauce = s_top + [(767, 492)] + s_bot[::-1] + [(233, 492)]
    sauce_drop = [ellipse(xc, 499 + h - w * 0.15, w * 0.75, w * 0.88, 0, 12) for xc, w, h in sauce_drips if h > 20]

    # ---------------- washes per layer
    W = lambda k: L[k]['wash']
    # heel: golden body, a darker baked bottom, a shadowed right side, the toasted cut face on top
    W('heel').extend(wash('bun', heel, rng, ((0.9, 1.6), (0.4, 2.6), (0.24, 3.2)), seg=16))
    hb = band(heel, lambda p, n: 20 * max(0.0, (p[1] - 652) / 46) ** 1.1 + 16 * max(0.0, (p[0] - 600) / 180) ** 1.6)
    if hb:
        W('heel').extend(wash('bun-top', hb, rng, ((0.55, 2.0), (0.3, 3.0)), seg=12))
    ht = band(heel, lambda p, n: 6.5 if p[1] < 612 and n[1] < -0.5 else 0.0)
    if ht:
        W('heel').extend(wash('crust-dark', ht, rng, ((0.4, 1.2),), seg=10))
    # patties: dark meat, a seared crust top and bottom, the crisp brim darker still, lace holes open
    for key, out, holes, topl, botl, brims in (('patty-top', pt_out, pt_holes, pt_top, pt_bot, pt_brims),
                                               ('patty-low', pl_out, pl_holes, pl_top, pl_bot, pl_brims)):
        W(key).extend(wash('patty', out, rng, ((0.94, 0.8), (0.45, 1.3)), holes=holes, seg=8, shift=0.9))
        sear = botl[::-1] + [(x, y - 7 - 2.5 * math.sin(x / 9)) for x, y in botl]
        W(key).extend(wash('patty-edge', sear, rng, ((0.6, 1.0),), seg=10, shift=0.8))
        crust_top = topl + [(x, y + 4.5 + 1.5 * math.sin(x / 7)) for x, y in topl[::-1]]
        W(key).extend(wash('patty-edge', crust_top, rng, ((0.45, 0.8),), seg=10, shift=0.6))
        for b_ in brims:
            W(key).extend(wash('patty-edge', b_, rng, ((0.6, 0.5),), seg=5, shift=0.3))
    # cheese: bright slab and melted corners, a thin shadow line under the edge
    for key, out, dr in (('cheese-top', ct, ct_drops), ('cheese-low', cl, cl_drops)):
        W(key).extend(wash('cheese', out, rng, ((0.95, 0.9), (0.42, 1.4)), seg=8, shift=0.8))
        for d in dr:
            W(key).extend(wash('cheese', d, rng, ((0.95, 0.4),), seg=4, shift=0.3))
        under = band(out, lambda p, n: 3.2 if n[1] > 0.35 else 0.0)
        if under:
            W(key).extend(wash('char', under, rng, ((0.22, 0.6),), seg=8, shift=0.4))
    # pickles: green flesh, dark skin at the rim, a ring of pale seeds
    for pts, (px, py, ang, rx) in pickles:
        W('pickles').extend(wash('pickle', pts, rng, ((0.94, 0.7), (0.45, 1.1)), seg=7, shift=0.7))
    for pts, (px, py, ang, rx) in pickles:
        skin = band(pts, lambda p, n: 3.4)
        if skin:
            W('pickles').extend(wash('patty-edge', skin, rng, ((0.3, 0.4),), seg=7, shift=0.3))
    pickle_seeds = []
    for pts, (px, py, ang, rx) in pickles:
        for j in range(6):
            t = TAU * j / 6 + 0.3
            sp = rot((px + rx * 0.5 * math.cos(t), py + 11.5 * 0.45 * math.sin(t)), ang, (px, py))
            seed = ellipse(sp[0], sp[1], 3.6 * (0.55 + 0.45 * abs(math.sin(t))), 1.5, ang + math.cos(t) * 0.5, 7)
            pickle_seeds.append(seed)
            W('pickles').extend(wash('sesame', seed, rng, ((0.6, 0.25),), seg=3, shift=0.15))
    # sauce
    W('sauce').extend(wash('sauce-burger', sauce, rng, ((0.94, 0.9), (0.42, 1.4)), seg=8, shift=0.8))
    for d in sauce_drop:
        W('sauce').extend(wash('sauce-burger', d, rng, ((0.94, 0.4),), seg=4, shift=0.3))
    # crown: toasted base, lighter body, shadow side, glossy highlight, pale foot
    W('crown').extend(wash('bun-top', crown, rng, ((0.9, 1.8), (0.42, 2.8), (0.24, 3.6)), seg=18))
    body = ellipse(452, 392, 222, 94, -0.12, 40)
    W('crown').extend(wash('bun', body, rng, ((0.52, 5.0), (0.32, 7.0)), seg=16))
    shade = band(crown, lambda p, n: 34 * max(0.0, n[0] * 0.8 + n[1] * 0.25 - 0.12) ** 1.1)
    if shade:
        W('crown').extend(wash('crust-dark', shade, rng, ((0.4, 3.0), (0.22, 4.0)), seg=14))
    foot = band(crown, lambda p, n: 9 if n[1] > 0.55 else 0.0)
    if foot:
        W('crown').extend(wash('sesame', foot, rng, ((0.24, 1.4),), seg=12))
    W('crown').extend(wash('sesame', ellipse(394, 347, 78, 22, -0.3, 30), rng, ((0.16, 2.6), (0.14, 3.4)), seg=10))
    W('crown').extend(wash('sesame', ellipse(383, 343, 36, 6.5, -0.33, 18), rng, ((0.85, 0.8),), seg=6))
    W('crown').extend(wash('sesame', ellipse(452, 325, 9, 3.2, -0.42, 10), rng, ((0.7, 0.4),), seg=4))

    # sesame seeds on the dome
    seeds = []
    tries = 0
    while len(seeds) < 38 and tries < 6000:
        tries += 1
        x = rng.uniform(222, 778)
        y = rng.uniform(296, 470)
        u, v = (x - CX) / 293, (y - 480) / 190
        if u * u + v * v > 0.86 or y > 466:
            continue
        if any(math.dist((x, y), q) < 28 for q, _ in seeds):
            continue
        fz = max(0.25, math.sqrt(max(0.0, 1 - u * u - v * v)))
        a = math.atan2(v, u) + math.pi / 2 + rng.uniform(-0.8, 0.8)
        seeds.append(((x, y), (a, fz)))
    seed_shapes = []
    for (x, y), (a, fz) in seeds:
        pts = []
        for i in range(9):
            t = TAU * i / 9
            pts.append((6.8 * math.cos(t), 3.2 * math.sin(t) * (1 + 0.3 * math.cos(t))))
        # seeds foreshorten towards the silhouette and follow the curve of the dome
        nrm = math.atan2((y - 480) / 190, (x - CX) / 293)
        pts = [rot(p, a - nrm) for p in pts]
        pts = [(p[0] * (0.45 + 0.55 * fz), p[1]) for p in pts]
        pts = [(x + q[0], y + q[1]) for q in (rot(p, nrm) for p in pts)]
        seed_shapes.append(pts)
        W('crown').extend(wash('sesame', pts, rng, ((0.95, 0.3),), seg=4.5, shift=0.3))

    # ---------------- hatching per layer
    def shade_dome(x, y):
        u, v = (x - CX) / 293, (y - 480) / 190
        v = min(v, 0.0)
        z2 = max(0.0, 1 - u * u - v * v)
        n = _norm3(u, v, math.sqrt(z2) + 0.05)
        lam = n[0] * LIGHT[0] + n[1] * LIGHT[1] + n[2] * LIGHT[2]
        s = (1 - lam) / 2
        if y > 462:
            s += (y - 462) / 30 * 0.25
        return s

    near_seed = lambda x, y: any(abs(x - q[0]) < 8 and abs(y - q[1]) < 8 for q, _ in seeds)
    hb_ = crown_poly.bb
    L['crown']['hatch'].hatches(hatch(rng, hb_, lambda x, y, r: (x, y) in crown_poly and
                                      shade_dome(x, y) > 0.45 + 0.07 * nz(x, y) + 0.06 * (r - 0.5) and
                                      not near_seed(x, y), spacing=7.2, minlen=6))
    L['crown']['hatch'].hatches(hatch(rng, hb_, lambda x, y, r: (x, y) in crown_poly and
                                      shade_dome(x, y) > 0.66 + 0.05 * nz(x, y) and not near_seed(x, y),
                                      spacing=7.6, angle=CROSS, minlen=6))

    def shade_heel(x, y):
        u = max(-1.0, min(1.0, (x - CX) / 280))
        t = max(0.0, (y - 652) / 46)
        n = _norm3(u * 1.3, t * 1.4, math.sqrt(max(0.0, 1 - u * u)) * 0.8 + 0.1)
        lam = n[0] * LIGHT[0] + n[1] * LIGHT[1] + n[2] * LIGHT[2]
        return (1 - lam) / 2

    L['heel']['hatch'].hatches(hatch(rng, heel_poly.bb, lambda x, y, r: (x, y) in heel_poly and
                                     shade_heel(x, y) > 0.5 + 0.07 * nz(x, y) + 0.05 * (r - 0.5), spacing=6.8,
                                     minlen=6))
    L['heel']['hatch'].hatches(hatch(rng, heel_poly.bb, lambda x, y, r: (x, y) in heel_poly and
                                     shade_heel(x, y) > 0.7, spacing=7.6, angle=CROSS, minlen=6))

    # the burger's cast shadow on the table (moves with the heel)
    def ground(x, y, r):
        if (x, y) in heel_poly:
            return False
        dx, dy = (x - 548) / 318, (y - 700) / 15
        e = dx * dx + dy * dy
        return e < 0.8 + 0.2 * r and y > 690 and (x > 330 or e < 0.3)

    L['heel']['hatch'].hatches(hatch(rng, (210, 682, 880, 718), ground, spacing=5.2, minlen=4, trim=0.1))
    L['heel']['hatch'].hatches(hatch(rng, (440, 688, 860, 712), lambda x, y, r: ground(x, y, r) and
                                     ((x - 600) / 230) ** 2 + ((y - 698) / 8) ** 2 < 1, spacing=6.2, angle=CROSS,
                                     minlen=4, trim=0.1))

    for key, out, topl, botl in (('patty-top', pt_out, pt_top, pt_bot), ('patty-low', pl_out, pl_top, pl_bot)):
        poly = Poly(out)
        x0 = topl[0][0]
        step = (topl[-1][0] - x0) / (len(topl) - 1)

        def pshade(x, y, topl=topl, botl=botl, x0=x0, step=step):
            i = min(max(int((x - x0) / step), 0), len(topl) - 1)
            t0, t1 = topl[i][1], botl[i][1]
            f = (y - t0) / max(t1 - t0, 1)
            return 0.3 + 0.6 * f + 0.22 * (x - CX) / 312

        L[key]['hatch'].hatches(hatch(rng, poly.bb, lambda x, y, r, poly=poly, pshade=pshade:
                                      (x, y) in poly and pshade(x, y) > 0.56 + 0.08 * nz(x, y) + 0.06 * (r - 0.5),
                                      spacing=6.4, minlen=5))
        L[key]['hatch'].hatches(hatch(rng, poly.bb, lambda x, y, r, poly=poly, pshade=pshade:
                                      (x, y) in poly and pshade(x, y) > 0.86, spacing=7.2, angle=CROSS, minlen=5))
        # crisp, craggy texture across the seared side
        marks = 0
        tries = 0
        while marks < 16 and tries < 400:
            tries += 1
            x = rng.uniform(topl[0][0] + 14, topl[-1][0] - 14)
            i = min(max(int((x - x0) / step), 0), len(topl) - 1)
            y = rng.uniform(topl[i][1] + 3.5, (topl[i][1] + botl[i][1]) / 2 + 2)
            if (x, y) not in poly:
                continue
            cr_ = rng.uniform(2.2, 3.8)
            a0 = rng.uniform(math.pi * 0.9, math.pi * 1.4)
            arc = ellipse(x, y, cr_ * 1.5, cr_, rng.uniform(-0.3, 0.3), 6, a0, a0 + rng.uniform(1.4, 2.2), True)
            L[key]['hatch'].stroke(spline(arc))
            marks += 1

    for key, out in (('cheese-top', ct), ('cheese-low', cl)):
        poly = Poly(out)
        ytop = out[0][1]
        L[key]['hatch'].hatches(hatch(rng, poly.bb, lambda x, y, r, poly=poly, ytop=ytop:
                                      (x, y) in poly and y > ytop + 12 and (x + 6 + 3 * r, y) not in poly,
                                      spacing=5.4, minlen=4))

    for pts, (px, py, ang, rx) in pickles:
        poly = Poly(pts)
        L['pickles']['hatch'].hatches(hatch(rng, poly.bb, lambda x, y, r, poly=poly, px=px, py=py, rx=rx:
                                            (x, y) in poly and (x - px) / rx * 0.55 + (y - py) / 11.5 * 0.8 > 0.4 + 0.2 * r,
                                            spacing=4.6, minlen=3))
    spoly = Poly(sauce)
    L['sauce']['hatch'].hatches(hatch(rng, spoly.bb, lambda x, y, r: (x, y) in spoly and y > 500 and
                                      (x + 5, y) not in spoly, spacing=4.6, minlen=3))

    # ---------------- ink per layer
    ln = lambda k: L[k]['line']
    ln('heel').strokes(ink(heel, True, rng, passes=3, wob=1.0, drift=1.6, part=(0.3, 0.55), seg=14))
    toast = [(x, 609.5 + 1.2 * math.sin(x / 31)) for x in range(236, 766, 8)]
    ln('heel').strokes(ink(toast, False, rng, passes=2, wob=0.6, over=4, part=(0.35, 0.6), seg=18))
    for key, out, holes in (('patty-top', pt_out, pt_holes), ('patty-low', pl_out, pl_holes)):
        ln(key).strokes(ink(out, True, rng, passes=2, wob=0.6, drift=1.0, part=(0.3, 0.5), seg=4.5))
        for h in holes:
            ln(key).strokes(ink(h, True, rng, passes=1, wob=0.1, drift=0.2, over=1, seg=3))
    for key, out, dr in (('cheese-top', ct, ct_drops), ('cheese-low', cl, cl_drops)):
        ln(key).strokes(ink(out, True, rng, passes=2, wob=0.6, drift=1.1, part=(0.3, 0.6), seg=9))
        for d in dr:
            ln(key).strokes(ink(d, True, rng, passes=1, wob=0.15, drift=0.3, over=2, seg=3.5))
    for pts, (px, py, ang, rx) in pickles:
        ln('pickles').strokes(ink(pts, True, rng, passes=2, wob=0.35, drift=0.7, part=(0.35, 0.6), seg=6))
        inner = ellipse(px, py, rx * 0.84, 11.5 * 0.66, ang, 40)
        ln('pickles').strokes(ink(inner, True, rng, passes=1, wob=0.2, drift=0.4, over=-rx * 1.6, seg=8),
                              'art-hatch')
    for seed in pickle_seeds:
        ln('pickles').strokes(ink(seed, True, rng, passes=1, wob=0.05, drift=0.1, over=0.5, seg=2.5), 'art-hatch')
    ln('sauce').strokes(ink(s_bot, False, rng, passes=2, wob=0.6, over=3, part=(0.3, 0.6), seg=8))
    for d in sauce_drop:
        ln('sauce').strokes(ink(d, True, rng, passes=1, wob=0.15, drift=0.3, over=2, seg=3.5))
    ln('crown').strokes(ink(crown, True, rng, passes=3, wob=1.1, drift=1.8, part=(0.3, 0.55), seg=14))
    # the dome meets the foot of the bun
    for side in (-1, 1):
        foot_line = [(CX + side * (285 - 3 * j - 0.18 * j * j), 462 + 0.9 * j - 0.035 * j * j) for j in range(0, 26, 2)]
        ln('crown').strokes(ink(foot_line, False, rng, passes=1, wob=0.4, over=3, seg=10))
    hl_line = ellipse(394, 347, 88, 29, -0.3, 30, math.radians(25), math.radians(150), True)
    ln('crown').strokes(ink(hl_line, False, rng, passes=1, wob=0.3, over=2, seg=10), 'art-hatch')
    for pts in seed_shapes:
        ln('crown').strokes(ink(pts, True, rng, passes=1, wob=0.08, drift=0.2, over=1.2, seg=4.6))

    # ---------------- explode: equal visual gaps between the layers' bodies, crown highest, heel lowest
    ys = lambda pts: (min(p[1] for p in pts), max(p[1] for p in pts))
    boxes = [ys(heel), ys(pl_out), (556.0 - 1, 556.0 + 11), ys(pt_out), (515.0 - 1, 515.0 + 11),
             ys([q for pts, _ in pickles for q in pts]), (482.0, 501.0), ys(crown)]
    heel_drop = 140.0
    crown_target_top = 52.0

    def chain(g):
        e = [heel_drop]
        for i in range(1, len(LAYERS)):
            e.append(boxes[i - 1][0] + e[i - 1] - g - boxes[i][1])
        return e

    e_a, e_b = chain(0.0), chain(1.0)
    g = (crown_target_top - boxes[-1][0] - e_a[-1]) / (e_b[-1] - e_a[-1])
    explode = {k: round(v, 1) for k, v in zip(LAYERS, chain(g))}

    # ---------------- anchors (each on its own layer)
    # on the right side of each layer, so the page's callout leaders run straight out to the label column
    anchors = {'heel': (760, 650), 'patty-low': (785, 578), 'cheese-low': (735, 566), 'patty-top': (790, 538),
               'cheese-top': (730, 530), 'pickles': (680, 508), 'sauce': (722, 521), 'crown': (735, 420)}

    # ---------------- static engineering guides
    dims = Layer('art-dim')
    # centre axis, dash-dot
    pd = PathData()
    y = 26.0
    while y < 972:
        pd.M(CX, y)
        pd.l(CX, min(y + 26, 972))
        y += 33
        if y < 970:
            pd.M(CX, y)
            pd.l(CX, y + 1.6)
        y += 8.6
    dims.stroke(str(pd))
    # ruler on the left, ticks every 10 units, longer every 50 and 100
    RX = 104.0
    dims.strokes(ink([(RX, 60 + i * 44) for i in range(21)], False, rng, passes=1, wob=0.25, over=0, seg=80))
    for rank in (0, 1, 2):
        pd = PathData()
        for k in range(0, 89):
            yv = 940 - k * 10
            r = 2 if k % 10 == 0 else (1 if k % 5 == 0 else 0)
            if r != rank:
                continue
            pd.M(RX, yv)
            pd.l(RX + (6, 12, 20)[r], yv + rng.uniform(-0.2, 0.2))
        dims.stroke(str(pd))
    # width of the heel, under it, with extension lines and arrowheads
    hx0 = min(p[0] for p in heel)
    hx1 = max(p[0] for p in heel)
    DY = 898.0
    for hx in (hx0, hx1):
        dims.strokes(ink([(hx, 712), (hx, 800), (hx, DY + 14)], False, rng, passes=1, wob=0.2, over=0, seg=80))
    dims.strokes(ink([(hx0 + (hx1 - hx0) * k / 10, DY) for k in range(11)], False, rng, passes=1, wob=0.3,
                     over=0, seg=90))
    pd = PathData()
    for hx, sgn in ((hx0, 1), (hx1, -1)):
        pd.M(hx + sgn * 15, DY - 5.5)
        pd.l(hx, DY)
        pd.l(hx + sgn * 15, DY + 5.5)
    dims.stroke(str(pd))

    # ---------------- assemble
    parts = ['<defs>' + wash_filter('bg-wash', 23, scale=5.5, freq=0.03) + '</defs>']
    stats = {}
    for k in LAYERS:
        Lk = L[k]
        a = anchors[k]
        inner = (group('class="art-group art-group--wash" filter="url(#bg-wash)"', Lk['wash'])
                 + group('class="art-group art-group--hatch"', Lk['hatch'].items, Lk['hatch'].n)
                 + group('class="art-group art-group--line"', Lk['line'].items, Lk['line'].n)
                 + f'<circle class="art-dot" r="5" data-note="{k}" cx="{_ft(_t(a[0]))}" cy="{_ft(_t(a[1]))}"/>')
        parts.append(f'<g id="bg-{k}" class="layer" data-layer="{k}" style="--explode:{_ft(_t(explode[k]))}">'
                     + inner + '</g>')
        stats[k] = {'wash': len(Lk['wash']), 'hatch': Lk['hatch'].n, 'line': Lk['line'].n}
    parts.append(group('id="bg-dims" class="art-group art-group--dims"', dims.items, dims.n))
    stats['dims'] = dims.n
    svg = svg_root('0 0 1000 1000', 'codex-art codex-art--burger', ''.join(parts))
    meta = {'viewBox': [0, 0, 1000, 1000], 'anchors': {k: [float(anchors[k][0]), float(anchors[k][1])] for k in LAYERS},
            'explode': explode}
    stats['gap'] = round(g, 1)
    stats['boxes'] = {k: [round(b[0], 1), round(b[1], 1)] for k, b in zip(LAYERS, boxes)}
    return svg, meta, stats


# --------------------------------------------------------------------------- the ribbon

def build_ribbon():
    rng = random.Random(1503)          # the Mona Lisa is begun
    ctrl = [(14, 76), (150, 84), (360, 80), (620, 62), (890, 43), (1186, 25)]
    spine = Curve(smooth_poly(ctrl, False, 40), False)
    SL = spine.L

    def frame(t):
        p = spine.at(t * SL)
        n = spine.normal(t * SL)
        if n[1] < 0:
            n = (-n[0], -n[1])
        return p, n

    items = []
    for name, off, half, ts, te, seed in (('basil', -18.5, 10.0, 0.0, 0.965, 1), ('cream', 0.0, 10.4, 0.018, 1.0, 2),
                                          ('tomato', 18.5, 10.0, 0.04, 0.982, 3)):
        r = random.Random(seed * 101)
        wob = wobble(r, 1.8, (420.0, 150.0, 60.0))

        def width(tt, seed=seed):
            tt = min(max(tt, 0.0), 1.0)
            return (min(1.0, tt / 0.04) ** 0.4 * (1 - tt) ** 0.6 * (1.12 - 0.3 * tt)
                    * (1 + 0.08 * math.sin(tt * 9 + seed)))

        def rib(t0, t1, lat, scale, n=70, ts=ts, te=te, off=off, half=half, wob=wob, width=width):
            top, bot = [], []
            for i in range(n + 1):
                t = t0 + (t1 - t0) * i / n
                tt = (t - ts) / (te - ts)
                (x, y), (nx, ny) = frame(t)
                w = half * width(tt)
                o = off * (1 - 0.15 * t) + wob(x) + lat * w
                top.append((x + nx * (o - w * scale), y + ny * (o - w * scale)))
                bot.append((x + nx * (o + w * scale), y + ny * (o + w * scale)))
            return top + bot[::-1]

        items += wash(name, rib(ts, te, 0, 1), r, ((0.85, 1.0), (0.3, 1.8)), seg=16, shift=0.6)
        # bristle streaks: the brush loads unevenly and runs dry towards the tail
        for b_ in range(5):
            lat = r.uniform(-0.7, 0.7)
            t0 = ts + r.uniform(0.0, 0.25) * (te - ts)
            t1 = te - r.uniform(0.0, 0.3) * (te - ts)
            items += wash(name, rib(t0, t1, lat, r.uniform(0.08, 0.16)), r, ((0.35, 0.3),), seg=16, shift=0.2)
        for b_ in range(4):
            lat = r.uniform(-0.85, 0.85)
            t0 = te - r.uniform(0.07, 0.14) * (te - ts)
            items += wash(name, rib(t0, min(1.0, te + 0.012), lat, r.uniform(0.05, 0.1), 24), r, ((0.6, 0.15),),
                          seg=10, shift=0.1)
    filt = ('<filter id="rb-wash" x="-2%" y="-25%" width="104%" height="150%" color-interpolation-filters="sRGB">'
            '<feTurbulence type="fractalNoise" baseFrequency="0.012 0.09" numOctaves="3" seed="4" result="n"/>'
            '<feDisplacementMap in="SourceGraphic" in2="n" scale="5" xChannelSelector="R" yChannelSelector="G" result="d"/>'
            '<feTurbulence type="fractalNoise" baseFrequency="0.008 0.45" numOctaves="2" seed="9" result="g"/>'
            '<feColorMatrix in="g" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1.2 0 0 0 0.3" result="ga"/>'
            '<feComposite in="d" in2="ga" operator="in"/>'
            '</filter>')
    body = ('<defs>' + filt + '</defs>'
            + group('id="rb-strokes" class="art-group art-group--wash" filter="url(#rb-wash)"', items))
    return svg_root('0 0 1200 120', 'codex-art codex-art--ribbon', body), len(items)


# --------------------------------------------------------------------------- icons

def cubic(p0, p1, p2, p3, n=14):
    out = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        out.append((u ** 3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t ** 3 * p3[0],
                    u ** 3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t ** 3 * p3[1]))
    return out


def path_pts(*segs):
    """Chain of cubic segments: (p0, p1, p2, p3), (p1', p2', p3'), ... or 'L' points."""
    out = []
    cur = None
    for s in segs:
        if len(s) == 4 and not isinstance(s[0], str):
            pts = cubic(*s)
        elif s[0] == 'L':
            pts = [cur, s[1]]
            pts = [(cur[0] + (s[1][0] - cur[0]) * k / 6, cur[1] + (s[1][1] - cur[1]) * k / 6) for k in range(7)]
        else:
            pts = cubic(cur, *s)
        if out:
            pts = pts[1:]
        out += pts
        cur = out[-1]
    return out


def line_pts(p, q, n=8):
    return [(p[0] + (q[0] - p[0]) * k / n, p[1] + (q[1] - p[1]) * k / n) for k in range(n + 1)]


def rrect(x0, y0, x1, y1, r):
    return path_pts(((x0 + r, y0), (x0 + r, y0), (x0 + r, y0), (x0 + r, y0)), ('L', (x1 - r, y0)),
                    ((x1 - r * 0.45, y0), (x1, y0 + r * 0.45), (x1, y0 + r)), ('L', (x1, y1 - r)),
                    ((x1, y1 - r * 0.45), (x1 - r * 0.45, y1), (x1 - r, y1)), ('L', (x0 + r, y1)),
                    ((x0 + r * 0.45, y1), (x0, y1 - r * 0.45), (x0, y1 - r)), ('L', (x0, y0 + r)),
                    ((x0, y0 + r * 0.45), (x0 + r * 0.45, y0), (x0 + r, y0)))


def build_icons():
    rng = random.Random(1490)          # the Vitruvian Man
    icons = {}

    def circ(cx, cy, r, a0=0.0, a1=TAU, n=None):
        n = n or max(10, int(r * 2.2))
        return [(cx + r * math.cos(a0 + (a1 - a0) * i / (n - 1)), cy + r * math.sin(a0 + (a1 - a0) * i / (n - 1)))
                for i in range(n)]

    def ring(cx, cy, r):
        return ('closed', circ(cx, cy, r, 0, TAU * (1 - 1 / 24), 24))

    O = lambda pts: ('open', pts)
    C = lambda pts: ('closed', pts)

    icons['i-pizza'] = [
        O(circ(24, 46, 35, math.radians(236), math.radians(304), 18)),
        O(circ(24, 46, 29.5, math.radians(239), math.radians(301), 16)),
        O(line_pts((24.2, 44.5), (4.6, 17.6))), O(line_pts((24.2, 44.5), (43.4, 17.6))),
        ring(19.5, 25.5, 3.2), ring(28.8, 25.8, 2.7), ring(24, 34.2, 2.3)]
    icons['i-burger'] = [
        C(path_pts(((8, 21), (7.5, 8), (40.5, 8), (40, 21)), ('L', (8, 21)))),
        O(line_pts((18, 15.5), (19.6, 14.6), 2)), O(line_pts((24, 13), (25.6, 12.6), 2)), O(line_pts((30, 15), (31.4, 16), 2)),
        O([(6.5 + i * 0.8, 25.2 + 1.1 * math.sin(i * 0.8 * TAU / 6.5)) for i in range(44)]),
        C(rrect(8, 28.2, 40, 33.6, 2.6)),
        C(path_pts(((8, 37), (8, 37), (8, 37), (8, 37)), ('L', (40, 37)), ((40, 41.5), (38, 42.5), (34, 42.5)),
                   ('L', (14, 42.5)), ((10, 42.5), (8, 41.5), (8, 37))))]
    icons['i-fries'] = [
        C([(12, 22)] + cubic((12, 22), (18, 26.5), (30, 26.5), (36, 22))[1:] + line_pts((36, 22), (32.6, 43))[1:]
          + line_pts((32.6, 43), (15.4, 43))[1:] + line_pts((15.4, 43), (12, 22))[1:-1]),
        O(line_pts((16.4, 24.5), (14, 7.5))), O(line_pts((21.2, 25.4), (20, 5))), O(line_pts((26.6, 25.4), (27.8, 6))),
        O(line_pts((31.6, 24.4), (34.4, 9))), O(line_pts((18.6, 9), (17.6, 20), 4))]
    icons['i-drink'] = [
        O(line_pts((13.2, 16), (16.6, 43))), O(line_pts((16.6, 43), (31.4, 43))), O(line_pts((31.4, 43), (34.8, 16))),
        C(rrect(10.5, 13, 37.5, 17, 1.8)),
        O(cubic((13.5, 13), (15, 8.5), (33, 8.5), (34.5, 13))),
        O(line_pts((25, 10.5), (29, 3.2), 5) + line_pts((29, 3.2), (35.5, 3.2), 5)[1:]),
        O(line_pts((14.6, 27.5), (33.4, 27.5)))]
    icons['i-chili'] = [
        C(path_pts(((31, 14), (37.5, 18.5), (36, 32), (24.5, 39)), ((18, 43), (10, 43.5), (7.5, 41)),
                   ((16, 37.5), (21.5, 30), (23.5, 21)), ((24.6, 16), (27.4, 13.6), (31, 14)))),
        O(cubic((30.6, 13.8), (30.6, 9.5), (32.8, 7), (36.6, 6))),
        O(cubic((26.4, 16.2), (29, 11.8), (33.5, 11.5), (35.6, 14.8))),
        O(cubic((12, 39.2), (18, 37), (23, 31.5), (26.2, 25)))]
    icons['i-leaf'] = [
        C(path_pts(((10, 38), (8, 21), (21, 9.5), (39.5, 8.5)), ((40.5, 26.5), (28, 39.5), (10, 38)))),
        O(cubic((10, 38), (19, 30), (28, 20), (37.5, 10.5))),
        O(line_pts((16, 32.4), (14.4, 24.5), 4)), O(line_pts((22, 26.6), (21.6, 17.4), 4)),
        O(line_pts((28.2, 20.4), (29, 12.8), 4)), O(line_pts((16, 32.4), (22.8, 35.2), 4)),
        O(line_pts((22, 26.6), (30.2, 29.6), 4)), O(line_pts((28.2, 20.4), (35, 22.8), 4)),
        O(line_pts((10.4, 37.6), (5.6, 42.4), 4))]
    icons['i-fire'] = [
        C(path_pts(((24, 43.5), (14, 43.5), (8.8, 36), (10, 28.5)), ((11.2, 21.5), (17.5, 17.5), (18, 9)),
                   ((23.5, 13), (25.5, 18.5), (24.4, 23.6)), ((27.5, 21.5), (29.5, 18.5), (29.4, 14.4)),
                   ((35.5, 19.5), (39.6, 27), (38.6, 32.6)), ((37.4, 39.6), (32, 43.5), (24, 43.5)))),
        C(path_pts(((24, 43.5), (19, 43.5), (16.8, 39.5), (18, 35)), ((19.2, 31), (23, 29.4), (24, 26)),
                   ((27.4, 30), (31.4, 33.2), (30.4, 37.4)), ((29.6, 41.4), (27, 43.5), (24, 43.5))))]
    icons['i-scooter'] = [
        ring(12, 36.5, 5.2), ring(37, 36.5, 5.2),
        O(line_pts((37, 36.5), (32.4, 15))), O(line_pts((28.6, 15.4), (35.8, 13.8), 4)),
        O(cubic((17.6, 34.5), (22, 36.8), (28, 35.6), (33.6, 30.5))),
        O(path_pts(((5.5, 34), (5, 27), (12, 23.8), (20.8, 26.6)), ('L', (21.4, 33.2)))),
        C(rrect(6, 12.5, 19.5, 23.5, 1.4)), O(line_pts((6.6, 16.4), (19, 16.4), 6))]
    icons['i-bag'] = [
        C(line_pts((10, 17), (38, 17))[:-1] + line_pts((38, 17), (36, 43))[:-1] + line_pts((36, 43), (12, 43))[:-1]
          + line_pts((12, 43), (10, 17))[:-1]),
        O(cubic((18, 21.5), (17.4, 8.5), (30.6, 8.5), (30, 21.5))),
        ring(18, 22, 1.1), ring(30, 22, 1.1)]
    icons['i-phone'] = [
        C(path_pts(((14.5, 7.5), (10, 8.5), (7.6, 12), (8.6, 17.5)), ((10.8, 27.5), (20.5, 37.4), (30.6, 39.5)),
                   ((36, 40.5), (39.5, 38.4), (40.4, 34)), ('L', (40.4, 31.2)), ('L', (33.4, 27.6)), ('L', (29.2, 31.6)),
                   ((23.6, 28.8), (19.6, 24.8), (16.8, 19.2)), ('L', (20.6, 15.2)), ('L', (17, 8.2)),
                   ((16.4, 7.6), (15.5, 7.4), (14.5, 7.5))))]
    icons['i-pin'] = [
        C(path_pts(((24, 44), (16, 34.5), (10, 27.5), (10, 19.5)), ((10, 11.5), (16.4, 5), (24, 5)),
                   ((31.6, 5), (38, 11.5), (38, 19.5)), ((38, 27.5), (32, 34.5), (24, 44)))),
        ring(24, 19.4, 5.2)]
    icons['i-clock'] = [
        ring(24, 25, 17.5), O(line_pts((24, 25.6), (24, 13.5), 5)), O(line_pts((24, 25.6), (31.4, 29.6), 5)),
        O(line_pts((24, 9.5), (24, 11.6), 2)), O(line_pts((39.5, 25), (37.4, 25), 2)),
        O(line_pts((24, 40.5), (24, 38.4), 2)), O(line_pts((8.5, 25), (10.6, 25), 2))]
    icons['i-arrow'] = [
        O(cubic((5.5, 25.5), (15, 22.6), (28, 26.2), (40.6, 23.8))),
        O(cubic((30.4, 15.2), (34.4, 19), (37.6, 21.6), (41.2, 23.7))),
        O(cubic((41.2, 23.9), (36.6, 26.6), (33.4, 29.4), (30.4, 33.2)))]
    icons['i-plus'] = [O(line_pts((24.2, 8.5), (23.8, 39.5))), O(line_pts((8.5, 24.2), (39.5, 23.6)))]
    icons['i-close'] = [O(line_pts((11, 11), (37, 37.2))), O(line_pts((37.2, 10.8), (10.8, 37.2)))]
    icons['i-menu'] = [O([(7.5 + i, y + 0.8 * math.sin(i * TAU / 16 + y)) for i in range(34)]) for y in (14, 24, 34)]
    star = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        rr = 18 if k % 2 == 0 else 7.6
        star.append((24 + rr * math.cos(a), 25.5 + rr * math.sin(a)))
    icons['i-star'] = [C([q for a, b in zip(star, star[1:] + star[:1]) for q in line_pts(a, b, 4)[:-1]])]
    icons['i-camera'] = [
        C(path_pts(((9, 15.5), (9, 15.5), (9, 15.5), (9, 15.5)), ('L', (15.6, 15.5)), ('L', (18.6, 10.5)),
                   ('L', (29.4, 10.5)), ('L', (32.4, 15.5)), ('L', (39, 15.5)), ((41, 15.5), (42, 16.5), (42, 18.5)),
                   ('L', (42, 36)), ((42, 38), (41, 39), (39, 39)), ('L', (9, 39)), ((7, 39), (6, 38), (6, 36)),
                   ('L', (6, 18.5)), ((6, 16.5), (7, 15.5), (9, 15.5)))),
        ring(24, 27.2, 7.4), ring(24, 27.2, 3), ring(36.4, 20.4, 1)]
    icons['i-play'] = [ring(24, 24, 18.5),
                       C(line_pts((19.5, 15.5), (33.2, 24), 5)[:-1] + line_pts((33.2, 24), (19.5, 32.5), 5)[:-1]
                         + line_pts((19.5, 32.5), (19.5, 15.5), 5)[:-1])]
    icons['i-mail'] = [C(rrect(6, 12, 42, 36, 2.4)),
                       O(line_pts((6.8, 13.6), (24, 26.4), 6) + line_pts((24, 26.4), (41.2, 13.6), 6)[1:])]
    spk = (line_pts((8, 19), (15, 19), 3)[:-1] + line_pts((15, 19), (24, 11), 4)[:-1] + line_pts((24, 11), (24, 37), 6)[:-1]
           + line_pts((24, 37), (15, 29), 4)[:-1] + line_pts((15, 29), (8, 29), 3)[:-1] + line_pts((8, 29), (8, 19), 4)[:-1])
    icons['i-sound-on'] = [C(spk), O(circ(24.5, 24, 7.5, -0.75, 0.75, 8)), O(circ(24.5, 24, 13.5, -0.8, 0.8, 12))]
    icons['i-sound-off'] = [C(spk), O(line_pts((30.5, 18.5), (41, 29.5), 5)), O(line_pts((41, 18.5), (30.5, 29.5), 5))]

    syms = []
    for name, prims in icons.items():
        pd = PathData()
        for kind, pts in prims:
            closed = kind == 'closed'
            L_ = Curve(pts, closed).L
            runs = ink(pts, closed, rng, passes=1, wob=0.22, drift=0.35, over=min(1.2, L_ * 0.06) if not closed else 1.6,
                       seg=max(1.6, min(4.0, L_ / 10)), step=0.5, minlen=0.5)
            for r in runs:
                catmull(pd, r, False)
        syms.append(f'<symbol id="{name}" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="2" '
                    f'stroke-linecap="round" stroke-linejoin="round"><path d="{pd}"/></symbol>')
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" class="icon-sprite" aria-hidden="true" focusable="false" '
           'width="0" height="0" style="position:absolute;overflow:hidden">' + ''.join(syms) + '</svg>\n')
    return svg, list(icons)


# --------------------------------------------------------------------------- main

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', default=os.path.join(here, '..', 'src', 'art'))
    args = ap.parse_args()
    out = os.path.normpath(args.out)
    os.makedirs(out, exist_ok=True)

    def write(name, text):
        with open(os.path.join(out, name), 'w', encoding='utf-8') as fh:
            fh.write(text)
        return os.path.getsize(os.path.join(out, name))

    report = {}
    svg, meta, stats = build_pizza()
    report['pizza-study.svg'] = write('pizza-study.svg', svg)
    write('pizza-study.json', json.dumps(meta, indent=2) + '\n')
    report['pizza'] = stats
    svg, meta, stats = build_burger()
    report['burger-study.svg'] = write('burger-study.svg', svg)
    write('burger-study.json', json.dumps(meta, indent=2) + '\n')
    report['burger'] = stats
    svg, n = build_ribbon()
    report['ribbon.svg'] = write('ribbon.svg', svg)
    svg, names = build_icons()
    report['icons.svg'] = write('icons.svg', svg)
    report['icons'] = names
    print(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
