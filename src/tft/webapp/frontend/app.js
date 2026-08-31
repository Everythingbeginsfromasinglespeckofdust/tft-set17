/**
 * TFT Decision Assistant Web v1.1 Frontend Application Logic.
 * Fast Manual Input, Live Top Status Bar Sync, Always-Visible Set 18 Champion Pool.
 */

// Application State
const state = {
  stage: "2-1",
  hp: 100,
  gold: 30,
  level: 4,
  xp: 0,
  streak: 0,
  
  // Units & Shop
  boardUnits: [],
  benchUnits: [],
  shop: [null, null, null, null, null],
  itemBench: [],
  augments: [],

  // Interaction Target ('board' | 'bench' | 'shop')
  activeTarget: "board",
  activeShopSlot: 0,

  // Recent Champions (max 8)
  recentChampions: [],

  // Undo Stack (Draft history)
  undoStack: [],

  // Session & Review State
  sessionId: "SESSION_LIVE_001",
  turnsHistory: [],
  currentDecision: null,
  previousDecision: null,
  previousTurnState: null,

  // Blind Mode State
  isBlindMode: false,
  blindRevealed: false,
  humanPreferredAction: "UNKNOWN",
  actualPlayerAction: "UNKNOWN",
  humanFeedback: "UNKNOWN",
  turnNotes: "",
  videoTimestampSec: null,

  // Reference Catalog
  champions: [],
  costFilter: "all",
  searchQuery: ""
};

// ==============================================================================
// 1. Initialization
// ==============================================================================

document.addEventListener("DOMContentLoaded", async () => {
  initTopBarSync();
  initTargetTabs();
  initSteppers();
  initActionButtons();
  initModals();
  initKeyboardShortcuts();

  await loadChampionsRoster();
  await loadVideoList();

  pushUndoState();
  renderAll();
});

async function loadChampionsRoster() {
  try {
    const res = await fetch("/api/data/champions");
    state.champions = await res.json();
    renderChampionPoolGrid();
  } catch (err) {
    console.error("Failed to load Set 18 champions:", err);
  }
}

async function loadVideoList() {
  try {
    const res = await fetch("/api/videos");
    const videos = await res.json();
    const select = document.getElementById("video-select");
    select.innerHTML = "";
    videos.forEach(v => {
      const opt = document.createElement("option");
      opt.value = v.filename;
      opt.textContent = `${v.filename} (${v.size_mb} MB)`;
      select.appendChild(opt);
    });
  } catch (err) {
    console.error("Failed to list videos:", err);
  }
}

// ==============================================================================
// 2. Top Status Bar Real-Time Synchronization
// ==============================================================================

function initTopBarSync() {
  // Directly bind input changes to top bar and draft state
  document.getElementById("input-stage").addEventListener("input", (e) => {
    state.stage = e.target.value.trim();
    syncTopStatusBar();
  });
  document.getElementById("input-hp").addEventListener("input", (e) => {
    state.hp = Math.min(100, Math.max(0, parseInt(e.target.value) || 0));
    syncTopStatusBar();
  });
  document.getElementById("input-gold").addEventListener("input", (e) => {
    state.gold = Math.min(250, Math.max(0, parseInt(e.target.value) || 0));
    syncTopStatusBar();
  });
  document.getElementById("input-level").addEventListener("input", (e) => {
    state.level = Math.min(11, Math.max(1, parseInt(e.target.value) || 1));
    document.getElementById("board-max").textContent = state.level;
    syncTopStatusBar();
  });
  document.getElementById("input-xp").addEventListener("input", (e) => {
    state.xp = Math.max(0, parseInt(e.target.value) || 0);
    syncTopStatusBar();
  });
}

function syncTopStatusBar() {
  document.getElementById("top-bar-stage").textContent = state.stage;
  document.getElementById("top-bar-hp").textContent = state.hp;
  document.getElementById("top-bar-gold").textContent = state.gold;
  document.getElementById("top-bar-level").textContent = state.level;
  document.getElementById("top-bar-xp").textContent = state.xp;
  
  // Completeness calculation
  const comp = calculateCompleteness();
  document.getElementById("top-bar-completeness").textContent = `${comp.score}/${comp.total} ✓`;
}

