#!/usr/bin/env python3
"""
hf_api.py — Wrapper API HuggingFace (recherche modèles + listing fichiers).

Usage CLI :
    # Recherche modèles
    python3 hf_api.py search <query> [--limit N] [--sort relevance|likes|date|downloads]

    # Liste fichiers GGUF d'un repo
    python3 hf_api.py tree <owner>/<repo>

Usage module :
    from hf_api import search_models, list_gguf_files
"""

import json
import sys
import urllib.request
import urllib.parse
import urllib.error


HF_API_BASE = "https://huggingface.co/api"
TIMEOUT = 10


def _http_get_json(url: str) -> dict | list | None:
    """GET JSON depuis HF avec timeout court."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EZmodL/1.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"_error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"_error": f"URL error: {e.reason}"}
    except (TimeoutError, json.JSONDecodeError) as e:
        return {"_error": f"Error: {e}"}


def search_models(query: str, limit: int = 20, sort: str = "relevance",
                  curators_only: bool = False, curators: list = None) -> list:
    """
    Recherche des modèles sur HuggingFace.

    :param query: terme de recherche
    :param limit: nombre max de résultats (default 20)
    :param sort: relevance | likes | downloads | trending | createdAt
    :param curators_only: si True, filtre par auteurs ∈ curators
    :param curators: liste d'auteurs autorisés
    :return: liste de dicts {id, author, likes, downloads, createdAt}
    """
    # Mapping sort UI → API HF
    sort_map = {
        "relevance": None,        # Default HF (pertinence)
        "likes": "likes",
        "downloads": "downloads",
        "date": "createdAt",
        "trending": "trendingScore",
    }
    sort_param = sort_map.get(sort)

    params = {
        "search": query,
        "limit": limit * 3 if curators_only else limit,
        # Sur-fetch si filtrage curators, pour avoir assez après filtre
        "filter": "gguf",
    }
    if sort_param:
        params["sort"] = sort_param
        params["direction"] = "-1"  # desc

    url = f"{HF_API_BASE}/models?" + urllib.parse.urlencode(params)
    data = _http_get_json(url)

    if isinstance(data, dict) and "_error" in data:
        return [{"_error": data["_error"]}]

    if not isinstance(data, list):
        return [{"_error": "Réponse API inattendue"}]

    results = []
    for m in data:
        if not isinstance(m, dict):
            continue
        model_id = m.get("id", "")
        if "/" not in model_id:
            continue

        author, model_name = model_id.split("/", 1)

        # Filtre curators
        if curators_only and curators:
            if author not in curators:
                continue

        results.append({
            "id": model_id,
            "author": author,
            "model": model_name,
            "likes": m.get("likes", 0),
            "downloads": m.get("downloads", 0),
            "created": m.get("createdAt", "")[:10],  # YYYY-MM-DD
            "trending": m.get("trendingScore", 0),
        })

        if len(results) >= limit:
            break

    return results


def list_gguf_files(repo: str) -> list:
    """
    Liste les fichiers .gguf d'un repo HF avec leurs tailles.

    :param repo: format "owner/repo"
    :return: liste de dicts {path, size_bytes, size_gb}
    """
    url = f"{HF_API_BASE}/models/{repo}/tree/main"
    data = _http_get_json(url)

    if isinstance(data, dict):
        if "_error" in data:
            return [{"_error": data["_error"]}]
        if "error" in data:
            # L'API HF retourne {"error": "..."} pour repos inexistants
            return [{"_error": f"Repo inexistant ou privé : {data['error']}"}]

    if not isinstance(data, list):
        return [{"_error": "Réponse API inattendue"}]

    files = []
    for item in data:
        if not isinstance(item, dict):
            continue
        path = item.get("path", "")
        if not path.endswith(".gguf"):
            continue

        # Taille : lfs.size en priorité (pour les fichiers LFS), sinon size
        lfs = item.get("lfs", {})
        size_bytes = lfs.get("size", item.get("size", 0))

        files.append({
            "path": path,
            "size_bytes": size_bytes,
            "size_gb": round(size_bytes / 1024**3, 2),
        })

    return files


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: hf_api.py search <query> | tree <repo>", file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "search":
        if len(sys.argv) < 3:
            print("Usage: search <query> [--limit N] [--sort X]", file=sys.stderr)
            sys.exit(1)
        query = sys.argv[2]
        limit = 20
        sort = "relevance"
        curators_only = False
        curators = []

        i = 3
        while i < len(sys.argv):
            if sys.argv[i] == "--limit" and i + 1 < len(sys.argv):
                limit = int(sys.argv[i + 1])
                i += 2
            elif sys.argv[i] == "--sort" and i + 1 < len(sys.argv):
                sort = sys.argv[i + 1]
                i += 2
            elif sys.argv[i] == "--curators-only":
                curators_only = True
                i += 1
            elif sys.argv[i] == "--curators" and i + 1 < len(sys.argv):
                curators = sys.argv[i + 1].split(",")
                i += 2
            else:
                i += 1

        results = search_models(query, limit=limit, sort=sort,
                                curators_only=curators_only,
                                curators=curators)
        print(json.dumps(results, indent=2, ensure_ascii=False))

    elif cmd == "tree":
        if len(sys.argv) < 3:
            print("Usage: tree <owner>/<repo>", file=sys.stderr)
            sys.exit(1)
        repo = sys.argv[2]
        files = list_gguf_files(repo)
        print(json.dumps(files, indent=2, ensure_ascii=False))

    else:
        print(f"Commande inconnue : {cmd}", file=sys.stderr)
        sys.exit(1)
