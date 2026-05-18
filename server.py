#!/usr/bin/env python3
"""
EZmodL — Flask backend
Serveur web local pour la gestion de modèles GGUF dans llama-swap.

Lancement :
    python3 server.py [--port 3001] [--host 127.0.0.1]
"""

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from datetime import datetime

# Ajout du dossier lib au path pour import des modules
SCRIPT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(SCRIPT_DIR / "lib"))

try:
    from flask import Flask, jsonify, request, send_from_directory, render_template
except ImportError:
    print("❌ Flask manquant. Install : pip install --user --break-system-packages flask",
          file=sys.stderr)
    sys.exit(1)

# Imports modules locaux
try:
    import hf_api
    import vram_classify
    import disk_search
    import yaml_helper
    import parse_quant
except ImportError as e:
    print(f"❌ Module local manquant : {e}", file=sys.stderr)
    print(f"Vérifie le dossier {SCRIPT_DIR / 'lib'}", file=sys.stderr)
    sys.exit(1)


# ─── Config ───────────────────────────────────────────────
EZMODL_DIR = Path.home() / ".ezmodl"
CONFIG_DIR = EZMODL_DIR / "config"
QUEUE_DIR = EZMODL_DIR / "queue"
LOGS_DIR = EZMODL_DIR / "logs"
MODELS_DIR = Path.home() / "llm-models"

PREFS_FILE = CONFIG_DIR / "preferences.json"
CURATORS_FILE = CONFIG_DIR / "curators.txt"
PENDING_FILE = QUEUE_DIR / "pending.json"
CURRENT_FILE = QUEUE_DIR / "current.json"
HISTORY_FILE = QUEUE_DIR / "history.json"
LOG_FILE = LOGS_DIR / "ezmodl.log"

LLAMA_SWAP_RELOAD_URL = "http://172.17.0.1:9292/v1/models"

# Curators par défaut (liste 2026)
DEFAULT_CURATORS = [
    "bartowski",
    "mradermacher",
    "unsloth",
    "ggml-org",
    "TheDrummer",
    "DavidAU",
    "Qwen",
    "google",
    "microsoft",
    "mistralai",
    "deepseek-ai",
    "meta-llama",
]

DEFAULT_PREFS = {
    "curators_only": True,
    "kv_target_gb": 3.0,
    "search_limit": 20,
    "sort_by": "relevance",
    "theme": "dark-futurist",
}


# ─── Init dossiers et fichiers ───────────────────────────
def init_dirs():
    """Crée les dossiers nécessaires et fichiers par défaut."""
    for d in [EZMODL_DIR, CONFIG_DIR, QUEUE_DIR, LOGS_DIR, MODELS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    if not CURATORS_FILE.exists():
        CURATORS_FILE.write_text("\n".join(DEFAULT_CURATORS) + "\n")

    if not PREFS_FILE.exists():
        PREFS_FILE.write_text(json.dumps(DEFAULT_PREFS, indent=2))

    for f in [PENDING_FILE, CURRENT_FILE, HISTORY_FILE]:
        if not f.exists():
            f.write_text("[]" if f != CURRENT_FILE else "null")


# ─── Logging ──────────────────────────────────────────────
def setup_logging():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout)
        ],
    )
    # Silence Flask werkzeug
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


# ─── Helpers fichiers JSON ────────────────────────────────
def load_json(path, default):
    """Charge un fichier JSON, retourne default si erreur."""
    try:
        if path.exists():
            return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        pass
    return default


def save_json(path, data):
    """Sauvegarde data en JSON dans path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def load_curators():
    """Charge la liste des curators depuis le fichier texte."""
    if not CURATORS_FILE.exists():
        return DEFAULT_CURATORS
    return [line.strip() for line in CURATORS_FILE.read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")]


# ─── Worker downloads ─────────────────────────────────────
worker_lock = threading.Lock()
worker_thread = None
worker_should_stop = False


def add_to_history(entry):
    """Ajoute une entrée à l'historique."""
    history = load_json(HISTORY_FILE, [])
    entry["timestamp"] = datetime.now().isoformat(timespec="seconds")
    history.insert(0, entry)
    # Garde les 100 derniers max
    history = history[:100]
    save_json(HISTORY_FILE, history)


