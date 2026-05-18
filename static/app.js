/* ═══════════════════════════════════════════════════════
   EZmodL — Frontend JS (vanilla)
   ═══════════════════════════════════════════════════════ */

const API = "/api";
const REFRESH_INTERVAL = 1000;  // 1s

// ─── État global ──────────────────────────────────────
const state = {
  vram: { total_gb: 0, used_gb: 0, free_gb: 0 },
  prefs: {},
  currentRepo: null,
  currentFiles: [],
  selectedQuants: new Set(),
};

// ─── Helpers ──────────────────────────────────────────
async function api(path, options = {}) {
  const opts = {
    headers: { "Content-Type": "application/json" },
    ...options,
  };
  if (opts.body && typeof opts.body !== "string") {
    opts.body = JSON.stringify(opts.body);
  }
  const r = await fetch(API + path, opts);
  if (!r.ok) {
    const err = await r.json().catch(() => ({ error: r.statusText }));
    throw new Error(err.error || `HTTP ${r.status}`);
  }
  return r.json();
}

function toast(message, type = "info", duration = 4000) {
  const container = document.getElementById("toast-container");
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => {
    el.style.animation = "slide-in 0.25s ease-in reverse";
    setTimeout(() => el.remove(), 250);
  }, duration);
}

function formatGB(gb) {
  return gb.toFixed(2) + " GB";
}

function formatBytes(bytes) {
  if (!bytes) return "0 B";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 ** 2) return (bytes / 1024).toFixed(1) + " KB";
  if (bytes < 1024 ** 3) return (bytes / 1024 ** 2).toFixed(1) + " MB";
  return (bytes / 1024 ** 3).toFixed(2) + " GB";
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

// ─── Theme ───────────────────────────────────────────
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("ezmodl-theme", theme);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute("data-theme");
  const next = current === "dark-futurist" ? "light" : "dark-futurist";
  applyTheme(next);
}

// ─── VRAM ─────────────────────────────────────────────
async function loadVRAM() {
  try {
    state.vram = await api("/vram");
    renderVRAM();
  } catch (e) {
    console.error("VRAM load:", e);
  }
}

function renderVRAM() {
  const { total_gb, used_gb, free_gb } = state.vram;
  document.getElementById("vram-total").textContent = formatGB(total_gb);
  document.getElementById("vram-used").textContent = formatGB(used_gb);
  document.getElementById("vram-free").textContent = formatGB(free_gb);

  const pct = total_gb > 0 ? (used_gb / total_gb) * 100 : 0;
  document.getElementById("vram-bar").style.width = pct + "%";

  updateBudget();
}

function updateBudget() {
  const kvTarget = parseFloat(document.getElementById("kv-target").value) || 0;
  const budget = Math.max(state.vram.total_gb - kvTarget, 1);
  document.getElementById("budget-gb").textContent = budget.toFixed(2);
}

// ─── Preferences ──────────────────────────────────────
async function loadPrefs() {
  try {
    state.prefs = await api("/preferences");
    document.getElementById("kv-target").value = state.prefs.kv_target_gb || 3.0;
    document.getElementById("curators-only").checked = state.prefs.curators_only !== false;
    document.getElementById("sort-by").value = state.prefs.sort_by || "relevance";
    document.getElementById("search-limit").value = state.prefs.search_limit || 20;
    if (state.prefs.theme) applyTheme(state.prefs.theme);
    updateBudget();
  } catch (e) {
    console.error("Prefs load:", e);
  }
}

async function maybeSavePrefs() {
  if (!document.getElementById("save-prefs").checked) return;
  const prefs = {
    curators_only: document.getElementById("curators-only").checked,
    kv_target_gb: parseFloat(document.getElementById("kv-target").value),
    sort_by: document.getElementById("sort-by").value,
    search_limit: parseInt(document.getElementById("search-limit").value),
    theme: document.documentElement.getAttribute("data-theme"),
  };
  try {
    await api("/preferences", { method: "POST", body: prefs });
    toast("Préférences sauvegardées", "success", 2000);
  } catch (e) {
    toast("Erreur sauvegarde : " + e.message, "error");
  }
}

