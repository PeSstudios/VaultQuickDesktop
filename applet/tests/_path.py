# Přidá desktop/applet do sys.path, aby šel balíček vqapplet importovat.
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
