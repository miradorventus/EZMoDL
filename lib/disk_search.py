#!/usr/bin/env python3
"""
disk_search.py — Recherche fichier GGUF existant dans plusieurs dossiers,
                  et création de symlink vers ~/llm-models/ si trouvé ailleurs.

Usage CLI :
    # Cherche un fichier dans les 4 dossiers
    python3 disk_search.py find <filename.gguf>

    # Crée un symlink dans ~/llm-models/
    python3 disk_search.py symlink <source_path> <filename.gguf>

Usage module :
    from disk_search import find_existing, create_symlink
"""

import os
import sys
import json
import subprocess
from pathlib import Path


# Dossiers de recherche (ordre de priorité : 1er trouvé gagne)
SEARCH_DIRS = [
    Path.home() / "llm-models",
    Path("/usr/share/ollama/.ollama/models/blobs"),
    Path.home() / ".cache" / "huggingface",
    Path.home() / ".cache" / "llama.cpp",
]

DEST_DIR = Path.home() / "llm-models"


def find_existing(filename: str) -> dict:
    """
    Cherche un fichier par nom EXACT dans tous les dossiers prioritaires.

    :param filename: nom du fichier à chercher (sans path)
    :return: dict {found: bool, path: str ou None, source_dir: str ou None,
                   is_blob: bool}
    """
    for search_dir in SEARCH_DIRS:
        if not search_dir.exists() or not search_dir.is_dir():
            continue

        # Recherche directe (fichier au top du dossier)
        direct = search_dir / filename
        if direct.is_file() or direct.is_symlink():
            return {
                "found": True,
                "path": str(direct.resolve()),
                "source_dir": str(search_dir),
                "is_blob": False,
            }

        # Recherche récursive (utile pour HF cache, ollama blobs)
        try:
            for f in search_dir.rglob(filename):
                if f.is_file() and not f.is_symlink():
                    return {
                        "found": True,
                        "path": str(f.resolve()),
                        "source_dir": str(search_dir),
                        "is_blob": "blobs" in str(f),
                    }
        except (PermissionError, OSError):
            continue

    return {"found": False, "path": None, "source_dir": None, "is_blob": False}


def find_by_size(size_bytes: int, tolerance_bytes: int = 0) -> dict:
    """
    Cherche un fichier .gguf par taille exacte dans tous les dossiers
    (utile pour matcher les blobs Ollama qui ont des noms sha256-XXX).

    :param size_bytes: taille à matcher
    :param tolerance_bytes: tolérance (défaut 0 = match exact)
    :return: dict {found: bool, path: str ou None, source_dir: str ou None}
    """
    for search_dir in SEARCH_DIRS:
        if not search_dir.exists():
            continue
        try:
            for f in search_dir.rglob("*"):
                if not f.is_file():
                    continue
                try:
                    fsize = f.stat().st_size
                except OSError:
                    continue
                if abs(fsize - size_bytes) <= tolerance_bytes:
                    # Match : vérifions si c'est probablement un GGUF
                    if f.name.endswith(".gguf") or "blobs" in str(f):
                        return {
                            "found": True,
                            "path": str(f.resolve()),
                            "source_dir": str(search_dir),
                            "is_blob": "blobs" in str(f),
                        }
        except (PermissionError, OSError):
            continue

    return {"found": False, "path": None, "source_dir": None, "is_blob": False}


def create_symlink(source_path: str, target_filename: str) -> dict:
    """
    Crée un symlink dans ~/llm-models/ pointant vers source_path.

    :param source_path: chemin absolu vers le fichier existant
    :param target_filename: nom du symlink dans ~/llm-models/
    :return: dict {success: bool, link_path: str, error: str ou None}
    """
    source = Path(source_path)
    if not source.exists():
        return {"success": False, "link_path": "",
                "error": f"Source inexistante : {source_path}"}

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    link_path = DEST_DIR / target_filename

    if link_path.exists() or link_path.is_symlink():
        return {"success": False, "link_path": str(link_path),
                "error": f"Le lien existe déjà : {link_path}"}

    try:
        link_path.symlink_to(source.resolve())
        return {"success": True, "link_path": str(link_path), "error": None}
    except OSError as e:
        return {"success": False, "link_path": str(link_path),
                "error": str(e)}


def list_installed_models() -> list:
    """
    Liste tous les modèles présents dans ~/llm-models/ avec leur statut.

    :return: liste de dicts {name, path, size_gb, is_symlink, target}
    """
    if not DEST_DIR.exists():
        return []

    models = []
    for f in sorted(DEST_DIR.iterdir()):
        if not (f.is_file() or f.is_symlink()):
            continue
        if not f.name.endswith(".gguf"):
            continue

        is_symlink = f.is_symlink()
        try:
            real_path = f.resolve()
            size_bytes = real_path.stat().st_size
        except OSError:
            size_bytes = 0
            real_path = f

        models.append({
            "name": f.name,
            "path": str(f),
            "real_path": str(real_path),
            "size_gb": round(size_bytes / 1024**3, 2),
            "is_symlink": is_symlink,
        })

    return models


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: disk_search.py find <filename> | symlink <src> <name> | list",
              file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "find":
        if len(sys.argv) < 3:
            print("Usage: find <filename>", file=sys.stderr)
            sys.exit(1)
        result = find_existing(sys.argv[2])
        print(json.dumps(result, indent=2))

    elif cmd == "find-size":
        if len(sys.argv) < 3:
            print("Usage: find-size <bytes>", file=sys.stderr)
            sys.exit(1)
        result = find_by_size(int(sys.argv[2]))
        print(json.dumps(result, indent=2))

    elif cmd == "symlink":
        if len(sys.argv) < 4:
            print("Usage: symlink <source_path> <target_filename>", file=sys.stderr)
            sys.exit(1)
        result = create_symlink(sys.argv[2], sys.argv[3])
        print(json.dumps(result, indent=2))

    elif cmd == "list":
        models = list_installed_models()
        print(json.dumps(models, indent=2))

    else:
        print(f"Commande inconnue : {cmd}", file=sys.stderr)
        sys.exit(1)
