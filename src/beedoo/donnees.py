"""Protection du dossier `data/` : visages, voix, souvenirs et conversations ne regardent que l'utilisateur.

Sur un ordinateur partagé, un dossier en 755 et des fichiers en 644 sont lisibles par les autres comptes.
On limite donc l'accès (dossiers 700, fichiers 600) au démarrage, pour ce qui existe déjà, et à chaque
écriture, pour ce qui est créé ensuite.
"""

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

DOSSIER = 0o700
FICHIER = 0o600


def proteger(chemin: Path) -> int:
    """Rend `chemin` (fichier ou dossier, récursivement) privé. Renvoie le nombre d'éléments modifiés.

    Les liens symboliques sont ignorés (on ne change jamais les droits de ce vers quoi ils pointent).
    """
    changes = 0

    def appliquer(element: Path, mode: int) -> None:
        nonlocal changes
        try:
            if not element.is_symlink() and (element.stat().st_mode & 0o777) != mode:
                os.chmod(element, mode)
                changes += 1
        except OSError as erreur:
            log.warning("droits de %s non modifiés (%s)", element.name, type(erreur).__name__)

    if not chemin.exists() or chemin.is_symlink():
        return 0
    if chemin.is_file():
        appliquer(chemin, FICHIER)
        return changes
    appliquer(chemin, DOSSIER)
    for racine, dossiers, fichiers in os.walk(chemin, followlinks=False):
        for nom in dossiers:
            appliquer(Path(racine) / nom, DOSSIER)
        for nom in fichiers:
            appliquer(Path(racine) / nom, FICHIER)
    return changes


def proteger_fichier(fichier: Path, jusqu_a: Path) -> None:
    """Après une écriture : le fichier en 600 et ses dossiers, jusqu'à `jusqu_a` inclus, en 700."""
    proteger(fichier)
    dossier = fichier.parent
    while dossier != jusqu_a.parent and dossier != dossier.parent:
        proteger_dossier_seul(dossier)
        if dossier == jusqu_a:
            break
        dossier = dossier.parent


def proteger_dossier_seul(dossier: Path) -> None:
    try:
        if not dossier.is_symlink() and (dossier.stat().st_mode & 0o777) != DOSSIER:
            os.chmod(dossier, DOSSIER)
    except OSError as erreur:
        log.warning("droits de %s non modifiés (%s)", dossier.name, type(erreur).__name__)