// ─── Search ───────────────────────────────────────────
async function doSearch() {
  const q = document.getElementById("search-input").value.trim();
  if (q.length < 2) {
    toast("Query trop courte (min 2 caractères)", "warning");
    return;
  }
  const params = new URLSearchParams({
    q,
    sort: document.getElementById("sort-by").value,
    limit: document.getElementById("search-limit").value,
    curators_only: document.getElementById("curators-only").checked,
  });

  const resultsEl = document.getElementById("search-results");
  resultsEl.innerHTML = '<p class="hint-empty">Recherche en cours...</p>';

  try {
    const data = await api("/search?" + params.toString());
    renderResults(data.results);
    if (data.results.length === 0) {
      resultsEl.innerHTML = '<p class="hint-empty">Aucun résultat</p>';
    }
  } catch (e) {
    resultsEl.innerHTML = `<p class="hint-empty">❌ ${escapeHtml(e.message)}</p>`;
  }
}

function renderResults(results) {
  const el = document.getElementById("search-results");
  el.innerHTML = results.map(r => `
    <div class="result-item" data-repo="${escapeHtml(r.id)}">
      <div class="result-info">
        <div class="result-title">${escapeHtml(r.model)}</div>
        <div class="result-author">${escapeHtml(r.author)}</div>
        <div class="result-meta">
          <span>★ ${r.likes}</span>
          <span>⬇️ ${r.downloads.toLocaleString()}</span>
          <span>📅 ${r.created || "?"}</span>
          ${r.trending ? `<span>🔥 ${r.trending}</span>` : ''}
        </div>
      </div>
      <div class="result-action">→</div>
    </div>
  `).join("");
  el.querySelectorAll(".result-item").forEach(item => {
    item.addEventListener("click", () => loadQuants(item.dataset.repo));
  });
}

