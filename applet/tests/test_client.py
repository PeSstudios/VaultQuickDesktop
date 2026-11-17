import os, sys, tempfile, textwrap, unittest
import _path  # noqa
from vqapplet.client import Client, VqdError

FAKE = textwrap.dedent('''
    import sys, json, os
    crash = os.environ.get("FAKE_CRASH_FILE")
    seen = os.environ.get("FAKE_SEEN_FILE")
    for line in sys.stdin:
        req = json.loads(line)
        cmd = req["cmd"]
        if seen:
            with open(seen, "a") as f:
                f.write(cmd + "\\n")
        if cmd in ("crash", "create") and crash and not os.path.exists(crash):
            open(crash, "w").close()
            sys.exit(1)
        if cmd == "conflict":
            out = {"id": req["id"], "ok": False, "error": "conflict", "message": "změna"}
        elif cmd == "hang":
            import time; time.sleep(30); continue
        else:
            out = {"id": req["id"], "ok": True, "result": {"echo": req}}
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\\n"); sys.stdout.flush()
''')


class ClientTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.script = os.path.join(self.d.name, "fake.py")
        with open(self.script, "w", encoding="utf-8") as f:
            f.write(FAKE)
        self.clients = []

    def tearDown(self):
        for c in self.clients:
            c.close()
        self.d.cleanup()

    def mk(self, **kw):
        c = Client([sys.executable, self.script], **kw)
        self.clients.append(c)
        return c

    def test_echo_and_ids(self):
        c = self.mk()
        a = c.request("agenda", project="č")
        b = c.request("meta")
        self.assertEqual(a["echo"]["project"], "č")
        self.assertEqual(b["echo"]["cmd"], "meta")
        self.assertNotEqual(a["echo"]["id"], b["echo"]["id"])

    def test_error(self):
        with self.assertRaises(VqdError) as cm:
            self.mk().request("conflict")
        self.assertEqual(cm.exception.code, "conflict")
        self.assertEqual(cm.exception.message, "změna")

    def test_restart_after_crash(self):
        os.environ["FAKE_CRASH_FILE"] = os.path.join(self.d.name, "crashed")
        try:
            c = self.mk()
            self.assertEqual(c.request("crash")["echo"]["cmd"], "crash")
        finally:
            del os.environ["FAKE_CRASH_FILE"]

    def test_create_not_resent_after_crash(self):
        # Pomocník přijal `create` a spadl – mohl úkol zapsat, druhý pokus by ho zdvojil.
        seen = os.path.join(self.d.name, "seen")
        os.environ["FAKE_CRASH_FILE"] = os.path.join(self.d.name, "crashed")
        os.environ["FAKE_SEEN_FILE"] = seen
        try:
            c = self.mk()
            with self.assertRaises(VqdError) as cm:
                c.request("create", text="x")
            self.assertEqual(cm.exception.code, "not_running")
            with open(seen) as f:
                self.assertEqual(f.read().split(), ["create"])
            # další požadavek pomocníka znovu spustí
            self.assertEqual(c.request("meta")["echo"]["cmd"], "meta")
        finally:
            del os.environ["FAKE_CRASH_FILE"]
            del os.environ["FAKE_SEEN_FILE"]

    def test_create_resent_when_write_failed(self):
        # Pomocník spadl dřív, než požadavek odešel (zápis selhal) → bezpečné zopakovat.
        c = self.mk()
        c.request("meta")
        c._proc.kill()
        c._proc.wait()
        c._proc.poll = lambda: None  # klient si pádu nevšimne předem → zápis do mrtvé roury
        self.assertEqual(c.request("create", text="x")["echo"]["cmd"], "create")

    def test_timeout(self):
        with self.assertRaises(VqdError) as cm:
            self.mk(timeout=0.5).request("hang")
        self.assertEqual(cm.exception.code, "timeout")

    def test_missing_binary(self):
        c = Client(["/nonexistent/vqd"])
        with self.assertRaises(VqdError) as cm:
            c.request("meta")
        self.assertEqual(cm.exception.code, "not_running")


if __name__ == "__main__":
    unittest.main()