def worker_loop():
    """Boucle worker : pop pending → download → history → reload."""
    global worker_should_stop
    logging.info("Worker downloads démarré")

    while not worker_should_stop:
        try:
            pending = load_json(PENDING_FILE, [])
            current = load_json(CURRENT_FILE, None)

            if current is None and pending:
                # Pop le premier
                item = pending.pop(0)
                save_json(PENDING_FILE, pending)
                item["status"] = "downloading"
                item["started_at"] = datetime.now().isoformat(timespec="seconds")
                item["downloaded_bytes"] = 0
                save_json(CURRENT_FILE, item)

                logging.info(f"Téléchargement : {item['repo']} / {item['filename']}")
                success, err = download_item(item)

                # Récupère taille finale
                target_path = MODELS_DIR / item['filename']
                final_size = target_path.stat().st_size if target_path.exists() else 0

                add_to_history({
                    "repo": item['repo'],
                    "filename": item['filename'],
                    "internal_name": item['internal_name'],
                    "status": "downloaded" if success else "failed",
                    "size_bytes": final_size,
                    "error": err if not success else None,
                })

                # Si succès : ajout au yaml
                if success:
                    yaml_result = yaml_helper.add_model(
                        item['internal_name'],
                        str(target_path),
                        ctx_size=32768
                    )
                    if yaml_result['success']:
                        logging.info(f"Ajouté au yaml : {item['internal_name']}")
                    else:
                        logging.error(f"Erreur yaml : {yaml_result['error']}")

                save_json(CURRENT_FILE, None)

            time.sleep(1)
        except Exception as e:
            logging.error(f"Erreur worker : {e}")
            save_json(CURRENT_FILE, None)
            time.sleep(2)