// ─── Direct repo / URL ────────────────────────────────
function parseDirectInput(input) {
  input = input.trim();
  input = input.replace(/^https?:\/\/huggingface\.co\//, "");
  input = input.replace(/\/$/, "");
  input = input.replace(/\/tree\/main$/, "");
  let quant = null;
  if (input.includes(":")) {
    [input, quant] = input.split(":");
  }
  if (!input.includes("/")) return null;
  return { repo: input, quant };
}

async function doDirectLoad() {
  const raw = document.getElementById("direct-input").value;
  const parsed = parseDirectInput(raw);
  if (!parsed) {
    toast("Format invalide. Attendu : owner/repo[:QUANT]", "warning");
    return;
  }
  await loadQuants(parsed.repo, parsed.quant);
}

// ─── Quants list ──────────────────────────────────────
async function loadQuants(repo, autoSelectQuant = null) {
  state.currentRepo = repo;
  state.selectedQuants.clear();
  const section = document.getElementById("section-quants");
  section.classList.remove("hidden");
  section.scrollIntoView({ behavior: "smooth", block: "center" });
  document.getElementById("quants-repo").textContent = repo;
  document.getElementById("quants-list").innerHTML = '<p class="hint-empty">Chargement...</p>';

  try {
    // Re-saisir kv-target pour budget à jour côté serveur
    await api("/preferences", {
      method: "POST",
      body: { kv_target_gb: parseFloat(document.getElementById("kv-target").value) }
    });

    const data = await api(`/tree/${repo}`);
    state.currentFiles = data.files;
    document.getElementById("quants-budget").textContent = data.budget_gb.toFixed(2);
    renderQuants(data.files);

    if (autoSelectQuant) {
      // Sélection auto par nom de quant (case-insensitive)
      const match = data.files.find(f =>
        f.quant.toLowerCase() === autoSelectQuant.toLowerCase() ||
        f.path.toLowerCase().includes(autoSelectQuant.toLowerCase())
      );
      if (match) {
        const cb = document.querySelector(`input[data-path="${match.path}"]`);
        if (cb) {
          cb.checked = true;
          state.selectedQuants.add(match.path);
          updateQueueButton();
        }
      }
    }
  } catch (e) {
    document.getElementById("quants-list").innerHTML =
      `<p class="hint-empty">❌ ${escapeHtml(e.message)}</p>`;
  }
}

function classifyClass(label) {
  return ({
    "Idéal": "quant-ideal",
    "Confortable": "quant-confort",
    "Tight": "quant-tight",
    "Déborde": "quant-deborde",
  })[label] || "";
}

function renderQuants(files) {
  const el = document.getElementById("quants-list");
  if (!files.length) {
    el.innerHTML = '<p class="hint-empty">Aucun .gguf dans ce repo</p>';
    return;
  }
  el.innerHTML = files.map(f => `
    <div class="quant-row ${classifyClass(f.status_label)}" data-path="${escapeHtml(f.path)}">
      <input type="checkbox" data-path="${escapeHtml(f.path)}" class="quant-cb">
      <span class="quant-name">${escapeHtml(f.quant)}</span>
      <span class="quant-filename mono" title="${escapeHtml(f.path)}">${escapeHtml(f.path)}</span>
      <span class="quant-size">${f.size_gb.toFixed(2)} GB</span>
      <span class="quant-status">${f.status_icon} ${escapeHtml(f.status_label)}</span>
    </div>
  `).join("");

  el.querySelectorAll(".quant-cb").forEach(cb => {
    cb.addEventListener("change", e => {
      const path = e.target.dataset.path;
      const file = state.currentFiles.find(f => f.path === path);
      if (e.target.checked) {
        if (file && file.status_label === "Déborde") {
          if (!confirm(`⚠️ ${file.quant} (${file.size_gb.toFixed(2)} GB) dépasse ta VRAM.\n\nTélécharger quand même ?`)) {
            e.target.checked = false;
            return;
          }
        }
        state.selectedQuants.add(path);
      } else {
        state.selectedQuants.delete(path);
      }
      updateQueueButton();
    });
  });
}

function updateQueueButton() {
  const btn = document.getElementById("btn-queue-selected");
  btn.disabled = state.selectedQuants.size === 0;
  btn.textContent = state.selectedQuants.size > 0
    ? `⬇️ Ajouter ${state.selectedQuants.size} à la queue`
    : "⬇️ Ajouter à la queue";
}

// ─── Add to queue (avec check existant) ──────────────
async function addSelectedToQueue() {
  for (const path of state.selectedQuants) {
    await addOneToQueue(state.currentRepo, path);
  }
  state.selectedQuants.clear();
  document.querySelectorAll(".quant-cb:checked").forEach(cb => cb.checked = false);
  updateQueueButton();
  await maybeSavePrefs();
}

async function addOneToQueue(repo, filename) {
  try {
    // Check si déjà présent
    const existing = await api("/check-existing", {
      method: "POST",
      body: { filename }
    });

    if (existing.found) {
      // Si dans ~/llm-models/ direct, on skip
      if (existing.source_dir.includes("/llm-models")) {
        toast(`${filename} déjà dans ~/llm-models/`, "info");
        return;
      }
      // Sinon, demande symlink
      const useSymlink = await askSymlink(filename, existing.path);
      if (useSymlink === "symlink") {
        await api("/symlink", {
          method: "POST",
          body: { source: existing.path, target: filename, repo }
        });
        toast(`🔗 Symlink créé pour ${filename}`, "success");
        await refreshInstalled();
        return;
      } else if (useSymlink === "cancel") {
        return;
      }
      // sinon redownload : fall through
    }

    const file = state.currentFiles.find(f => f.path === filename);
    await api("/queue", {
      method: "POST",
      body: { repo, filename, size_bytes: file ? file.size_bytes : 0 }
    });
    toast(`Ajouté à la queue : ${filename}`, "success");
  } catch (e) {
    toast(`Erreur : ${e.message}`, "error");
  }
}

function askSymlink(filename, foundAt) {
  return new Promise(resolve => {
    const modal = document.getElementById("modal-symlink");
    document.getElementById("modal-symlink-text").innerHTML =
      `<strong>${escapeHtml(filename)}</strong> existe déjà :<br>` +
      `<code>${escapeHtml(foundAt)}</code><br><br>` +
      `Utiliser l'existant via symlink (économise l'espace) ?`;
    modal.classList.remove("hidden");

    const cleanup = (result) => {
      modal.classList.add("hidden");
      document.getElementById("modal-symlink-yes").onclick = null;
      document.getElementById("modal-symlink-redownload").onclick = null;
      document.getElementById("modal-symlink-cancel").onclick = null;
      resolve(result);
    };

    document.getElementById("modal-symlink-yes").onclick = () => cleanup("symlink");
    document.getElementById("modal-symlink-redownload").onclick = () => cleanup("redownload");
    document.getElementById("modal-symlink-cancel").onclick = () => cleanup("cancel");
  });
}

// ─── Queue display ────────────────────────────────────
async function refreshQueue() {
  try {
    const data = await api("/queue");
    renderCurrent(data.current);
    renderPending(data.pending);
    renderHistory(data.history);
  } catch (e) {
    console.error("Queue refresh:", e);
  }
}

function renderCurrent(current) {
  const el = document.getElementById("queue-current");
  if (!current) {
    el.classList.remove("active");
    el.innerHTML = '<p class="hint-empty">Aucun téléchargement en cours</p>';
    return;
  }
  el.classList.add("active");

  // Tente d'estimer le total via state.currentFiles (si match)
  const totalBytes = current.size_bytes || 0;
  const dlBytes = current.downloaded_bytes || 0;
  const pct = totalBytes > 0 ? (dlBytes / totalBytes) * 100 : 0;

  el.innerHTML = `
    <div class="queue-current-title">⬇️ ${escapeHtml(current.repo)} → ${escapeHtml(current.quant)}</div>
    <div class="mono" style="font-size:12px;color:var(--text-muted)">
      ${escapeHtml(current.filename)}
    </div>
    <div class="queue-progress-bar">
      <div class="queue-progress-fill" style="width: ${pct.toFixed(1)}%"></div>
    </div>
    <div class="queue-progress-meta">
      <span>${formatBytes(dlBytes)}${totalBytes > 0 ? ` / ${formatBytes(totalBytes)}` : ''}</span>
      <span>${pct.toFixed(1)}%</span>
    </div>
  `;
}

function renderPending(pending) {
  const el = document.getElementById("queue-pending");
  if (!pending.length) {
    el.innerHTML = '<p class="hint-empty">Queue vide</p>';
    return;
  }
  el.innerHTML = pending.map(p => `
    <div class="queue-item">
      <div>
        <div class="queue-item-name">${escapeHtml(p.filename)}</div>
        <div class="queue-item-meta">${escapeHtml(p.repo)} • ${escapeHtml(p.quant)}</div>
      </div>
      <button class="btn-ghost btn-cancel-queue" data-id="${escapeHtml(p.id)}" title="Annuler">×</button>
    </div>
  `).join("");
  el.querySelectorAll(".btn-cancel-queue").forEach(btn => {
    btn.addEventListener("click", async () => {
      try {
        await api(`/queue/${btn.dataset.id}`, { method: "DELETE" });
        toast("Annulé", "success", 1500);
      } catch (e) {
        toast(`Erreur annulation : ${e.message}`, "error");
      }
    });
  });
}

// ─── History ──────────────────────────────────────────
function renderHistory(history) {
  const el = document.getElementById("history-list");
  if (!history.length) {
    el.innerHTML = '<p class="hint-empty">Aucune action dans l\'historique</p>';
    return;
  }
  el.innerHTML = history.map(h => {
    const size = h.size_bytes ? (h.size_bytes / 1024 ** 3).toFixed(2) + " GB" : "—";
    const time = h.timestamp ? h.timestamp.slice(11, 16) : "?";
    return `
      <div class="history-item">
        <div>
          <div class="queue-item-name">${escapeHtml(h.filename)}</div>
          <div class="queue-item-meta">
            ${time} • ${escapeHtml(h.repo)} •
            <span class="history-status ${escapeHtml(h.status)}">${escapeHtml(h.status)}</span>
            ${h.error ? ` • <span style="color:var(--text-danger)">${escapeHtml(h.error.slice(0,60))}</span>` : ''}
          </div>
        </div>
        <span class="mono" style="color:var(--text-muted)">${size}</span>
      </div>
    `;
  }).join("");
}

// ─── Installed ────────────────────────────────────────
async function refreshInstalled() {
  try {
    const models = await api("/installed");
    renderInstalled(models);
  } catch (e) {
    console.error("Installed refresh:", e);
  }
}

function renderInstalled(models) {
  const el = document.getElementById("installed-list");
  if (!models.length) {
    el.innerHTML = '<p class="hint-empty">Aucun modèle dans ~/llm-models/</p>';
    return;
  }
  el.innerHTML = models.map(m => `
    <div class="installed-item">
      <div>
        <div class="installed-item-name">${escapeHtml(m.name)}
          <span class="tag ${m.is_symlink ? 'tag-symlink' : 'tag-file'}">${m.is_symlink ? 'symlink' : 'fichier'}</span>
        </div>
        <div class="installed-item-meta mono" title="${escapeHtml(m.real_path)}">
          ${formatGB(m.size_gb)} • ${escapeHtml(m.real_path)}
        </div>
      </div>
      <button class="btn-ghost btn-del-installed" data-name="${escapeHtml(m.name)}" title="Supprimer">🗑️</button>
    </div>
  `).join("");
  el.querySelectorAll(".btn-del-installed").forEach(btn => {
    btn.addEventListener("click", async () => {
      const name = btn.dataset.name;
      if (!confirm(`Supprimer "${name}" ?\n\n(Si symlink : supprime seulement le lien)`)) return;
      try {
        const r = await api(`/installed/${encodeURIComponent(name)}`, { method: "DELETE" });
        toast(`Supprimé : ${name}`, "success");
        if (r.yaml_entries_removed?.length) {
          toast(`Yaml nettoyé : ${r.yaml_entries_removed.join(", ")}`, "info", 3000);
        }
        await refreshInstalled();
      } catch (e) {
        toast(`Erreur : ${e.message}`, "error");
      }
    });
  });
}

// ─── Deps modal ───────────────────────────────────────
async function showDeps() {
  const modal = document.getElementById("modal-deps");
  const list = document.getElementById("modal-deps-list");
  list.innerHTML = '<p class="hint-empty">Chargement...</p>';
  modal.classList.remove("hidden");

  try {
    const deps = await api("/deps-status");
    list.innerHTML = Object.entries(deps).map(([name, info]) => `
      <div class="installed-item" style="margin-bottom:6px">
        <div>
          <div class="installed-item-name">${escapeHtml(name)}</div>
          <div class="installed-item-meta">${info.installed ? `v${info.installed}` : 'non installé'}</div>
        </div>
        <span>${info.available ? '✅' : '❌'}</span>
      </div>
    `).join("");
  } catch (e) {
    list.innerHTML = `<p style="color:var(--text-danger)">${escapeHtml(e.message)}</p>`;
  }
}

// ─── Tabs & collapse ───────────────────────────────────
function setupTabs() {
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(tab).classList.add("active");
    });
  });
}

