import math
import unittest
from curveFit import fit, polynomial, at, compose, maximum


def key(t, v, incoming=0, outgoing=0):
    return {"time": t, "value": v, "in": incoming, "out": outgoing}


def error(source, result):
    worst = 0
    for a, b in zip(result, result[1:]):
        fitted = polynomial(a, b)
        for c, d in zip(source, source[1:]):
            if c["time"] < a["time"] or d["time"] > b["time"]:
                continue
            q = compose(fitted, (c["time"]-a["time"])/(b["time"]-a["time"]),
                        (d["time"]-c["time"])/(b["time"]-a["time"]))
            p = polynomial(c, d)
            worst = max(worst, maximum(tuple(q[i]-p[i] for i in range(4)))[0])
    return worst


class CurveTests(unittest.TestCase):
    def test_cubic_tangents(self):
        source = [key(i/8, (i/8)**3, 3*(i/8)**2, 3*(i/8)**2) for i in range(9)]
        result = fit(source, 1e-10)
        self.assertEqual(len(result), 2)
        self.assertAlmostEqual(result[-1]["in"], 3)
        self.assertLess(error(source, result), 1e-10)

    def test_linear_samples_fitted_to_new_cubic(self):
        source = [key(i/20, (i/20)**3) for i in range(21)]
        for a, b in zip(source, source[1:]):
            a["out"] = b["in"] = (b["value"]-a["value"])/(b["time"]-a["time"])
        result = fit(source, .003)
        self.assertEqual(len(result), 2)
        self.assertLessEqual(error(source, result), .003)

    def test_overshoot_is_not_flat(self):
        source = [key(0, 1, 0, 10), key(.5, 1, -10, 10), key(1, 1, -10, 0)]
        result = fit(source, .001)
        self.assertGreater(len(result), 1)
        self.assertLessEqual(error(source, result), .001)

    def test_constant_and_full_turn(self):
        self.assertEqual(len(fit([key(0, 3), key(20, 3)], .001)), 1)
        result = fit([key(0, 0, 720, 720), key(.5, 360, 720, 720), key(1, 720, 720, 720)], .001)
        self.assertEqual(result[-1]["value"], 720)
        self.assertEqual(len(result), 2)

    def test_fractional_and_reverse(self):
        source = [key(.25, 1, 3, 3), key(.5, 2, 5, -2), key(1.75, 1, -1, 0)]
        result = fit(source, .001)
        self.assertEqual(result[0]["time"], .25)
        self.assertEqual(result[-1]["time"], 1.75)
        reverse = [dict(k, time=2-k["time"], **{"in": -k["out"], "out": -k["in"]})
                   for k in reversed(source)]
        for i in range(2):
            p, q = polynomial(source[i], source[i+1]), polynomial(reverse[1-i], reverse[2-i])
            for j in range(11):
                self.assertAlmostEqual(at(p, j/10), at(q, 1-j/10))

    def test_invalid_data(self):
        for tolerance in (-1, math.nan, math.inf):
            with self.assertRaises(ValueError):
                fit([key(0, 0)], tolerance)
        with self.assertRaises(ValueError):
            fit([key(0, 0), key(0, 1)], .001)
        with self.assertRaises(ValueError):
            fit([key(0, math.nan)], .001)


if __name__ == "__main__":
    unittest.main()
