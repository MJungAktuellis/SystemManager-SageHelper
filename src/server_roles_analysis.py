import os
import logging
from tkinter import Tk, Label, Button, Listbox

logging.basicConfig(
    filename=os.path.join(os.getcwd(), "logs/server_roles_analysis_log.txt"),
    level=logging.DEBUG,
    format='[%(asctime)s] %(message)s'
)

def find_installation_directory():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def analyze_server_roles(installation_dir):
    logging.info("Starte Serverrollen-Analyse...")

    # Beispielhafte Serverrollenanalyse
    roles = []
    try:
        roles.append("DNS-Server")
        roles.append("DHCP-Server")
        roles.append("Active Directory")

        logging.info(f"Serverrollen gefunden: {', '.join(roles)}")
        return roles
    except Exception as e:
        logging.error(f"Fehler bei der Serverrollen-Analyse: {str(e)}")
        return []


def show_server_roles_gui():
    installation_dir = find_installation_directory()

    roles = analyze_server_roles(installation_dir)

    root = Tk()
    root.title("Server Rollen Übersicht")

    Label(root, text="Gefundene Serverrollen:", font=("Arial", 16)).pack(pady=10)

    roles_listbox = Listbox(root, width=40, height=10)
    roles_listbox.pack(pady=20)

    for role in roles:
        roles_listbox.insert('end', role)

    Button(root, text="Beenden", command=root.destroy, width=20).pack(pady=10)

    root.mainloop()


def main():
    logging.info("Starte Anwendung Serverrollen-Analyse...")
    installation_dir = find_installation_directory()

    if os.path.exists(os.path.join(installation_dir, "install_complete.txt")):
        show_server_roles_gui()
    else:
        logging.error("Installationsdatei nicht gefunden. Serverrollenanalyse nicht möglich.")

if __name__ == "__main__":
    main()