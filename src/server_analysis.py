import socket
import concurrent.futures
from tkinter import Tk, Label, Button, Entry, Checkbutton, BooleanVar, StringVar, Frame

# Logging Setup
def log(message, level="INFO"):
    with open("server_analysis_log.txt", "a") as log_file:
        log_file.write(f"[{level}] {message}\n")

log("SystemManager-SageHelper gestartet.")

# GUI-Setup
def start_gui():
    app = Tk()
    app.title("Server Doku Helper - Python")

    # Header
    Label(app, text="Server-Rollen Auswahl & Netzwerkscan", font=("Arial", 16)).grid(row=0, columnspan=2, pady=10)

    # Server-Rollen Container
    roles_frame = Frame(app)
    roles_frame.grid(row=1, padx=10, pady=10)

    Label(roles_frame, text="Servername:").grid(row=0, column=0, sticky="w")
    server_name_var = StringVar()
    Entry(roles_frame, textvariable=server_name_var).grid(row=1, column=0)

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

        def is_reachable(ip):
            try:
                socket.create_connection((ip, 135), timeout=0.5)
                return True
            except:
                return False

        subnet = "192.168.1."
        reachable_ips = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            tasks = [executor.submit(is_reachable, f"{subnet}{i}") for i in range(1, 255)]
            reachable_ips = [ip.result() for ip in tasks if ip.result()]

        progress_label["text"] = f"Scan abgeschlossen. Erreichbare Hosts: {len(reachable_ips)}"
        log(f"Hosts gefunden: {reachable_ips}")

    Button(app, text="Netzwerkscan starten", command=scan_network).grid(row=3, pady=10)
    Button(app, text="Beenden", command=app.quit).grid(row=4, pady=10)

    app.mainloop()

# Main
if __name__ == "__main__":
    start_gui()