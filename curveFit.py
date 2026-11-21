"""Error-bounded cubic fitting, independent of the FBX SDK and UI."""
import math


def polynomial(a, b):
    h = b["time"] - a["time"]
    d = b["value"] - a["value"]
    m0, m1 = a["out"] * h, b["in"] * h
    return (a["value"], m0, 3*d - 2*m0 - m1, -2*d + m0 + m1)


def at(p, x):
    return ((p[3]*x + p[2])*x + p[1])*x + p[0]


def compose(p, u, v):
    return (at(p, u), v*(p[1]+2*p[2]*u+3*p[3]*u*u),
            v*v*(p[2]+3*p[3]*u), p[3]*v*v*v)


def maximum(p):
    candidates = [0.0, 1.0]
    a, b, c = 3*p[3], 2*p[2], p[1]
    if abs(a) < 1e-24:
        if abs(b) >= 1e-24:
            candidates.append(-c/b)
    else:
        disc = b*b - 4*a*c
        if disc >= 0:
            root = math.sqrt(disc)
            candidates.extend(((-b-root)/(2*a), (-b+root)/(2*a)))
    return max((abs(at(p, t)), t) for t in candidates if 0 <= t <= 1)


def fit(keys, tolerance):
    """Return new keys/slopes; bound deviation over the complete input graph."""
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("Curve tolerance must be finite and nonnegative.")
    for i, key in enumerate(keys):
        if not all(math.isfinite(key[k]) for k in ("time", "value", "in", "out")):
            raise ValueError("Curve contains non-finite data.")
        if i and key["time"] <= keys[i-1]["time"]:
            raise ValueError("Curve times must increase.")
    if len(keys) < 2:
        return [dict(k) for k in keys]
    base = keys[0]["value"]
    if all(maximum((p[0]-base, p[1], p[2], p[3]))[0] <= tolerance
           for p in (polynomial(a, b) for a, b in zip(keys, keys[1:]))):
        return [dict(keys[0], **{"in": 0.0, "out": 0.0})]
    if len(keys) == 2:
        return [dict(k) for k in keys]

    source = [polynomial(a, b) for a, b in zip(keys, keys[1:])]

    def integral(a, b):
        return sum(a[i]*b[j]/(i+j+1) for i in range(4) for j in range(4))

    def span(left, right):
        if right == left+1:
            return (left, right, keys[left]["out"], keys[right]["in"], 0, left)
        t0 = keys[left]["time"]
        h = keys[right]["time"]-t0
        d = keys[right]["value"]-keys[left]["value"]
        fixed = (keys[left]["value"], 0, 3*d, -2*d)
        ay = by = 0.0
        # Integrals of the two Hermite tangent basis products on [0, 1].
        aa, ab, bb = 1/105, -1/140, 1/105
        for i in range(left, right):
            u = (keys[i]["time"]-t0)/h
            v = (keys[i+1]["time"]-keys[i]["time"])/h
            a = compose((0, 1, -2, 1), u, v)
            b = compose((0, 0, -1, 1), u, v)
            f = compose(fixed, u, v)
            target = tuple(source[i][j]-f[j] for j in range(4))
            ay += v*integral(a, target)
            by += v*integral(b, target)
        det = aa*bb-ab*ab
        m0, m1 = (ay*bb-by*ab)/det, (by*aa-ay*ab)/det
        p = (fixed[0], m0, 3*d-2*m0-m1, -2*d+m0+m1)
        error, worst_time = 0.0, (t0+keys[right]["time"])/2
        for i in range(left, right):
            u = (keys[i]["time"]-t0)/h
            v = (keys[i+1]["time"]-keys[i]["time"])/h
            q = compose(p, u, v)
            e, t = maximum(tuple(q[j]-source[i][j] for j in range(4)))
            if e > error:
                error = e
                worst_time = keys[i]["time"]+t*(keys[i+1]["time"]-keys[i]["time"])
        split = min(range(left+1, right), key=lambda i: abs(keys[i]["time"]-worst_time))
        return (left, right, m0/h, m1/h, error, split)

    pending, spans = [(0, len(keys)-1)], []
    while pending:
        left, right = pending.pop()
        result = span(left, right)
        if result[4] <= tolerance or right == left+1:
            spans.append(result)
        else:
            split = result[5]
            pending.extend(((split, right), (left, split)))
    i = 0
    while i < len(spans)-1:
        merged = span(spans[i][0], spans[i+1][1])
        if merged[4] <= tolerance:
            spans[i:i+2] = [merged]
            i = max(0, i-1)
        else:
            i += 1
    result = [dict(keys[0])]
    for left, right, out_slope, in_slope, _, _ in spans:
        result[-1]["out"] = out_slope
        result.append(dict(keys[right], **{"in": in_slope}))
    return result
