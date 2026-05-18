#!/usr/bin/env python3
"""
vram_classify.py — Détection VRAM dGPU + classification des quants selon budget.

Usage CLI :
    # Détecter VRAM totale
    python3 vram_classify.py detect

    # Classifier une taille en GB selon budget
    python3 vram_classify.py classify <size_gb> <budget_gb>

Usage module :
    from vram_classify import detect_vram_total_gb, classify_size

    total = detect_vram_total_gb()        # Ex: 16.0
    status = classify_size(12.1, 13.0)    # Ex: ("🟢", "Confortable")
"""

import subprocess
import sys
import re


# Seuils de classification (% du budget poids modèle)
THRESHOLD_IDEAL = 0.80      # <= 80% : idéal
THRESHOLD_CONFORT = 0.90    # 80-90% : confortable
THRESHOLD_TIGHT = 1.00      # 90-100% : tight
# > 100% : déborde


def detect_vram_total_gb() -> float:
    """
    Détecte la VRAM totale du dGPU (GPU[0]) en GB via rocm-smi.

    :return: VRAM totale en GB (float), 0.0 si non détectable
    """
    try:
        result = subprocess.run(
            ["rocm-smi", "--showmeminfo", "vram"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return 0.0

        # Cherche la ligne "GPU[0] : VRAM Total Memory (B): <bytes>"
        for line in result.stdout.splitlines():
            if "GPU[0]" in line and "Total Memory" in line and "Used" not in line:
                match = re.search(r"(\d+)\s*$", line.strip())
                if match:
                    bytes_total = int(match.group(1))
                    return round(bytes_total / 1024**3, 2)
        return 0.0
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return 0.0


def detect_vram_used_gb() -> float:
    """
    Détecte la VRAM actuellement utilisée du dGPU (GPU[0]) en GB.

    :return: VRAM utilisée en GB, 0.0 si non détectable
    """
    try:
        result = subprocess.run(
            ["rocm-smi", "--showmeminfo", "vram"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return 0.0

        for line in result.stdout.splitlines():
            if "GPU[0]" in line and "Total Used Memory" in line:
                match = re.search(r"(\d+)\s*$", line.strip())
                if match:
                    return round(int(match.group(1)) / 1024**3, 2)
        return 0.0
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return 0.0


def classify_size(size_gb: float, budget_gb: float) -> tuple:
    """
    Classifie une taille de modèle par rapport au budget poids.

    :param size_gb: taille du fichier en GB
    :param budget_gb: budget poids modèle (VRAM totale - KV cible)
    :return: tuple (icône, label)
    """
    if budget_gb <= 0:
        return ("❓", "Budget invalide")

    ratio = size_gb / budget_gb

    if ratio <= THRESHOLD_IDEAL:
        return ("🟢", "Idéal")
    elif ratio <= THRESHOLD_CONFORT:
        return ("🟢", "Confortable")
    elif ratio <= THRESHOLD_TIGHT:
        return ("🟡", "Tight")
    else:
        return ("🔴", "Déborde")


def bytes_to_gb(byte_size: int) -> float:
    """Convertit bytes en GB (binaire)."""
    return round(byte_size / 1024**3, 2)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: vram_classify.py detect | classify <size_gb> <budget_gb>",
              file=sys.stderr)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "detect":
        total = detect_vram_total_gb()
        used = detect_vram_used_gb()
        print(f"total={total}")
        print(f"used={used}")
        print(f"free={round(total - used, 2)}")

    elif cmd == "classify":
        if len(sys.argv) < 4:
            print("Usage: classify <size_gb> <budget_gb>", file=sys.stderr)
            sys.exit(1)
        size = float(sys.argv[2])
        budget = float(sys.argv[3])
        icon, label = classify_size(size, budget)
        print(f"{icon} {label}")

    else:
        print(f"Commande inconnue : {cmd}", file=sys.stderr)
        sys.exit(1)
