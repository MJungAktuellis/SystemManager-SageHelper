import concurrent.futures
import subprocess
import os
from ping3 import ping, PingError
from tkinter import Tk, Label, Button, Entry, Checkbutton, BooleanVar, StringVar, Frame

# Logging Setup
def log(message, level="INFO"):
    with open("server_analysis_log.txt", "a") as log_file:
        log_file.write(f"[{level}] {message}\n")

log("SystemManager-SageHelper gestartet.")

# Funktion für Netzwerkscan mit `ping3`
def is_host_reachable(host):
    try:
        response = ping(host, timeout=1)
        return response is not None
    except PingError as e:
        log(f"Ping-Fehler bei {host}: {str(e)}", level="ERROR")
        return False

# Rollenprüfungs-Funktionen

def check_sql_roles(server):
    log(f"Überprüfe SQL-Rollen auf {server}...")
    try:
        result = subprocess.run(
            ["sc", f"\\\\{server}", "query", "type= service", "state= all"],
            capture_output=True,
            text=True,
        )
        sql_instances = [line for line in result.stdout.split("\n") if "MSSQL" in line]
        log(f"Gefundene SQL Services auf {server}: {', '.join(sql_instances)}")
    except Exception as e:
        log(f"Fehler bei SQL-Prüfung auf {server}: {str(e)}", level="ERROR")

def check_app_roles(server):
    log(f"Überprüfe APP-Rollen auf {server}...")
    paths = [
        "C:\\Program Files\\Sage",
        "C:\\Program Files (x86)\\Sage",
        "C:\\Sage"
    ]
    found_paths = []
    for path in paths:
        if os.path.exists(path):
            found_paths.append(path)
    if found_paths:
        log(f"Gefundene Applikationspfade auf {server}: {', '.join(found_paths)}")
    else:
        log(f"Keine Applikationspfade gefunden auf {server}")

def check_ctx_roles(server):
    log(f"Überprüfe CTX-Rollen auf {server}...")
    try:
        result = subprocess.run(
            ["quser.exe"],
            capture_output=True,
            text=True,
        )
        active_sessions = result.stdout.split("\n")
        log(f"Gefundene aktive Sessions auf {server}: {len(active_sessions) - 1}")
    except Exception as e:
        log(f"Fehler bei CTX-Prüfung auf {server}: {str(e)}", level="ERROR")

# GUI-Setup
def start_gui():
    app = Tk()
    app.title("Server Doku Helper - Python")

    # Header
    Label(app, text="Server-Rollen Auswahl & erweiterter Netzwerkscan", font=("Arial", 16)).grid(row=0, columnspan=2, pady=10)

    # Server-Rollen Container
    roles_frame = Frame(app)
    roles_frame.grid(row=1, padx=10, pady=10)

    Label(roles_frame, text="Bitte Servernamen/Subnetz eingeben:").grid(row=0, column=0, sticky="w")
    subnet_var = StringVar(value="192.168.1.")
    Entry(roles_frame, textvariable=subnet_var).grid(row=1, column=0)

    sql_var = BooleanVar()
    app_var = BooleanVar()
    ctx_var = BooleanVar()

    Checkbutton(roles_frame, text="SQL", variable=sql_var).grid(row=1, column=1)
    Checkbutton(roles_frame, text="APP", variable=app_var).grid(row=1, column=2)
    Checkbutton(roles_frame, text="CTX", variable=ctx_var).grid(row=1, column=3)

    # Progress label
    progress_label = Label(app, text="Bereit", fg="green")
    progress_label.grid(row=2, pady=10)

    def scan_network():
        progress_label["text"] = "Scanning... Bitte Warten."
        subnet = subnet_var.get().strip()
        reachable_hosts = []

        # Automatischer Netzwerkscan
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            tasks = [executor.submit(is_host_reachable, f"{subnet}{i}") for i in range(1, 255)]
            for i, task in enumerate(tasks, 1):
                if task.result():
                    reachable_hosts.append(f"{subnet}{i}")

        progress_label["text"] = f"Scan abgeschlossen. {len(reachable_hosts)} Hosts erreichbar."
        log(f"Gefundene Hosts: {reachable_hosts}")

        # Rollenprüfungen
        for server in reachable_hosts:
            if sql_var.get():
                check_sql_roles(server)
            if app_var.get():
                check_app_roles(server)
            if ctx_var.get():
                check_ctx_roles(server)

    Button(app, text="Netzwerkscan starten", command=scan_network).grid(row=3, pady=10)
    Button(app, text="Beenden", command=app.quit).grid(row=4, pady=10)

    app.mainloop()

# Main
if __name__ == "__main__":
    start_gui()