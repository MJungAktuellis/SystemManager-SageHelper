"""Zentrale Logging-Helfer für konsistente Formate, Rotation und Lauf-Kontext.

Dieses Modul stellt projektweit wiederverwendbare Funktionen bereit, damit alle
Einstiegspunkte identische Log-Dateiformate, Dateiendungen und Rotationsregeln
verwenden.
"""

from __future__ import annotations

import contextvars
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from uuid import uuid4

_RUN_ID_CONTEXT: contextvars.ContextVar[str] = contextvars.ContextVar("analyse_lauf_id", default="-")
_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | run_id=%(run_id)s | %(message)s"
_MAX_BYTES = 2 * 1024 * 1024
_BACKUP_COUNT = 5
_LOG_VERZEICHNIS = Path.cwd() / "logs"
_HANDLER_CACHE: dict[str, RotatingFileHandler] = {}


class _RunIdFilter(logging.Filter):
    """Ergänzt jede Logzeile um die aktuelle Lauf-ID aus dem Kontext."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = _RUN_ID_CONTEXT.get()
        return True


def erstelle_lauf_id() -> str:
    """Erzeugt eine robuste Lauf-ID aus Zeitstempel und Kurz-UUID."""
    zeitstempel = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"lauf-{zeitstempel}-{uuid4().hex[:8]}"


def setze_lauf_id(lauf_id: str) -> None:
    """Setzt die Lauf-ID im Kontext, damit sie automatisch in Logs erscheint."""
    _RUN_ID_CONTEXT.set(lauf_id.strip() or "-")


def hole_lauf_id() -> str:
    """Liefert die aktuell aktive Lauf-ID."""
    return _RUN_ID_CONTEXT.get()


def _hole_rotierenden_handler(dateiname: str) -> RotatingFileHandler:
    """Erzeugt je Log-Datei genau einen rotierenden Datei-Handler."""
    if dateiname in _HANDLER_CACHE:
        return _HANDLER_CACHE[dateiname]

    _LOG_VERZEICHNIS.mkdir(parents=True, exist_ok=True)
    log_datei = _LOG_VERZEICHNIS / dateiname
    handler = RotatingFileHandler(log_datei, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8")
    handler.setFormatter(logging.Formatter(_FORMAT))
    handler.addFilter(_RunIdFilter())
    _HANDLER_CACHE[dateiname] = handler
    return handler


def konfiguriere_logger(name: str, *, dateiname: str = "systemmanager.log", level: int = logging.INFO) -> logging.Logger:
    """Konfiguriert einen Logger mit einheitlichem Format und Dateirotation.

    Args:
        name: Technischer Loggername (z. B. Modulpfad).
        dateiname: Ziel-Logdatei (immer mit ``.log``-Endung).
        level: Logging-Level.
    """
    if not dateiname.endswith(".log"):
        raise ValueError("Log-Dateien müssen auf '.log' enden.")

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    handler = _hole_rotierenden_handler(dateiname)
    if handler not in logger.handlers:
        logger.addHandler(handler)

    return logger

