# EZmodL

> GGUF Model Manager for llama-swap — Browse HuggingFace, download, manage models, all in one place.

<p align="center">
  <img src="icon.png" alt="EZmodL" width="160">
</p>

<p align="center">
  <strong>Web UI lightweight pour gérer ton parc de modèles GGUF locaux.</strong>
</p>

---

## ✨ Features

- 🔍 **Recherche HuggingFace intégrée** avec liste de curators 2026 connus (bartowski, mradermacher, unsloth...)
- 📦 **Browse direct par owner/repo** ou URL HuggingFace
- 🎯 **Classification VRAM dynamique** : 🟢 Idéal / 🟡 Tight / 🔴 Déborde selon ton budget configurable
- 🔗 **Détection symlinks Ollama blobs** : évite les doublons disque (économise des GB)
- ⬇️ **Queue de téléchargement** avec progress bar fluide et historique
- 🔧 **Auto-add au `llama-swap.yaml`** + reload automatique
- 🎨 **UI dark futuriste** (CSS exposé, totalement retouchable)
- 🚀 **Lance dans Firefox WebApp isolé** (pattern OllamaUI)

## 📦 Compatibilité

Testé sur :
- ✅ Ubuntu 24.04 (noble)
- ✅ Linux Mint 22.x (xia / wilma / zara)
- ✅ Debian 13 (trixie) *probable*
- ✅ Pop!_OS 24.04 *probable*

Distros non-apt (Fedora, Arch, openSUSE) : install manuel des deps requis.

## 🚀 Installation rapide

```bash
git clone https://github.com/miradorventus/EZmodL.git
cd EZmodL
EZMODL_LOCAL_INSTALL=1 bash install.sh
```

Ou en ligne unique :

```bash
curl -fsSL https://raw.githubusercontent.com/miradorventus/EZmodL/main/install.sh | bash
```

📌 L'installateur télécharge les fichiers, installe les dépendances système (via pkexec), configure les entrées menu/bureau, et te prévient si quelque chose manque.

## 🔧 Prérequis

EZmodL est conçu pour fonctionner **avec llama-swap**, donc tu as besoin :

- `llama-swap` configuré (`~/.llamaui/config/llama-swap.yaml`)
- `llama.cpp` compilé avec ton backend (Vulkan / CUDA / ROCm)

Pour un setup complet llama.cpp + llama-swap automatisé sur AMD : voir [ollama-amd-plug-and-play](https://github.com/miradorventus/ollama-amd-plug-and-play).

## 🎬 Usage

1. Lance **EZmodL** depuis le menu Applications
2. Cherche un modèle (ex: `Qwen3`) ou colle un repo (`bartowski/Qwen_Qwen3-14B-GGUF`)
3. Configure ta cible VRAM KV cache
4. Coche la/les quants à télécharger
5. EZmodL gère le téléchargement, détecte les doublons, ajoute au yaml, recharge llama-swap

## 🛠️ Configuration

Tous les fichiers de config sont dans `~/.ezmodl/` :

```
~/.ezmodl/
├── config/
│   ├── preferences.json    # Cible VRAM, sort, curators_only, thème
│   └── curators.txt        # Liste éditable des curators
├── queue/                  # File d'attente + historique
└── logs/                   # Journal d'activité
```

**Éditer la liste des curators** (ajouter/retirer) :

```bash
nano ~/.ezmodl/config/curators.txt
```

## 🎨 Personnalisation du thème

Le CSS est exposé dans `~/.ezmodl/static/style.css`. Variables CSS au top du fichier :

```css
:root[data-theme="dark-futurist"] {
  --bg-base: #0a0e1a;
  --text-accent: #00d9ff;
  /* ... */
}
```

Tu peux créer ton propre thème en ajoutant un bloc `:root[data-theme="mon-theme"]`.

## 🗂️ Architecture

| Composant | Rôle |
|---|---|
| `server.py` | Backend Flask, expose une API REST |
| `lib/hf_api.py` | Wrapper HuggingFace API (search + tree) |
| `lib/vram_classify.py` | Détection VRAM AMD/NVIDIA + classification quants |
| `lib/disk_search.py` | Recherche multi-dossiers + création symlinks |
| `lib/yaml_helper.py` | Add/remove modèles dans llama-swap.yaml |
| `lib/parse_quant.py` | Extraction quant depuis nom de fichier |
| `templates/index.html` | UI principale (sections collapsibles) |
| `static/app.js` | Vanilla JS, fetch endpoints REST |
| `ezmodl.sh` | Launcher pattern OllamaUI (lockfile, integrity check) |

## ❌ Désinstallation

```bash
cd EZmodL
bash uninstall.sh
```

Les modèles GGUF dans `~/llm-models/` sont conservés. La config `llama-swap.yaml` n'est pas modifiée (à toi de nettoyer si besoin).

## 📋 Limites V1

- Pas de mass-actions sur modèles installés (à venir)
- Pas de comparaison côte-à-côte de modèles (autre projet)
- Re-classification VRAM basée sur le total détecté (pas sur la VRAM dispo live)
- Édition curators uniquement via fichier texte
- Pas de cache des résultats de recherche HF

## 🤝 Contribuer

Issues et PRs bienvenues. Ce projet est volontairement simple et minimaliste — restons dans cet esprit.

## 📜 License

Apache 2.0 — voir [LICENSE](LICENSE).

## 🙏 Crédits

- [llama.cpp](https://github.com/ggml-org/llama.cpp)
- [llama-swap](https://github.com/mostlygeek/llama-swap)
- Curators GGUF : bartowski, mradermacher, unsloth, ggml-org, et tous les autres
- Built with 🤖 by [miradorventus](https://github.com/miradorventus)

---

**EZmodL** — Because managing GGUFs shouldn't be a chore.
