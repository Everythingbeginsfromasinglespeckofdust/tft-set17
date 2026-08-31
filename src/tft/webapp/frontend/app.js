/**
 * TFT Decision Assistant Web v1 Frontend Application Logic.
 */

// Application State
const state = {
  stage: "2-1",
  hp: 100,
  gold: 30,
  level: 4,
  xp: 0,
  streak: 0,
  shop: [null, null, null, null, null],
  boardUnits: [],
  benchUnits: [],
  itemBench: [],
  augments: [],
  
  // Review & Session State
  sessionId: "SESSION_LIVE_001",
  turnsHistory: [],
  currentTurnIndex: -1,
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

  // Reference Catalogs
  champions: [],
  items: [],
  pickerTarget: null // { type: 'shop'|'board'|'bench', index: number }
};

// ==============================================================================
// 1. Initialization & Reference Data Loading
// ==============================================================================

document.addEventListener("DOMContentLoaded", async () => {
  initSteppers();
  initShopSlots();
  initActionButtons();
  initModals();
  initKeyboardShortcuts();
  
  await loadReferenceData();
  await loadVideoList();
  
  renderState();
});

async function loadReferenceData() {
  try {
    const [champsRes, itemsRes] = await Promise.all([
      fetch("/api/data/champions"),
      fetch("/api/data/items")
    ]);
    state.champions = await champsRes.json();
    state.items = await itemsRes.json();
    renderChampionPickerGrid();
  } catch (err) {
    console.error("Failed to load reference data:", err);
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
// 2. Stepper Controls & State Synchronization
// ==============================================================================

function initSteppers() {
  // Stage Steppers
  document.getElementById("btn-stage-prev").onclick = () => stepStage(-1);
  document.getElementById("btn-stage-next").onclick = () => stepStage(1);
  document.getElementById("input-stage").onchange = (e) => {
    state.stage = e.target.value.trim();
  };

  // HP Steppers
  document.getElementById("btn-hp-m10").onclick = () => updateNumericField("hp", -10, 0, 150);
  document.getElementById("btn-hp-m1").onclick = () => updateNumericField("hp", -1, 0, 150);
  document.getElementById("btn-hp-p1").onclick = () => updateNumericField("hp", 1, 0, 150);
  document.getElementById("btn-hp-p10").onclick = () => updateNumericField("hp", 10, 0, 150);
  document.getElementById("input-hp").onchange = (e) => state.hp = parseInt(e.target.value) || 0;

  // Gold Steppers
  document.getElementById("btn-gold-m10").onclick = () => updateNumericField("gold", -10, 0, 250);
  document.getElementById("btn-gold-m5").onclick = () => updateNumericField("gold", -5, 0, 250);
  document.getElementById("btn-gold-p5").onclick = () => updateNumericField("gold", 5, 0, 250);
  document.getElementById("btn-gold-p10").onclick = () => updateNumericField("gold", 10, 0, 250);
  document.getElementById("input-gold").onchange = (e) => state.gold = parseInt(e.target.value) || 0;

  // Level & XP Steppers
  document.getElementById("btn-lvl-m1").onclick = () => updateNumericField("level", -1, 1, 11);
  document.getElementById("btn-lvl-p1").onclick = () => updateNumericField("level", 1, 1, 11);
  document.getElementById("btn-xp-p4").onclick = () => updateNumericField("xp", 4, 0, 200);
  document.getElementById("input-level").onchange = (e) => {
    state.level = parseInt(e.target.value) || 1;
    document.getElementById("board-max").textContent = state.level;
  };
  document.getElementById("input-xp").onchange = (e) => state.xp = parseInt(e.target.value) || 0;
}

function updateNumericField(field, delta, min, max) {
  state[field] = Math.min(max, Math.max(min, (state[field] || 0) + delta));
  renderState();
}

function stepStage(delta) {
  const parts = state.stage.split("-");
  let s = parseInt(parts[0]) || 2;
  let r = parseInt(parts[1]) || 1;
  r += delta;
  if (r > 7) { s += 1; r = 1; }
  else if (r < 1) { s = Math.max(1, s - 1); r = 7; }
  state.stage = `${s}-${r}`;
  renderState();
}

function renderState() {
  document.getElementById("input-stage").value = state.stage;
  document.getElementById("input-hp").value = state.hp;
  document.getElementById("input-gold").value = state.gold;
  document.getElementById("input-level").value = state.level;
  document.getElementById("input-xp").value = state.xp;
  document.getElementById("board-max").textContent = state.level;
  
  renderShopSlots();
  renderUnitsList("board");
  renderUnitsList("bench");
}

// ==============================================================================
// 3. Shop & Units Management
// ==============================================================================

function initShopSlots() {
  document.getElementById("btn-clear-shop").onclick = () => {
    state.shop = [null, null, null, null, null];
    renderShopSlots();
  };
}

function renderShopSlots() {
  const container = document.getElementById("shop-slots-container");
  container.innerHTML = "";
  
  for (let i = 0; i < 5; i++) {
    const champName = state.shop[i];
    const champMeta = champName ? getChampionMeta(champName) : null;
    const slotCard = document.createElement("div");
    slotCard.className = `shop-slot-card ${champName ? '' : 'empty'}`;
    
    if (champName && champMeta) {
      slotCard.innerHTML = `
        <span class="slot-index">SLOT ${i+1}</span>
        <span class="champ-name">${champMeta.name}</span>
        <span class="cost-badge cost-${champMeta.cost}">${champMeta.cost}G</span>
      `;
    } else {
      slotCard.innerHTML = `
        <span class="slot-index">SLOT ${i+1}</span>
        <span class="champ-name">[EMPTY]</span>
        <span class="cost-badge">-</span>
      `;
    }

    slotCard.onclick = () => {
      state.pickerTarget = { type: "shop", index: i };
      openChampionPicker();
    };

    container.appendChild(slotCard);
  }
}

function renderUnitsList(type) {
  const isBoard = type === "board";
  const units = isBoard ? state.boardUnits : state.benchUnits;
  const container = document.getElementById(isBoard ? "board-units-list" : "bench-units-list");
  const countSpan = document.getElementById(isBoard ? "board-count" : "bench-count");
  
  countSpan.textContent = units.length;
  container.innerHTML = "";

  if (units.length === 0) {
    container.innerHTML = `<div class="empty-units-notice">${isBoard ? 'No units on board. Click [+ Add Board Unit]' : 'Bench empty'}</div>`;
    return;
  }

  units.forEach((u, idx) => {
    const meta = getChampionMeta(u.champion);
    const row = document.createElement("div");
    row.className = "unit-row-card";
    row.innerHTML = `
      <div class="unit-info-left">
        <span class="cost-badge cost-${meta.cost}">${meta.cost}G</span>
        <span class="unit-champ-title">${meta.name}</span>
        <div class="unit-stars-group">
          <button class="star-btn ${u.star_level === 1 ? 'active' : ''}" onclick="setUnitStar('${type}', ${idx}, 1)">1★</button>
          <button class="star-btn ${u.star_level === 2 ? 'active' : ''}" onclick="setUnitStar('${type}', ${idx}, 2)">2★</button>
          <button class="star-btn ${u.star_level === 3 ? 'active' : ''}" onclick="setUnitStar('${type}', ${idx}, 3)">3★</button>
        </div>
      </div>
      <div class="unit-info-right">
        <button class="btn btn-xs btn-ghost" onclick="removeUnit('${type}', ${idx})">✕</button>
      </div>
    `;
    container.appendChild(row);
  });
}

window.setUnitStar = (type, idx, star) => {
  const list = type === "board" ? state.boardUnits : state.benchUnits;
  if (list[idx]) {
    list[idx].star_level = star;
    renderUnitsList(type);
  }
};

window.removeUnit = (type, idx) => {
  const list = type === "board" ? state.boardUnits : state.benchUnits;
  list.splice(idx, 1);
  renderUnitsList(type);
};

function getChampionMeta(name) {
  if (!name) return { name: "Unknown", cost: 1 };
  const found = state.champions.find(c => c.name.toLowerCase() === name.toLowerCase());
  return found || { name: name, cost: 1 };
}

// ==============================================================================
// 4. Champion Picker Modal
// ==============================================================================

function initModals() {
  document.getElementById("btn-add-board-unit").onclick = () => {
    state.pickerTarget = { type: "board", index: state.boardUnits.length };
    openChampionPicker();
  };
  document.getElementById("btn-add-bench-unit").onclick = () => {
    state.pickerTarget = { type: "bench", index: state.benchUnits.length };
    openChampionPicker();
  };
  document.getElementById("btn-close-champ-picker").onclick = closeChampionPicker;
  
  // Cost filters
  document.querySelectorAll(".cost-pill").forEach(btn => {
    btn.onclick = (e) => {
      document.querySelectorAll(".cost-pill").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      renderChampionPickerGrid(btn.dataset.cost);
    };
  });

  // Search input
  document.getElementById("champ-search-input").oninput = (e) => {
    renderChampionPickerGrid(null, e.target.value.trim().toLowerCase());
  };

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

function openChampionPicker() {
  document.getElementById("champ-search-input").value = "";
  renderChampionPickerGrid();
  document.getElementById("champ-picker-modal").classList.remove("hidden");
  document.getElementById("champ-search-input").focus();
}

function closeChampionPicker() {
  document.getElementById("champ-picker-modal").classList.add("hidden");
}

function renderChampionPickerGrid(costFilter = "all", query = "") {
  const container = document.getElementById("champ-grid-container");
  container.innerHTML = "";

  // Also add [EMPTY] card option for shop
  if (state.pickerTarget && state.pickerTarget.type === "shop") {
    const emptyCard = document.createElement("div");
    emptyCard.className = "champ-pick-card";
    emptyCard.innerHTML = `<span style="font-size:12px; color:#888;">[EMPTY]</span>`;
    emptyCard.onclick = () => selectChampion(null);
    container.appendChild(emptyCard);
  }

  const filtered = state.champions.filter(c => {
    if (costFilter && costFilter !== "all" && String(c.cost) !== costFilter) return false;
    if (query && !c.name.toLowerCase().includes(query)) return false;
    return true;
  });

  filtered.forEach(c => {
    const card = document.createElement("div");
    card.className = "champ-pick-card";
    card.innerHTML = `
      <div style="font-weight:700; font-size:13px;">${c.name}</div>
      <span class="cost-badge cost-${c.cost}">${c.cost}G</span>
    `;
    card.onclick = () => selectChampion(c.name);
    container.appendChild(card);
  });
}

function selectChampion(champName) {
  if (!state.pickerTarget) return;

  if (state.pickerTarget.type === "shop") {
    state.shop[state.pickerTarget.index] = champName;
    renderShopSlots();
  } else if (state.pickerTarget.type === "board") {
    if (champName) {
      const meta = getChampionMeta(champName);
      state.boardUnits.push({ champion: meta.name, cost: meta.cost, star_level: 1, items: [] });
      renderUnitsList("board");
    }
  } else if (state.pickerTarget.type === "bench") {
    if (champName) {
      const meta = getChampionMeta(champName);
      state.benchUnits.push({ champion: meta.name, cost: meta.cost, star_level: 1, items: [] });
      renderUnitsList("bench");
    }
  }

  closeChampionPicker();
}

// ==============================================================================
// 5. Decision Engine Execution & Display
// ==============================================================================

function initActionButtons() {
  document.getElementById("btn-analyze").onclick = analyzeTurn;
  document.getElementById("btn-copy-prev").onclick = copyPreviousTurn;
  document.getElementById("btn-new-turn").onclick = resetTurn;
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

  // Select synchronization
  document.getElementById("select-actual-action").onchange = (e) => state.actualPlayerAction = e.target.value;
  document.getElementById("select-human-pref").onchange = (e) => state.humanPreferredAction = e.target.value;
  document.getElementById("input-turn-notes").oninput = (e) => state.turnNotes = e.target.value;
  
  document.getElementById("btn-save-turn").onclick = saveCurrentTurn;
  document.getElementById("btn-save-session").onclick = saveSessionToBackend;
  document.getElementById("btn-export-dataset").onclick = exportDataset;
}

async function analyzeTurn() {
  hideValidationErrors();
  
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

  // Reasons List
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
    <div style="font-size:12px; display:flex; gap:16px;">
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

  const lastTurn = state.turnsHistory[state.turnsHistory.length - 1];
  state.previousTurnState = JSON.parse(JSON.stringify(lastTurn.state));
  
  // Clone state
  const prev = lastTurn.state;
  state.hp = prev.hp;
  state.gold = prev.gold;
  state.level = prev.level;
  state.xp = prev.xp;
  state.boardUnits = JSON.parse(JSON.stringify(prev.board_units || []));
  state.benchUnits = JSON.parse(JSON.stringify(prev.bench_units || []));
  state.shop = JSON.parse(JSON.stringify(prev.shop_units || [null, null, null, null, null]));

  // Auto-advance stage round
  stepStage(1);
  renderState();
}

function resetTurn() {
  state.boardUnits = [];
  state.benchUnits = [];
  state.shop = [null, null, null, null, null];
  state.humanFeedback = "UNKNOWN";
  state.humanPreferredAction = "UNKNOWN";
  state.actualPlayerAction = "UNKNOWN";
  state.turnNotes = "";
  document.getElementById("input-turn-notes").value = "";
  renderState();
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
    notes: state.turnNotes,
    reviewed_at_iso: new Date().toISOString()
  };

  state.turnsHistory.push(turnRecord);
  state.previousTurnState = JSON.parse(JSON.stringify(turnRecord.state));
  renderTurnHistory();
  
  // Auto-save session to backend
  saveSessionToBackend(false);
}

function renderTurnHistory() {
  const container = document.getElementById("history-timeline");
  document.getElementById("history-count").textContent = state.turnsHistory.length;
  container.innerHTML = "";

  if (state.turnsHistory.length === 0) {
    container.innerHTML = `<div class="empty-history">No turns recorded yet in this session.</div>`;
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

  renderState();
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

async function exportDataset() {
  try {
    const res = await fetch("/api/export/dataset", { method: "POST" });
    const data = await res.json();
    alert(`Dataset exported successfully! (${data.exported_records} records exported to ${data.export_path})`);
  } catch (err) {
    alert(`Failed to export dataset: ${err.message}`);
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
// 6. Keyboard Shortcuts
// ==============================================================================

function initKeyboardShortcuts() {
  document.addEventListener("keydown", (e) => {
    // Avoid shortcuts if typing in search or text inputs
    if (["INPUT", "TEXTAREA"].includes(e.target.tagName)) {
      if (e.key === "Enter" && e.target.id !== "champ-search-input") {
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
      resetTurn();
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