function calculateCompleteness() {
  const checklist = {
    stage: Boolean(state.stage && /^[1-8]-[1-7]$/.test(state.stage)),
    hp: state.hp > 0,
    gold: state.gold >= 0,
    level: state.level >= 1,
    xp: state.xp >= 0,
    board: state.boardUnits.length > 0,
    bench: true,
    shop: state.shop.length === 5
  };
  const score = Object.values(checklist).filter(Boolean).length;
  return { score, total: Object.keys(checklist).length };
}

// ==============================================================================
// 3. Quick Steppers & Target Selectors
// ==============================================================================

function initSteppers() {
  // Stage Steppers
  document.getElementById("btn-stage-prev").onclick = () => stepStage(-1);
  document.getElementById("btn-stage-next").onclick = () => stepStage(1);

  // HP Steppers (0 ~ 100)
  document.getElementById("btn-hp-m10").onclick = () => updateNumericField("hp", -10, 0, 100);
  document.getElementById("btn-hp-m1").onclick = () => updateNumericField("hp", -1, 0, 100);
  document.getElementById("btn-hp-p1").onclick = () => updateNumericField("hp", 1, 0, 100);
  document.getElementById("btn-hp-p10").onclick = () => updateNumericField("hp", 10, 0, 100);

  // Gold Steppers (0 ~ 250)
  document.getElementById("btn-gold-m10").onclick = () => updateNumericField("gold", -10, 0, 250);
  document.getElementById("btn-gold-m5").onclick = () => updateNumericField("gold", -5, 0, 250);
  document.getElementById("btn-gold-p5").onclick = () => updateNumericField("gold", 5, 0, 250);
  document.getElementById("btn-gold-p10").onclick = () => updateNumericField("gold", 10, 0, 250);

  // Level & XP Steppers
  document.getElementById("btn-lvl-m1").onclick = () => updateNumericField("level", -1, 1, 11);
  document.getElementById("btn-lvl-p1").onclick = () => updateNumericField("level", 1, 1, 11);
  document.getElementById("btn-xp-p4").onclick = () => updateNumericField("xp", 4, 0, 200);

  // Undo Draft
  document.getElementById("btn-undo-draft").onclick = performUndo;
}

function updateNumericField(field, delta, min, max) {
  pushUndoState();
  state[field] = Math.min(max, Math.max(min, (state[field] || 0) + delta));
  renderInputs();
  syncTopStatusBar();
}

function stepStage(delta) {
  pushUndoState();
  const parts = state.stage.split("-");
  let s = parseInt(parts[0]) || 2;
  let r = parseInt(parts[1]) || 1;
  r += delta;
  if (r > 7) { s += 1; r = 1; }
  else if (r < 1) { s = Math.max(1, s - 1); r = 7; }
  state.stage = `${s}-${r}`;
  renderInputs();
  syncTopStatusBar();
}

function initTargetTabs() {
  document.getElementById("tab-target-board").onclick = () => setTarget("board");
  document.getElementById("tab-target-bench").onclick = () => setTarget("bench");
  document.getElementById("tab-target-shop").onclick = () => setTarget("shop");

  document.getElementById("btn-select-target-board").onclick = () => setTarget("board");
  document.getElementById("btn-select-target-bench").onclick = () => setTarget("bench");

  // Cost Filters in Champion Pool
  document.querySelectorAll(".filter-pill").forEach(btn => {
    btn.onclick = () => {
      document.querySelectorAll(".filter-pill").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      state.costFilter = btn.dataset.cost;
      renderChampionPoolGrid();
    };
  });

  // Quick Search input
  document.getElementById("champ-quick-search").addEventListener("input", (e) => {
    state.searchQuery = e.target.value.trim().toLowerCase();
    renderChampionPoolGrid();
  });

  // Clear Shop button
  document.getElementById("btn-clear-shop").onclick = () => {
    pushUndoState();
    state.shop = [null, null, null, null, null];
    renderShopSlots();
    syncTopStatusBar();
  };
}

