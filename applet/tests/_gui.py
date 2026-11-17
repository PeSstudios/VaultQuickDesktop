# Společná podmínka pro testy GTK: jen s VQ_GUI_TESTS=1 a dostupným displejem.
import os

GUI_SKIP = "testy GTK jen s VQ_GUI_TESTS=1 (a displejem)"
HAVE_DISPLAY = False
if os.environ.get("VQ_GUI_TESTS") == "1":
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk
        HAVE_DISPLAY = Gdk.Display.get_default() is not None
    except (ImportError, ValueError):
        HAVE_DISPLAY = False
