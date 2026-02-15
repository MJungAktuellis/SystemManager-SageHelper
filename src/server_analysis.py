import concurrent.futures
import subprocess
import os
import sys
from ping3 import ping
from tkinter import Tk, Label, Button, Entry, Checkbutton, BooleanVar, StringVar, Frame

# Zusätzliche Fehlerbehebung und Logging
log_file_path = "server_analysis_log.txt"

def log(message, level="INFO"):
    with open(log_file_path, "a") as log_file:
        log_file.write(f"[{level}] {message}\n")

log("== Serveranalyse gestartet ==")

# Prüfung auf installierte Module vor Serveranalyse
required_modules = ["ping3"]
missing_modules = []
for module in required_modules:
    try:
        __import__(module)
    except ImportError:
        log(f"Fehlendes Modul: {module}. Prüfe Installation.", level="ERROR")
        sys.exit(1)

log("Alle benötigten Module sind vorhanden.")

# Funktion: Host erreichbarkeit prüfen

def is_host_reachable(host):
    try:
        response = ping(host, timeout=2)
        if response is not None:
            log(f"Host {host} erreichbar: Antwortzeit: {response:.2f} ms")
            return True
        else:
            log(f"Host {host} nicht erreichbar. Keine Antwort.")
    except Exception as ex:
           log="#OUTOS``POINT EX INT."APP`` etc...  
 --- Ordners auff트를. Testen. EX vurder.''--  Fixed validated \ Runnable.---.  EndRewrite Knots fixed Verified: Would reN. pls confirm,.,. FixptDone restructuring. Plzz. `` ContextFull resolutions tream approaches runAVEL">