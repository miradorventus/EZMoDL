#!/usr/bin/env python3
"""
yaml_helper.py — Helper pour modifier llama-swap.yaml de manière sécurisée.

Usage CLI :
    # Ajouter un modèle
    python3 yaml_helper.py add <internal_name> <model_path>

    # Supprimer un modèle
    python3 yaml_helper.py remove <internal_name>

    # Lister les modèles
    python3 yaml_helper.py list

Usage module :
    from yaml_helper import add_model, remove_model
"""

import sys
import os
import shutil
import json
from pathlib import Path
from datetime import datetime

try:
    import yaml
except ImportError:
    print("❌ PyYAML manquant. Install : pip install --user --break-system-packages pyyaml",
          file=sys.stderr)
    sys.exit(1)


YAML_PATH = Path.home() / ".llamaui" / "config" / "llama-swap.yaml"
BACKUP_DIR = YAML_PATH.parent


def _backup_yaml() -> str:
    """Crée un backup horodaté du yaml. Retourne le chemin du backup."""
    if not YAML_PATH.exists():
        return ""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = BACKUP_DIR / f"{YAML_PATH.name}.bak-{ts}"
    shutil.copy2(YAML_PATH, backup)
    return str(backup)


def _load_yaml() -> dict:
    """Charge le YAML, retourne {} si inexistant ou invalide."""
    if not YAML_PATH.exists():
        return {}
    with open(YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def _save_yaml(data: dict) -> None:
    """Sauvegarde le YAML avec formatage cohérent."""
    YAML_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(YAML_PATH, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False,
                  allow_unicode=True)


def add_model(internal_name: str, model_path: str,
              ctx_size: int = 32768, ttl: int = 600,
              add_to_group: str = "main") -> dict:
    """
    Ajoute un modèle au llama-swap.yaml.

    :param internal_name: nom interne (clé du dict 'models')
    :param model_path: chemin absolu vers le fichier GGUF
    :param ctx_size: taille contexte (défaut 32K)
    :param ttl: time-to-live en secondes (défaut 600 = 10 min)
    :param add_to_group: groupe où ajouter, "" pour aucun
    :return: dict {success, backup_path, error}
    """
    if not Path(model_path).exists():
        return {"success": False, "backup_path": "",
                "error": f"Fichier inexistant : {model_path}"}

    if not YAML_PATH.exists():
        return {"success": False, "backup_path": "",
                "error": f"Config llama-swap absente : {YAML_PATH}"}

    try:
        backup = _backup_yaml()
        data = _load_yaml()

        # Construire la commande llama-server
        new_cmd = (
            "/home/ia/llama.cpp/build/bin/llama-server\n"
            "--host 127.0.0.1\n"
            "--port ${PORT}\n"
            "--device Vulkan0\n"
            "-ngl 99\n"
            "--no-warmup\n"
            "--jinja\n"
            "--metrics\n"
            f"--model {model_path}\n"
            f"--ctx-size {ctx_size}\n"
        )

        if "models" not in data:
            data["models"] = {}
        data["models"][internal_name] = {
            "cmd": new_cmd,
            "ttl": ttl,
        }

        # Ajouter au groupe si spécifié
        if add_to_group and "groups" in data:
            if add_to_group in data["groups"]:
                members = data["groups"][add_to_group].get("members", [])
                if internal_name not in members:
                    members.append(internal_name)
                    data["groups"][add_to_group]["members"] = members

        _save_yaml(data)
        return {"success": True, "backup_path": backup, "error": None}

    except Exception as e:
        return {"success": False, "backup_path": "", "error": str(e)}


def remove_model(internal_name: str) -> dict:
    """
    Supprime un modèle du llama-swap.yaml et de tous les groupes.

    :return: dict {success, backup_path, error, was_present}
    """
    if not YAML_PATH.exists():
        return {"success": False, "backup_path": "", "was_present": False,
                "error": f"Config llama-swap absente : {YAML_PATH}"}

    try:
        backup = _backup_yaml()
        data = _load_yaml()
        was_present = False

        if "models" in data and internal_name in data["models"]:
            del data["models"][internal_name]
            was_present = True

        # Retirer de tous les groupes
        if "groups" in data:
            for group_name, group_data in data["groups"].items():
                members = group_data.get("members", [])
                if internal_name in members:
                    members.remove(internal_name)
                    data["groups"][group_name]["members"] = members

        if was_present:
            _save_yaml(data)
            return {"success": True, "backup_path": backup,
                    "was_present": True, "error": None}
        else:
            return {"success": False, "backup_path": backup,
                    "was_present": False,
                    "error": f"Modèle '{internal_name}' absent du yaml"}

    except Exception as e:
        return {"success": False, "backup_path": "", "was_present": False,
                "error": str(e)}


def list_models() -> list:
    """Liste tous les modèles déclarés dans le yaml."""
    if not YAML_PATH.exists():
        return []
    data = _load_yaml()
    models = data.get("models", {})
    result = []
    for name, conf in models.items():
        cmd = conf.get("cmd", "")
        # Extraire le chemin du --model
        path = ""
        for line in cmd.split("\n"):
            line = line.strip()
            if line.startswith("--model "):
                path = line.split(" ", 1)[1].strip()
                break
        result.append({
            "name": name,
            "model_path": path,
            "ttl": conf.get("ttl", 0),
        })
    return result


def model_exists(internal_name: str) -> bool:
    """Vérifie si un modèle est déjà déclaré."""
    if not YAML_PATH.exists():
        return False
    data = _load_yaml()
    return internal_name in data.get("models", {})


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: yaml_helper.py add <name> <path> | remove <name> | list | exists <name>",
              file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "add":
        if len(sys.argv) < 4:
            print("Usage: add <name> <path>", file=sys.stderr)
            sys.exit(1)
        result = add_model(sys.argv[2], sys.argv[3])
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["success"] else 1)

    elif cmd == "remove":
        if len(sys.argv) < 3:
            print("Usage: remove <name>", file=sys.stderr)
            sys.exit(1)
        result = remove_model(sys.argv[2])
        print(json.dumps(result, indent=2))
        sys.exit(0 if result["success"] else 1)

    elif cmd == "list":
        print(json.dumps(list_models(), indent=2, ensure_ascii=False))

    elif cmd == "exists":
        if len(sys.argv) < 3:
            print("Usage: exists <name>", file=sys.stderr)
            sys.exit(1)
        print("yes" if model_exists(sys.argv[2]) else "no")

    else:
        print(f"Commande inconnue : {cmd}", file=sys.stderr)
        sys.exit(1)