function setTarget(target, shopSlot = 0) {
  state.activeTarget = target;
  if (target === "shop") state.activeShopSlot = shopSlot;

  document.querySelectorAll(".target-tab").forEach(tab => {
    tab.classList.toggle("active", tab.dataset.target === target);
  });

  const badge = document.getElementById("active-target-badge");
  if (target === "board") badge.textContent = "TARGET: BOARD";
  else if (target === "bench") badge.textContent = "TARGET: BENCH";
  else if (target === "shop") badge.textContent = `TARGET: SHOP (SLOT ${state.activeShopSlot + 1})`;

  renderShopSlots();
}

// ==============================================================================
// 4. Champion Pool & 1-Click Fast Add
// ==============================================================================

function renderChampionPoolGrid() {
  const container = document.getElementById("champion-pool-grid");
  container.innerHTML = "";

  const filtered = state.champions.filter(c => {
    if (state.costFilter !== "all" && String(c.cost) !== state.costFilter) return false;
    if (state.searchQuery && !c.name.toLowerCase().includes(state.searchQuery)) return false;
    return true;
  });

  filtered.forEach(c => {
    const card = document.createElement("div");
    card.className = "champ-card-mini";
    
    // Check if splash exists
    const imgSrc = c.splash_art ? `/img/champion/${c.splash_art}` : "";
    const imgHtml = imgSrc ? `<img src="${imgSrc}" alt="${c.name}" onerror="this.style.display='none'">` : '';

    card.innerHTML = `
      ${imgHtml}
      <span class="c-name" title="${c.name}">${c.name}</span>
      <span class="cost-tag c${c.cost}">${c.cost}G</span>
    `;

    card.onclick = () => onChampionPoolClick(c.name);
    container.appendChild(card);
  });
}

function onChampionPoolClick(champName) {
  pushUndoState();
  const meta = getChampionMeta(champName);
  
  // Track Recent Champions
  if (!state.recentChampions.includes(meta.name)) {
    state.recentChampions.unshift(meta.name);
    if (state.recentChampions.length > 6) state.recentChampions.pop();
    renderRecentChampions();
  }

  // Fast 1-Click Direct Placement (No modals, instant state update)
  if (state.activeTarget === "board") {
    state.boardUnits.push({
      champion: meta.name,
      cost: meta.cost,
      star_level: 1,
      items: []
    });
    renderBoardUnits();
  } else if (state.activeTarget === "bench") {
    state.benchUnits.push({
      champion: meta.name,
      cost: meta.cost,
      star_level: 1,
      items: []
    });
    renderBenchUnits();
  } else if (state.activeTarget === "shop") {
    state.shop[state.activeShopSlot] = meta.name;
    // Auto-advance to next shop slot
    state.activeShopSlot = (state.activeShopSlot + 1) % 5;
    document.getElementById("active-target-badge").textContent = `TARGET: SHOP (SLOT ${state.activeShopSlot + 1})`;
    renderShopSlots();
  }

  syncTopStatusBar();
}

function renderRecentChampions() {
  const container = document.getElementById("recent-chips-list");
  if (state.recentChampions.length === 0) {
    container.innerHTML = `<span class="no-recents">None yet</span>`;
    return;
  }
  container.innerHTML = "";
  state.recentChampions.forEach(name => {
    const chip = document.createElement("span");
    chip.className = "recent-chip";
    chip.textContent = name;
    chip.onclick = () => onChampionPoolClick(name);
    container.appendChild(chip);
  });
}

function getChampionMeta(name) {
  if (!name) return { name: "Unknown", cost: 1 };
  const found = state.champions.find(c => c.name.toLowerCase() === name.toLowerCase());
  return found || { name: name, cost: 1 };
}

// ==============================================================================
// 5. Units & Shop Rendering with Star Toggles and Deletion
// ==============================================================================

function renderBoardUnits() {
  const container = document.getElementById("board-units-chips");
  const countSpan = document.getElementById("board-count");
  countSpan.textContent = state.boardUnits.length;
  container.innerHTML = "";

  if (state.boardUnits.length === 0) {
    container.innerHTML = `<span class="empty-hint">Click champions in the pool on left to add to Board</span>`;
    return;
  }

  state.boardUnits.forEach((u, idx) => {
    const chip = document.createElement("div");
    chip.className = "unit-chip-item";
    chip.innerHTML = `
      <span class="cost-tag c${u.cost}">${u.cost}G</span>
      <span class="u-name">${u.champion}</span>
      <div class="unit-stars-toggle">
        <span class="star-tag ${u.star_level === 1 ? 'active' : ''}" onclick="toggleStar('board', ${idx}, 1)">1★</span>
        <span class="star-tag ${u.star_level === 2 ? 'active' : ''}" onclick="toggleStar('board', ${idx}, 2)">2★</span>
        <span class="star-tag ${u.star_level === 3 ? 'active' : ''}" onclick="toggleStar('board', ${idx}, 3)">3★</span>
      </div>
      <button class="btn-del-unit" onclick="removeUnitItem('board', ${idx})" title="Remove Unit">✕</button>
    `;
    container.appendChild(chip);
  });
}

