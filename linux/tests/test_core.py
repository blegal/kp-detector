import datetime as dt
import unittest

from kp_detector import core
from kp_detector.config import Config
from kp_detector.i18n import T

UTC = dt.timezone.utc


def sample(h, kp, pred=False, day=11):
    return core.Sample(dt.datetime(2026, 10, day, h, tzinfo=UTC), kp, pred)


class CoreTests(unittest.TestCase):
    def test_parse_kp(self):
        rows = [{"time_tag": "2026-10-10T15:00:00", "kp": 7.0, "observed": "observed"},
                {"time_tag": "2026-10-12T00:00:00", "kp": "3.33", "observed": "predicted"},
                {"bad": 1}]
        s = core.parse_kp(rows)
        self.assertEqual(len(s), 2)
        self.assertFalse(s[0].predicted)
        self.assertTrue(s[1].predicted)
        self.assertEqual(s[1].kp, 3.33)
        with self.assertRaises(ValueError):
            core.parse_kp([])

    def test_geomagnetic_latitude_paris(self):
        # même valeur que l'app macOS (Swift)
        self.assertAlmostEqual(core.geomagnetic_latitude(48.85, 2.35), 50.4, delta=0.1)
        self.assertAlmostEqual(core.kp_needed_for_aurora(50.4), 7.3, delta=0.05)

    def test_kp_needed_never_negative(self):
        self.assertEqual(core.kp_needed_for_aurora(80), 0)

    def test_find_aurora(self):
        data = b'{"coordinates": [[0, -90, 4], [2, 49, 17], [2, 50, 3], [359, 49, 8]]}'
        self.assertEqual(core.find_aurora(data, 49.2, 2.1), 17)
        self.assertEqual(core.find_aurora(data, 49.0, -1.0), 8)   # lon -1 → 359
        self.assertEqual(core.find_aurora(data, -90, 0), 4)
        self.assertIsNone(core.find_aurora(data, 10, 10))

    def test_levels(self):
        self.assertEqual([core.level(k) for k in (3, 4.67, 5.33, 6.67, 9)], [0, 1, 1, 3, 3])
        self.assertEqual(core.label_key(7.0), "G3 · strong")

    def test_current_and_peak(self):
        s = [sample(0, 2), sample(3, 3), sample(6, 5, True), sample(9, 6.3, True), sample(12, 4, True, day=14)]
        now = dt.datetime(2026, 10, 11, 4, tzinfo=UTC)
        self.assertEqual(core.current(s).kp, 3)
        self.assertEqual(core.peak_next_24h(s, now).kp, 6.3)

    def test_hot_slots(self):
        s = [sample(0, 7.0), sample(3, 6.0), sample(6, 6.5, True), sample(9, 8.0, True)]
        now = dt.datetime(2026, 10, 11, 4, tzinfo=UTC)
        hot = core.hot_slots(s, 6, set(), now)
        self.assertEqual([x.kp for x in hot], [6.5, 8.0])        # > 6 strict, créneau 0h terminé
        done = {core.slot_key(s[3])}
        self.assertEqual([x.kp for x in core.hot_slots(s, 6, done, now)], [6.5])

    def test_daily_max(self):
        s = [sample(0, 2), sample(9, 4, True), sample(0, 5, True, day=12)]
        d = core.daily_max(s, dt.date(2026, 10, 11))
        self.assertTrue(all(x[0] >= dt.date(2026, 10, 11) for x in d))
        self.assertEqual(max(kp for _, kp, _ in d), 5)

    def test_recipients(self):
        self.assertEqual(core.recipients("a@x.org, B@x.org;a@X.org  +33600000000\nc"),
                         ["a@x.org", "B@x.org", "+33600000000", "c"])
        self.assertEqual(core.recipients(""), [])

    def test_i18n(self):
        import os
        os.environ["LANGUAGE"] = "fr"
        self.assertEqual(T("Calm"), "Calme")
        self.assertEqual(T("Geomagnetic storm: Kp %.1f", 7.0), "Orage géomagnétique : Kp 7.0")
        os.environ["LANGUAGE"] = "en"
        self.assertEqual(T("Calm"), "Calm")
        self.assertEqual(T("Unknown key"), "Unknown key")

    def test_config_roundtrip(self):
        import os, stat, tempfile
        p = os.path.join(tempfile.mkdtemp(), "c", "config.json")
        c = Config(p)
        self.assertEqual(c["alert_threshold"], 6)
        c.update(alert_threshold=7, email_to="a@b.c", bogus=1)
        c.save()
        c2 = Config(p)
        self.assertEqual(c2["alert_threshold"], 7)
        self.assertNotIn("bogus", c2.data)
        self.assertEqual(stat.S_IMODE(os.stat(p).st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