def download_item(item):
    """
    Télécharge un fichier via curl (écriture directe avec progress).
    Retourne (success: bool, error: str|None).
    """
    repo = item['repo']
    filename = item['filename']
    target_path = MODELS_DIR / filename

    if target_path.exists() and target_path.stat().st_size > 0:
        return True, None

    # Construction URL HF
    url = f"https://huggingface.co/{repo}/resolve/main/{filename}"

    try:
        # curl -L (follow redirects) -C - (resume) -o (output) --fail-with-body
        proc = subprocess.Popen(
            ["curl", "-L", "-C", "-", "--fail-with-body",
             "-o", str(target_path), url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Polling toutes les 0.5s pendant que curl tourne
        while proc.poll() is None:
            time.sleep(0.5)
            if target_path.exists():
                try:
                    size = target_path.stat().st_size
                    current = load_json(CURRENT_FILE, None)
                    if current:
                        current["downloaded_bytes"] = size
                        save_json(CURRENT_FILE, current)
                except OSError:
                    pass

        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            # Nettoie fichier partiel si erreur
            if target_path.exists() and target_path.stat().st_size < (item.get("size_bytes", 0) * 0.99):
                try:
                    target_path.unlink()
                except OSError:
                    pass
            err_msg = stderr.decode("utf-8", errors="ignore")[:500] if stderr else "curl failed"
            return False, err_msg

        # Vérif taille finale
        if item.get("size_bytes", 0) > 0:
            actual = target_path.stat().st_size
            expected = item["size_bytes"]
            if abs(actual - expected) > 1024 * 1024:  # tolérance 1MB
                return False, f"Taille incorrecte : {actual} vs {expected} attendu"

        return True, None

    except FileNotFoundError:
        return False, "curl absent"
    except Exception as e:
        return False, str(e)



def start_worker():
    """Démarre le worker thread (singleton)."""
    global worker_thread, worker_should_stop
    with worker_lock:
        if worker_thread is None or not worker_thread.is_alive():
            worker_should_stop = False
            worker_thread = threading.Thread(target=worker_loop, daemon=True)
            worker_thread.start()


# ─── Flask app ────────────────────────────────────────────
app = Flask(__name__, template_folder=str(SCRIPT_DIR / "templates"),
            static_folder=str(SCRIPT_DIR / "static"))


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/vram")
def api_vram():
    total = vram_classify.detect_vram_total_gb()
    used = vram_classify.detect_vram_used_gb()
    return jsonify({
        "total_gb": total,
        "used_gb": used,
        "free_gb": round(total - used, 2),
        "detected": total > 0,
    })


@app.route("/api/preferences", methods=["GET", "POST"])
def api_preferences():
    if request.method == "GET":
        return jsonify(load_json(PREFS_FILE, DEFAULT_PREFS))
    else:
        data = request.get_json() or {}
        prefs = load_json(PREFS_FILE, DEFAULT_PREFS)
        prefs.update(data)
        save_json(PREFS_FILE, prefs)
        return jsonify({"success": True, "preferences": prefs})


@app.route("/api/curators")
def api_curators():
    return jsonify(load_curators())


@app.route("/api/search")
def api_search():
    query = request.args.get("q", "").strip()
    limit = int(request.args.get("limit", 20))
    sort = request.args.get("sort", "relevance")
    curators_only = request.args.get("curators_only", "false").lower() == "true"

    if not query or len(query) < 2:
        return jsonify({"error": "Query trop courte (min 2 chars)"}), 400

    curators = load_curators() if curators_only else []
    results = hf_api.search_models(
        query=query, limit=limit, sort=sort,
        curators_only=curators_only, curators=curators
    )

    # Si erreur API HF
    if results and isinstance(results[0], dict) and "_error" in results[0]:
        return jsonify({"error": results[0]["_error"]}), 502

    return jsonify({"results": results, "count": len(results)})


@app.route("/api/tree/<path:repo>")
def api_tree(repo):
    """Liste les fichiers GGUF d'un repo."""
    files = hf_api.list_gguf_files(repo)

    if files and isinstance(files[0], dict) and "_error" in files[0]:
        return jsonify({"error": files[0]["_error"]}), 502

    # Enrichir avec quant + classification VRAM
    prefs = load_json(PREFS_FILE, DEFAULT_PREFS)
    vram_total = vram_classify.detect_vram_total_gb() or 16.0
    kv_target = prefs.get("kv_target_gb", 3.0)
    budget = max(vram_total - kv_target, 1.0)

    for f in files:
        f["quant"] = parse_quant.extract_quant(f["path"])
        icon, label = vram_classify.classify_size(f["size_gb"], budget)
        f["status_icon"] = icon
        f["status_label"] = label

    return jsonify({
        "files": files,
        "vram_total": vram_total,
        "kv_target": kv_target,
        "budget_gb": budget,
    })


@app.route("/api/check-existing", methods=["POST"])
def api_check_existing():
    """Cherche si un fichier existe déjà sur disque."""
    data = request.get_json() or {}
    filename = data.get("filename", "")
    if not filename:
        return jsonify({"error": "filename requis"}), 400
    return jsonify(disk_search.find_existing(filename))


@app.route("/api/symlink", methods=["POST"])
def api_symlink():
    data = request.get_json() or {}
    source = data.get("source", "")
    target = data.get("target", "")
    if not source or not target:
        return jsonify({"error": "source et target requis"}), 400

    result = disk_search.create_symlink(source, target)

    # Si succès : ajouter au yaml
    if result["success"]:
        owner = data.get("repo", "").split("/")[0] if "/" in data.get("repo", "") else "local"
        quant = parse_quant.extract_quant(target)
        internal_name = data.get("internal_name") or _make_internal_name(owner, target, quant)
        yaml_result = yaml_helper.add_model(internal_name, result["link_path"])
        result["yaml_added"] = yaml_result["success"]
        result["internal_name"] = internal_name

        if yaml_result["success"]:
            add_to_history({
                "repo": data.get("repo", "local"),
                "filename": target,
                "internal_name": internal_name,
                "status": "symlinked",
                "size_bytes": Path(result["link_path"]).resolve().stat().st_size,
                "error": None,
            })

    return jsonify(result)


def _make_internal_name(owner, filename, quant):
    """Génère nom interne owner-model-quant."""
    model_name = filename.replace(".gguf", "")
    # Strip Q_K suffix from model name
    model_name = model_name.replace(f"-{quant}", "")
    name = f"{owner}-{model_name}-{quant}".lower()
    # Remplacer caractères spéciaux
    import re
    name = re.sub(r"[^a-z0-9-]", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    return name


@app.route("/api/queue", methods=["GET", "POST"])
def api_queue():
    if request.method == "GET":
        return jsonify({
            "pending": load_json(PENDING_FILE, []),
            "current": load_json(CURRENT_FILE, None),
            "history": load_json(HISTORY_FILE, [])[:30],
        })

    else:  # POST : ajouter à la queue
        data = request.get_json() or {}
        repo = data.get("repo", "")
        filename = data.get("filename", "")
        if not repo or not filename:
            return jsonify({"error": "repo et filename requis"}), 400

        quant = parse_quant.extract_quant(filename)
        owner = repo.split("/")[0]
        internal_name = data.get("internal_name") or _make_internal_name(owner, filename, quant)

        # Vérif doublon dans la queue
        pending = load_json(PENDING_FILE, [])
        for p in pending:
            if p["filename"] == filename and p["repo"] == repo:
                return jsonify({"error": "Déjà en queue"}), 409

        item = {
            "id": str(uuid.uuid4()),
            "repo": repo,
            "filename": filename,
            "internal_name": internal_name,
            "quant": quant,
            "size_bytes": int(data.get("size_bytes", 0)),
            "size_bytes": int(data.get("size_bytes", 0)),
            "size_bytes": int(data.get("size_bytes", 0)),
            "queued_at": datetime.now().isoformat(timespec="seconds"),
        }
        pending.append(item)
        save_json(PENDING_FILE, pending)
        start_worker()
        return jsonify({"success": True, "item": item})


@app.route("/api/queue/<item_id>", methods=["DELETE"])
def api_queue_cancel(item_id):
    pending = load_json(PENDING_FILE, [])
    new_pending = [p for p in pending if p["id"] != item_id]
    if len(new_pending) == len(pending):
        return jsonify({"error": "Item absent"}), 404
    save_json(PENDING_FILE, new_pending)
    return jsonify({"success": True})


@app.route("/api/installed")
def api_installed():
    """Liste modèles dans ~/llm-models/."""
    return jsonify(disk_search.list_installed_models())


@app.route("/api/installed/<filename>", methods=["DELETE"])
def api_installed_delete(filename):
    """Supprime un modèle (fichier + entrée yaml)."""
    path = MODELS_DIR / filename
    if not (path.exists() or path.is_symlink()):
        return jsonify({"error": "Fichier inexistant"}), 404

    try:
        is_symlink = path.is_symlink()
        path.unlink()

        # Tentative suppression yaml par nom interne déduit
        # On scanne le yaml pour trouver l'entrée avec --model = <ce path>
        models = yaml_helper.list_models()
        deleted_yaml_entries = []
        for m in models:
            if filename in m.get("model_path", ""):
                result = yaml_helper.remove_model(m["name"])
                if result["success"]:
                    deleted_yaml_entries.append(m["name"])

        return jsonify({
            "success": True,
            "was_symlink": is_symlink,
            "yaml_entries_removed": deleted_yaml_entries,
        })
    except OSError as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/deps-status")
def api_deps_status():
    """Vérifie versions des dépendances Python."""
    deps_to_check = ["huggingface_hub", "flask", "pyyaml", "requests"]
    result = {}
    for dep in deps_to_check:
        try:
            installed = subprocess.run(
                ["pip", "show", dep],
                capture_output=True, text=True, timeout=3
            )
            if installed.returncode == 0:
                for line in installed.stdout.splitlines():
                    if line.startswith("Version:"):
                        result[dep] = {"installed": line.split(":")[1].strip(),
                                       "available": True}
                        break
            else:
                result[dep] = {"installed": None, "available": False}
        except Exception as e:
            result[dep] = {"installed": None, "available": False,
                           "error": str(e)}
    return jsonify(result)


@app.route("/api/llama-swap-reload", methods=["POST"])
def api_llama_swap_reload():
    """Force un reload de llama-swap (utile après ajout)."""
    try:
        import urllib.request
        with urllib.request.urlopen(LLAMA_SWAP_RELOAD_URL, timeout=3) as r:
            data = json.loads(r.read().decode("utf-8"))
            return jsonify({"success": True, "models_count": len(data.get("data", []))})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/favicon.ico")
def favicon():
    """Sert l'icône à la racine pour les bookmarks/onglets."""
    return send_from_directory(str(SCRIPT_DIR / "static"), "icon.png",
                                mimetype="image/png")


@app.route("/api/health")
def api_health():
    """Healthcheck."""
    return jsonify({
        "status": "ok",
        "version": "1.0",
        "timestamp": datetime.now().isoformat(),
    })


# ─── Main ──────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="EZmodL Flask backend")
    parser.add_argument("--port", type=int, default=3001)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    init_dirs()
    setup_logging()
    start_worker()

    logging.info(f"EZmodL démarre sur http://{args.host}:{args.port}")
    logging.info(f"Modèles dir : {MODELS_DIR}")
    logging.info(f"Config dir  : {CONFIG_DIR}")

    # Gestion shutdown propre
    def shutdown(signum, frame):
        global worker_should_stop
        worker_should_stop = True
        logging.info("Shutdown signal reçu, arrêt propre...")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
