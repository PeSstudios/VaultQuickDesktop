# Klient pomocníka vqd (JSON po řádcích přes stdin/stdout), bezpečný pro vlákna.
import json
import queue
import subprocess
import threading


class VqdError(Exception):
    def __init__(self, code, message=""):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class _Dead(Exception):
    def __init__(self, sent=False):
        super().__init__()
        self.sent = sent  # požadavek už odešel – pomocník ho mohl zpracovat


# Příkazy, které se po pádu pomocníka nesmí poslat znovu, pokud už požadavek odešel
# (druhý `create` by zapsal úkol podruhé).
_NO_RESEND = {"create"}


class Client:
    def __init__(self, argv, timeout=15.0):
        self.argv = list(argv)
        self.timeout = timeout
        self._lock = threading.Lock()
        self._next_id = 0
        self._proc = None
        self._lines = None

    def _start(self):
        try:
            self._proc = subprocess.Popen(
                self.argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                encoding="utf-8", bufsize=1)
        except OSError as e:
            self._proc = None
            raise VqdError("not_running", str(e))
        q = queue.Queue()
        self._lines = q
        out = self._proc.stdout

        def pump():
            for line in out:
                q.put(line)
            q.put(None)  # konec proudu = proces skončil
        threading.Thread(target=pump, daemon=True).start()

    def _kill(self):
        p, self._proc = self._proc, None
        if p:
            try:
                p.kill()
                p.wait(timeout=2)
                p.stdin.close()
                p.stdout.close()
            except Exception:
                pass

    def close(self):
        with self._lock:
            self._kill()

    def _roundtrip(self, req):
        if self._proc is None or self._proc.poll() is not None:
            self._kill()
            self._start()
        try:
            self._proc.stdin.write(json.dumps(req, ensure_ascii=False) + "\n")
            self._proc.stdin.flush()
        except (OSError, ValueError):
            raise _Dead()
        while True:
            try:
                line = self._lines.get(timeout=self.timeout)
            except queue.Empty:
                self._kill()
                raise VqdError("timeout", "pomocník neodpověděl včas")
            if line is None:
                raise _Dead(sent=True)
            try:
                resp = json.loads(line)
            except ValueError:
                continue
            if resp.get("id") == req["id"]:
                return resp
            # cizí (opožděná) odpověď – zahodit

    def request(self, cmd, **params):
        with self._lock:
            self._next_id += 1
            req = {"id": self._next_id, "cmd": cmd, **params}
            try:
                resp = self._roundtrip(req)
            except _Dead as dead:
                # proces spadl: jeden restart a zopakování (u `create` jen, když požadavek neodešel)
                self._kill()
                if dead.sent and cmd in _NO_RESEND:
                    raise VqdError("not_running", "pomocník spadl – úkol se možná zapsal")
                try:
                    resp = self._roundtrip(req)
                except _Dead:
                    self._kill()
                    raise VqdError("not_running", "pomocník spadl")
        if resp.get("ok"):
            return resp.get("result") or {}
        raise VqdError(resp.get("error", "failed"), resp.get("message", ""))