function setupCollapse() {
  document.querySelectorAll(".btn-collapse").forEach(btn => {
    btn.addEventListener("click", () => {
      const target = document.getElementById(btn.dataset.target);
      target.classList.toggle("collapsed");
      btn.classList.toggle("collapsed");
    });
  });
}

// ─── Init ──────────────────────────────────────────────
async function init() {
  // Thème depuis localStorage si dispo
  const savedTheme = localStorage.getItem("ezmodl-theme");
  if (savedTheme) applyTheme(savedTheme);

  setupTabs();
  setupCollapse();

  // Listeners
  document.getElementById("btn-theme").addEventListener("click", toggleTheme);
  document.getElementById("btn-deps").addEventListener("click", showDeps);
  document.getElementById("btn-refresh").addEventListener("click", () => {
    loadVRAM(); refreshQueue(); refreshInstalled();
    toast("Actualisé", "info", 1500);
  });

  document.getElementById("btn-search").addEventListener("click", doSearch);
  document.getElementById("search-input").addEventListener("keypress", e => {
    if (e.key === "Enter") doSearch();
  });
  document.getElementById("btn-direct").addEventListener("click", doDirectLoad);
  document.getElementById("direct-input").addEventListener("keypress", e => {
    if (e.key === "Enter") doDirectLoad();
  });

  document.getElementById("kv-target").addEventListener("input", updateBudget);
  document.getElementById("btn-close-quants").addEventListener("click", () => {
    document.getElementById("section-quants").classList.add("hidden");
  });
  document.getElementById("btn-queue-selected").addEventListener("click", addSelectedToQueue);

  document.getElementById("modal-deps-close").addEventListener("click", () => {
    document.getElementById("modal-deps").classList.add("hidden");
  });

  // Initial load
  await loadPrefs();
  await loadVRAM();
  await refreshQueue();
  await refreshInstalled();

  // Refresh queue toutes les secondes
  setInterval(refreshQueue, REFRESH_INTERVAL);
  // VRAM moins fréquent
  setInterval(loadVRAM, 5000);
}

document.addEventListener("DOMContentLoaded", init);
