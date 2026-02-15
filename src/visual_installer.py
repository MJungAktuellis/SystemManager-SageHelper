from install_handler import verarbeite_installation
import os

def visueller_installationsassistent():
    print("=== Visueller Installationsassistent ===")
    print("Dieser Assistent hilft Ihnen, Module korrekt zu installieren.")

    # Schritt 1: ZIP-Datei angeben
    zip_pfad = input("Bitte geben Sie den Pfad zur ZIP-Datei ein: ").strip()
    if not os.path.exists(zip_pfad):
        print(f"❌ Fehler: Die Datei '{zip_pfad}' wurde nicht gefunden.")
        return

    # Schritt 2: Zielverzeichnis angeben
    ziel_verzeichnis = input("Bitte geben Sie das Zielverzeichnis für die Installation ein: ").strip()
    if not os.path.exists(ziel_verzeichnis):
        try:
            os.makedirs(ziel_verzeichnis)
            print(f"📁 Zielverzeichnis '{ziel_verzeichnis}' wurde erstellt.")
        except Exception as e:
            print(f"❌ Fehler: Das Zielverzeichnis konnte nicht erstellt werden: {e}")
            return

    # Installation starten
    try:
        print("\n🚀 Installation wird gestartet...")
        verarbeite_installation(zip_pfad, ziel_verzeichnis)
        print("\n✅ Installation erfolgreich abgeschlossen.")
    except Exception as e:
        print(f"❌ Ein Fehler ist während der Installation aufgetreten: {e}")

if __name__ == "__main__":
    visueller_installationsassistent()