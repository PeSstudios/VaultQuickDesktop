# Práce s pomocníkem ve vlákně, výsledek zpět v hlavním vlákně GTK.
import subprocess
import threading

from gi.repository import GLib

from .client import VqdError


def run_async(fn, on_done):
    """Spustí fn ve vlákně; on_done(result, error) zavolá v hlavním vlákně GTK."""
    def work():
        try:
            res, err = fn(), None
        except VqdError as e:
            res, err = None, e
        except Exception as e:  # neočekávaná chyba = pomocník nefunguje
            res, err = None, VqdError("not_running", str(e))
        GLib.idle_add(lambda: on_done(res, err) and False)
    threading.Thread(target=work, daemon=True).start()


def spawn(argv):
    """Spustí program na pozadí (xdg-open) a nečeká na něj."""
    try:
        p = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
    except OSError:
        return
    threading.Thread(target=p.wait, daemon=True).start()