function renderBenchUnits() {
  const container = document.getElementById("bench-units-chips");
  const countSpan = document.getElementById("bench-count");
  countSpan.textContent = state.benchUnits.length;
  container.innerHTML = "";

  if (state.benchUnits.length === 0) {
    container.innerHTML = `<span class="empty-hint">Bench empty</span>`;
    return;
  }

  state.benchUnits.forEach((u, idx) => {
    const chip = document.createElement("div");
    chip.className = "unit-chip-item";
    chip.innerHTML = `
      <span class="cost-tag c${u.cost}">${u.cost}G</span>
      <span class="u-name">${u.champion}</span>
      <div class="unit-stars-toggle">
        <span class="star-tag ${u.star_level === 1 ? 'active' : ''}" onclick="toggleStar('bench', ${idx}, 1)">1★</span>
        <span class="star-tag ${u.star_level === 2 ? 'active' : ''}" onclick="toggleStar('bench', ${idx}, 2)">2★</span>
        <span class="star-tag ${u.star_level === 3 ? 'active' : ''}" onclick="toggleStar('bench', ${idx}, 3)">3★</span>
      </div>
      <button class="btn-del-unit" onclick="removeUnitItem('bench', ${idx})" title="Remove Unit">✕</button>
    `;
    container.appendChild(chip);
  });
}

function renderShopSlots() {
  const container = document.getElementById("shop-slots-container");
  container.innerHTML = "";

  for (let i = 0; i < 5; i++) {
    const champName = state.shop[i];
    const meta = champName ? getChampionMeta(champName) : null;
    const isTarget = state.activeTarget === "shop" && state.activeShopSlot === i;

    const btn = document.createElement("div");
    btn.className = `shop-slot-btn ${champName ? '' : 'empty'} ${isTarget ? 'active-target' : ''}`;
    
    if (champName && meta) {
      btn.innerHTML = `
        <span class="s-index">SLOT ${i+1}</span>
        <span class="s-name">${meta.name}</span>
        <span class="cost-tag c${meta.cost}">${meta.cost}G</span>
      `;
    } else {
      btn.innerHTML = `
        <span class="s-index">SLOT ${i+1}</span>
        <span class="s-name">[EMPTY]</span>
        <span class="cost-tag">-</span>
      `;
    }

    btn.onclick = () => {
      if (champName) {
        // Toggle to empty if already clicked
        pushUndoState();
        state.shop[i] = null;
        renderShopSlots();
      } else {
        setTarget("shop", i);
      }
      syncTopStatusBar();
    };

    container.appendChild(btn);
  }
}

window.toggleStar = (target, idx, star) => {
  pushUndoState();
  const list = target === "board" ? state.boardUnits : state.benchUnits;
  if (list[idx]) {
    list[idx].star_level = star;
    if (target === "board") renderBoardUnits();
    else renderBenchUnits();
  }
};

window.removeUnitItem = (target, idx) => {
  pushUndoState();
  const list = target === "board" ? state.boardUnits : state.benchUnits;
  list.splice(idx, 1);
  if (target === "board") renderBoardUnits();
  else renderBenchUnits();
  syncTopStatusBar();
};

// ==============================================================================
// 6. Undo & State Restoration
// ==============================================================================

function pushUndoState() {
  const snapshot = {
    stage: state.stage,
    hp: state.hp,
    gold: state.gold,
    level: state.level,
    xp: state.xp,
    boardUnits: JSON.parse(JSON.stringify(state.boardUnits)),
    benchUnits: JSON.parse(JSON.stringify(state.benchUnits)),
    shop: JSON.parse(JSON.stringify(state.shop))
  };
  state.undoStack.push(snapshot);
  if (state.undoStack.length > 20) state.undoStack.shift();
}

