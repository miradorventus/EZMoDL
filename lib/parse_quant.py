#!/usr/bin/env python3
"""
parse_quant.py — Extrait le type de quantization depuis un nom de fichier GGUF.

Usage CLI :
    python3 parse_quant.py <filename.gguf>

Usage module :
    from parse_quant import extract_quant
    quant = extract_quant("Qwen_Qwen3-14B-Q6_K.gguf")  # => "Q6_K"
"""

import re
import sys

# Ordre important : les patterns plus spécifiques en premier
QUANT_PATTERNS = [
    # IQ-quants imatrix (variantes étendues)
    r"IQ[0-9]+_X{0,2}[SMLN]?",
    r"IQ[0-9]+_NL",
    # K-quants standards (Q4_K_M, Q4_K_S, Q4_K_L, Q4_K_XL)
    r"Q[0-9]+_K_X?[SMLN]",
    r"Q[0-9]+_K",
    # Legacy quants (Q4_0, Q4_1, Q5_0, Q5_1, Q8_0)
    r"Q[0-9]+_[0-9]+",
    # Quants Q_K nu (sans suffixe)
    r"Q[0-9]+",
    # Half/single precision
    r"BF16",
    r"F16",
    r"F32",
]


def extract_quant(filename: str) -> str:
    """
    Extrait le type de quant depuis un nom de fichier GGUF.

    :param filename: nom du fichier (avec ou sans path/extension)
    :return: type de quant trouvé, ou "unknown" si non détecté
    """
    # Strip path et extension
    name = filename.rsplit("/", 1)[-1]
    name = name.replace(".gguf", "")

    # Cherche le pattern qui match (insensitive)
    for pattern in QUANT_PATTERNS:
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            return match.group(0).upper()

    return "unknown"


def normalize_quant_for_name(quant: str) -> str:
    """
    Normalise une quant pour usage dans un nom interne (lowercase, tiret).
    Ex: "Q6_K" -> "q6-k", "IQ4_XS" -> "iq4-xs"
    """
    return quant.lower().replace("_", "-")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: parse_quant.py <filename.gguf>", file=sys.stderr)
        sys.exit(1)

    filename = sys.argv[1]
    quant = extract_quant(filename)
    print(quant)