function performUndo() {
  if (state.undoStack.length === 0) return;
  const prev = state.undoStack.pop();
  state.stage = prev.stage;
  state.hp = prev.hp;
  state.gold = prev.gold;
  state.level = prev.level;
  state.xp = prev.xp;
  state.boardUnits = prev.boardUnits;
  state.benchUnits = prev.benchUnits;
  state.shop = prev.shop;
  renderAll();
}

function renderInputs() {
  document.getElementById("input-stage").value = state.stage;
  document.getElementById("input-hp").value = state.hp;
  document.getElementById("input-gold").value = state.gold;
  document.getElementById("input-level").value = state.level;
  document.getElementById("input-xp").value = state.xp;
  document.getElementById("board-max").textContent = state.level;
}

function renderAll() {
  renderInputs();
  syncTopStatusBar();
  renderBoardUnits();
  renderBenchUnits();
  renderShopSlots();
}

// ==============================================================================
// 7. Decision Engine Execution & Display
// ==============================================================================

function initActionButtons() {
  document.getElementById("btn-analyze").onclick = analyzeTurn;
  document.getElementById("btn-copy-prev").onclick = copyPreviousTurn;
  document.getElementById("btn-new-turn").onclick = resetCurrentTurn;
  document.getElementById("btn-toggle-blind").onclick = toggleBlindMode;
  document.getElementById("btn-reveal-engine").onclick = revealBlindDecision;

  // Feedback Buttons
  document.querySelectorAll(".btn-fb").forEach(btn => {
    btn.onclick = () => {
      document.querySelectorAll(".btn-fb").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.humanFeedback = btn.dataset.fb;
    };
  });

  // Preference Buttons (Blind mode)
  document.querySelectorAll(".btn-pref").forEach(btn => {
    btn.onclick = () => {
      document.querySelectorAll(".btn-pref").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.humanPreferredAction = btn.dataset.pref;
      document.getElementById("select-human-pref").value = btn.dataset.pref;
    };
  });

  // Select sync
  document.getElementById("select-actual-action").onchange = (e) => state.actualPlayerAction = e.target.value;
  document.getElementById("select-human-pref").onchange = (e) => state.humanPreferredAction = e.target.value;
  document.getElementById("input-turn-notes").oninput = (e) => state.turnNotes = e.target.value;

  document.getElementById("btn-save-turn").onclick = saveCurrentTurn;
  document.getElementById("btn-save-session").onclick = saveSessionToBackend;
}

async function analyzeTurn() {
  hideValidationErrors();
  state.blindRevealed = false;

  const payload = {
    stage_round: state.stage,
    hp: state.hp,
    gold: state.gold,
    level: state.level,
    xp: state.xp,
    streak: state.streak,
    board_units: state.boardUnits,
    bench_units: state.benchUnits,
    shop_units: state.shop,
    calibration_mode: document.getElementById("calib-mode-select").value,
    video_timestamp_sec: state.videoTimestampSec,
    actual_player_action: state.actualPlayerAction,
    human_preferred_action: state.humanPreferredAction,
    notes: state.turnNotes
  };

  try {
    const res = await fetch("/api/decide", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json();
      showValidationErrors(err.detail?.errors || [err.detail || "Validation Error"]);
      return;
    }

    const decision = await res.json();
    state.previousDecision = state.currentDecision;
    state.currentDecision = decision;

    if (state.isBlindMode && !state.blindRevealed) {
      document.getElementById("blind-mode-banner").classList.remove("hidden");
      document.getElementById("decision-empty-state").classList.add("hidden");
      document.getElementById("decision-active-content").classList.add("hidden");
    } else {
      renderDecisionResults(decision);
    }

    // Render Turn Diff if previous state exists
    if (state.previousTurnState) {
      renderTurnDiff(state.previousTurnState, payload);
    }

  } catch (err) {
    showValidationErrors([`Network / Server error: ${err.message}`]);
  }
}

function renderDecisionResults(decision) {
  document.getElementById("blind-mode-banner").classList.add("hidden");
  document.getElementById("decision-empty-state").classList.add("hidden");
  document.getElementById("decision-active-content").classList.remove("hidden");

  // Banner
  const act = decision.recommended_action;
  const banner = document.getElementById("rec-banner");
  banner.className = `rec-banner act-${act === 'ROLL' ? 'roll' : (act === 'SAVE_GOLD' ? 'save' : 'level')}`;

  document.getElementById("rec-action-name").textContent = act;
  document.getElementById("rec-gap-badge").textContent = `Gap: +${decision.action_score_gap.toFixed(4)}`;
  document.getElementById("rec-score-val").textContent = decision.score.toFixed(4);
  document.getElementById("rec-conf-val").textContent = decision.confidence.toFixed(2);
  document.getElementById("rec-engine-tag").textContent = decision.calibration.applied ? `CALIB_C (${decision.calibration.mode})` : `Frozen Base Engine`;

  // Operational Direction
  const dir = decision.current_direction;
  document.getElementById("dir-now-text").textContent = dir.now.description;
  const watchList = document.getElementById("dir-watch-list");
  watchList.innerHTML = "";
  dir.watch.forEach(w => {
    const li = document.createElement("li");
    li.textContent = w;
    watchList.appendChild(li);
  });
  document.getElementById("dir-then-text").textContent = dir.then.description;

  // Reasons
  const reasonsContainer = document.getElementById("reasons-container");
  reasonsContainer.innerHTML = "";
  decision.reasons.forEach(r => {
    const item = document.createElement("div");
    item.className = "reason-item";
    item.textContent = `[${r.code}] ${r.summary} (impact: ${r.impact.toFixed(3)})`;
    reasonsContainer.appendChild(item);
  });

  // Scores Table
  const tbody = document.getElementById("scores-table-body");
  tbody.innerHTML = "";
  decision.all_scores.forEach(asc => {
    const tr = document.createElement("tr");
    if (asc.action === act) tr.className = "best-row";

    const surv = asc.breakdown.survival?.contribution?.toFixed(3) || "0.000";
    const econ = asc.breakdown.economy?.contribution?.toFixed(3) || "0.000";
    const pow = asc.breakdown.board_power?.contribution?.toFixed(3) || "0.000";
    const upg = asc.breakdown.upgrade?.contribution?.toFixed(3) || "0.000";

    tr.innerHTML = `
      <td><strong>${asc.action}</strong></td>
      <td><strong>${asc.score.toFixed(4)}</strong></td>
      <td>${surv}</td>
      <td>${econ}</td>
      <td>${pow}</td>
      <td>${upg}</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderTurnDiff(prev, curr) {
  const card = document.getElementById("turn-diff-card");
  card.classList.remove("hidden");
  document.getElementById("diff-stage-label").textContent = `${prev.stage_round} → ${curr.stage_round}`;

  const hpDiff = curr.hp - prev.hp;
  const goldDiff = curr.gold - prev.gold;
  const lvlDiff = curr.level - prev.level;

  document.getElementById("diff-grid-content").innerHTML = `
    <div style="font-size:11px; display:flex; gap:14px;">
      <span>HP: <strong>${prev.hp} → ${curr.hp} (${hpDiff >= 0 ? '+' : ''}${hpDiff})</strong></span>
      <span>Gold: <strong>${prev.gold} → ${curr.gold} (${goldDiff >= 0 ? '+' : ''}${goldDiff})</strong></span>
      <span>Level: <strong>${prev.level} → ${curr.level}</strong></span>
    </div>
  `;
}

function copyPreviousTurn() {
  if (state.turnsHistory.length === 0) {
    alert("No previous turn recorded in this session to copy.");
    return;
  }
  pushUndoState();
  const lastTurn = state.turnsHistory[state.turnsHistory.length - 1];
  state.previousTurnState = JSON.parse(JSON.stringify(lastTurn.state));

  const prev = lastTurn.state;
  state.hp = prev.hp;
  state.gold = prev.gold;
  state.level = prev.level;
  state.xp = prev.xp;
  state.boardUnits = JSON.parse(JSON.stringify(prev.board_units || []));
  state.benchUnits = JSON.parse(JSON.stringify(prev.bench_units || []));
  state.shop = JSON.parse(JSON.stringify(prev.shop_units || [null, null, null, null, null]));

  stepStage(1);
  renderAll();
}

function resetCurrentTurn() {
  pushUndoState();
  state.boardUnits = [];
  state.benchUnits = [];
  state.shop = [null, null, null, null, null];
  state.humanFeedback = "UNKNOWN";
  state.humanPreferredAction = "UNKNOWN";
  state.actualPlayerAction = "UNKNOWN";
  state.turnNotes = "";
  document.getElementById("input-turn-notes").value = "";
  renderAll();
}

function toggleBlindMode() {
  state.isBlindMode = !state.isBlindMode;
  state.blindRevealed = false;
  const btn = document.getElementById("btn-toggle-blind");
  btn.classList.toggle("btn-primary", state.isBlindMode);
  if (state.isBlindMode) {
    btn.innerHTML = `🔒 Blind Mode ON <span class="kbd-hint">[B]</span>`;
  } else {
    btn.innerHTML = `👁️ Blind Mode <span class="kbd-hint">[B]</span>`;
    document.getElementById("blind-mode-banner").classList.add("hidden");
    if (state.currentDecision) renderDecisionResults(state.currentDecision);
  }
}

function revealBlindDecision() {
  state.blindRevealed = true;
  if (state.currentDecision) {
    renderDecisionResults(state.currentDecision);
  }
}

function saveCurrentTurn() {
  if (!state.currentDecision) {
    alert("Please [ANALYZE] the turn before saving.");
    return;
  }

  const turnRecord = {
    turn_id: `TURN_${state.stage}_${Date.now()}`,
    stage_round: state.stage,
    video_timestamp_sec: state.videoTimestampSec,
    state: {
      stage_round: state.stage,
      hp: state.hp,
      gold: state.gold,
      level: state.level,
      xp: state.xp,
      board_units: state.boardUnits,
      bench_units: state.benchUnits,
      shop_units: state.shop
    },
    decision: state.currentDecision,
    actual_player_action: state.actualPlayerAction,
    human_preferred_action: state.humanPreferredAction,
    human_feedback: state.humanFeedback,
    human_judgment: state.humanFeedback,
    notes: state.turnNotes,
    reviewed_at_iso: new Date().toISOString()
  };

  state.turnsHistory.push(turnRecord);
  state.previousTurnState = JSON.parse(JSON.stringify(turnRecord.state));
  renderTurnHistory();
  saveSessionToBackend(false);
}

function renderTurnHistory() {
  const container = document.getElementById("history-timeline");
  document.getElementById("history-count").textContent = state.turnsHistory.length;
  container.innerHTML = "";

  if (state.turnsHistory.length === 0) {
    container.innerHTML = `<div class="empty-history">No turns recorded yet.</div>`;
    return;
  }

  state.turnsHistory.forEach((t, idx) => {
    const item = document.createElement("div");
    item.className = "history-item";
    item.innerHTML = `
      <span><strong>${t.stage_round}</strong> (HP ${t.state.hp}, ${t.state.gold}G)</span>
      <span>Rec: <strong>${t.decision.recommended_action}</strong> | FB: ${t.human_feedback}</span>
    `;
    item.onclick = () => loadTurnFromHistory(idx);
    container.appendChild(item);
  });
}

function loadTurnFromHistory(idx) {
  const t = state.turnsHistory[idx];
  if (!t) return;

  pushUndoState();
  state.stage = t.state.stage_round;
  state.hp = t.state.hp;
  state.gold = t.state.gold;
  state.level = t.state.level;
  state.xp = t.state.xp;
  state.boardUnits = JSON.parse(JSON.stringify(t.state.board_units || []));
  state.benchUnits = JSON.parse(JSON.stringify(t.state.bench_units || []));
  state.shop = JSON.parse(JSON.stringify(t.state.shop_units || []));
  state.currentDecision = t.decision;
  state.actualPlayerAction = t.actual_player_action;
  state.humanPreferredAction = t.human_preferred_action;
  state.humanFeedback = t.human_feedback;
  state.turnNotes = t.notes;

  renderAll();
  renderDecisionResults(t.decision);
}

async function saveSessionToBackend(showAlert = true) {
  const sessionId = document.getElementById("session-id-input").value.trim() || state.sessionId;
  const payload = {
    session_id: sessionId,
    turns: state.turnsHistory,
    video_filename: document.getElementById("video-select").value || ""
  };

  try {
    const res = await fetch("/api/sessions/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (showAlert) alert(`Session '${sessionId}' saved successfully (${data.turns_saved} turns).`);
  } catch (err) {
    if (showAlert) alert(`Failed to save session: ${err.message}`);
  }
}

function showValidationErrors(errors) {
  const box = document.getElementById("validation-error-box");
  const list = document.getElementById("validation-errors-list");
  list.innerHTML = "";
  errors.forEach(e => {
    const li = document.createElement("li");
    li.textContent = typeof e === "string" ? e : JSON.stringify(e);
    list.appendChild(li);
  });
  box.classList.remove("hidden");
}

function hideValidationErrors() {
  document.getElementById("validation-error-box").classList.add("hidden");
}

// ==============================================================================
// 8. Modals & Shortcuts
// ==============================================================================

function initModals() {
  // Video modal
  document.getElementById("btn-toggle-video").onclick = () => {
    document.getElementById("video-assistant-modal").classList.remove("hidden");
  };
  document.getElementById("btn-close-video-modal").onclick = () => {
    document.getElementById("video-assistant-modal").classList.add("hidden");
  };
  document.getElementById("btn-load-video").onclick = () => {
    const sel = document.getElementById("video-select").value;
    if (sel) {
      const vid = document.getElementById("replay-video");
      vid.src = `/api/videos/stream/${sel}`;
      vid.play();
    }
  };

  // Video time tracking
  const vid = document.getElementById("replay-video");
  vid.ontimeupdate = () => {
    const sec = vid.currentTime;
    state.videoTimestampSec = sec;
    const m = Math.floor(sec / 60);
    const s = (sec % 60).toFixed(2);
    document.getElementById("video-time-str").textContent = `${String(m).padStart(2, '0')}:${String(s).padStart(5, '0')}`;
    document.getElementById("video-time-sec").textContent = sec.toFixed(1);
  };

  document.getElementById("btn-seek-m10").onclick = () => vid.currentTime = Math.max(0, vid.currentTime - 10);
  document.getElementById("btn-seek-m5").onclick = () => vid.currentTime = Math.max(0, vid.currentTime - 5);
  document.getElementById("btn-seek-p5").onclick = () => vid.currentTime += 5;
  document.getElementById("btn-seek-p10").onclick = () => vid.currentTime += 10;
  document.getElementById("video-speed-select").onchange = (e) => vid.playbackRate = parseFloat(e.target.value);
  document.getElementById("btn-capture-checkpoint").onclick = () => {
    alert(`Captured video timestamp: ${vid.currentTime.toFixed(1)}s for turn ${state.stage}`);
  };

  // Shortcuts modal
  document.getElementById("btn-shortcuts-modal").onclick = () => {
    document.getElementById("shortcuts-modal").classList.remove("hidden");
  };
  document.getElementById("btn-close-shortcuts").onclick = () => {
    document.getElementById("shortcuts-modal").classList.add("hidden");
  };
}

function initKeyboardShortcuts() {
  document.addEventListener("keydown", (e) => {
    if (["INPUT", "TEXTAREA"].includes(e.target.tagName)) {
      if (e.key === "Enter" && e.target.id !== "champ-quick-search") {
        analyzeTurn();
      }
      return;
    }

    if (e.key === "Enter") {
      e.preventDefault();
      analyzeTurn();
    } else if (e.ctrlKey && (e.key === "s" || e.key === "S")) {
      e.preventDefault();
      saveCurrentTurn();
    } else if (e.key === "p" || e.key === "P") {
      copyPreviousTurn();
    } else if (e.key === "n" || e.key === "N") {
      resetCurrentTurn();
    } else if (e.key === "b" || e.key === "B") {
      toggleBlindMode();
    } else if (e.key === "1") {
      document.querySelector(".btn-pref[data-pref='ROLL']")?.click();
    } else if (e.key === "2") {
      document.querySelector(".btn-pref[data-pref='LEVEL_UP']")?.click();
    } else if (e.key === "3") {
      document.querySelector(".btn-pref[data-pref='SAVE_GOLD']")?.click();
    } else if (e.key === "4") {
      document.querySelector(".btn-pref[data-pref='UNKNOWN']")?.click();
    }
  });
}
