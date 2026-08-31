/**
 * TFT Decision Assistant Web v1.1 - Frontend Application (Korean Localized)
 * Human Input → Fast Manual State Sync → Frozen DecisionEngine → Action & Direction
 */

// Application Global State
const state = {
  // Current Draft Turn State
  stage: "2-1",
  hp: 100,
  gold: 30,
  level: 4,
  xp: 0,
  streak: 0,
  boardUnits: [], // [{champion, cost, star_level, items: []}]
  benchUnits: [], // [{champion, cost, star_level, items: []}]
  shop: [null, null, null, null, null], // [champName | null]
  
  // Placement Target: 'board' | 'bench' | 'shop'
  activeTarget: "board",
  activeShopSlot: 0,

  // Reference Catalogs
  champions: [], // Set 18 Champions (64 normalized)
  costFilter: "all",
  searchQuery: "",
  recentChampions: [],

  // Undo History Stack for Draft Turn
  undoStack: [],

  // Decision & Blind Mode State
  isBlindMode: false,
  blindRevealed: false,
  currentDecision: null,
  previousDecision: null,
  previousTurnState: null,

  // Feedback & Notes
  actualPlayerAction: "UNKNOWN",
  humanPreferredAction: "UNKNOWN",
  humanFeedback: "UNKNOWN",
  turnNotes: "",

  // Video Replay Sync
  videoTimestampSec: null,

  // Session History
  sessionId: "SESSION_LIVE_001",
  turnsHistory: []
};

// Korean Reason Code Mapping
const REASON_MAP_KO = {
  "LOW_HP_PRESSURE": "위험 체력 압박: 생존을 위해 즉시 리롤하여 보드 파워를 올려야 합니다.",
  "HIGH_GOLD_ROLL_SURPLUS": "골드 잉여 이자: 50G 초과 이자 골드로 상점을 리롤하여 2성/3성 업그레이드를 탐색합니다.",
  "PRESERVE_COMPOUND_INTEREST": "복리 이자 극대화: 현재 골드를 유지하여 라운드당 최대 이자(+5G)를 획득하고 경제력을 비축합니다.",
  "LEVEL_UP_BREAKPOINT": "레벨업 타이밍: 즉시 레벨업하여 필드에 기물을 1개 더 추가하고 고코스트 유닛 확률을 높입니다.",
  "PAIR_UPGRADE_POTENTIAL": "페어 완성 기회: 상점 또는 대기석에 2성 완성이 임박한 페어 기물이 존재합니다.",
  "STABLE_BOARD_POWER": "안정적인 필드 전력: 현재 보드가 충분히 강력하므로 불필요한 골드 소모 없이 경제력을 비축합니다.",
  "FAST_LEVEL_OPPORTUNITY": "패스트 레벨업 기회: 높은 체력과 경제력을 바탕으로 상위 레벨로 빠르게 전환합니다.",
  "LOSS_STREAK_ECONOMY": "연패 이자 관리: 연패 보너스를 유지하며 50G 복리를 쌓습니다.",
  "WIN_STREAK_MOMENTUM": "연승 유지: 필드 전력을 유지하여 연승 보너스를 이어갑니다."
};

const ACTION_MAP_KO = {
  "ROLL": "상점 리롤 (ROLL)",
  "SAVE_GOLD": "골드 세이브 (SAVE_GOLD)",
  "LEVEL_UP": "레벨업 (LEVEL_UP)",
  "BUY_UNIT": "기물 구매 (BUY_UNIT)",
  "UNKNOWN": "미정 (UNKNOWN)"
};

// ==============================================================================
// 1. Initialization & Event Binding
// ==============================================================================

document.addEventListener("DOMContentLoaded", async () => {
  await loadChampionRoster();
  await loadVideoList();
  initTopBarSync();
  initSteppers();
  initTargetSelector();
  initFiltersAndSearch();
  initDecisionAndActions();
  initVideoModal();
  initShortcuts();

  renderAll();
});

async function loadChampionRoster() {
  try {
    const res = await fetch("/api/data/champions");
    state.champions = await res.json();
    renderChampionPoolGrid();
  } catch (err) {
    console.error("Failed to load champion roster:", err);
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

  // HP Steppers
  document.getElementById("btn-hp-m10").onclick = () => adjustNumInput("input-hp", -10, 0, 100);
  document.getElementById("btn-hp-m1").onclick = () => adjustNumInput("input-hp", -1, 0, 100);
  document.getElementById("btn-hp-p1").onclick = () => adjustNumInput("input-hp", 1, 0, 100);
  document.getElementById("btn-hp-p10").onclick = () => adjustNumInput("input-hp", 10, 0, 100);

  // Gold Steppers
  document.getElementById("btn-gold-m10").onclick = () => adjustNumInput("input-gold", -10, 0, 250);
  document.getElementById("btn-gold-m5").onclick = () => adjustNumInput("input-gold", -5, 0, 250);
  document.getElementById("btn-gold-p5").onclick = () => adjustNumInput("input-gold", 5, 0, 250);
  document.getElementById("btn-gold-p10").onclick = () => adjustNumInput("input-gold", 10, 0, 250);

  // Level & XP Steppers
  document.getElementById("btn-lvl-m1").onclick = () => adjustNumInput("input-level", -1, 1, 11);
  document.getElementById("btn-lvl-p1").onclick = () => adjustNumInput("input-level", 1, 1, 11);
  document.getElementById("btn-xp-p4").onclick = () => adjustNumInput("input-xp", 4, 0, 200);

  // Quick Action Buttons
  document.getElementById("btn-undo-draft").onclick = performUndo;
  document.getElementById("btn-copy-prev").onclick = copyPreviousTurn;
  document.getElementById("btn-new-turn").onclick = resetCurrentTurn;
}

function adjustNumInput(id, delta, min, max) {
  pushUndoState();
  const input = document.getElementById(id);
  let val = (parseInt(input.value) || 0) + delta;
  val = Math.min(max, Math.max(min, val));
  input.value = val;
  input.dispatchEvent(new Event("input"));
}

function stepStage(delta) {
  pushUndoState();
  const parts = state.stage.split("-");
  let s = parseInt(parts[0]) || 2;
  let r = parseInt(parts[1]) || 1;

  r += delta;
  if (r > 7) {
    s += 1;
    r = 1;
  } else if (r < 1) {
    if (s > 1) {
      s -= 1;
      r = 7;
    } else {
      r = 1;
    }
  }
  state.stage = `${s}-${r}`;
  document.getElementById("input-stage").value = state.stage;
  syncTopStatusBar();
}

function initTargetSelector() {
  const tabs = document.querySelectorAll(".target-tab");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      state.activeTarget = tab.dataset.target;
      updateTargetIndicator();
    });
  });

  document.getElementById("btn-select-target-board").onclick = () => setTarget("board");
  document.getElementById("btn-select-target-bench").onclick = () => setTarget("bench");
  document.getElementById("btn-clear-shop").onclick = () => {
    pushUndoState();
    state.shop = [null, null, null, null, null];
    renderShopSlots();
  };
}

function setTarget(target) {
  state.activeTarget = target;
  document.querySelectorAll(".target-tab").forEach(t => {
    t.classList.toggle("active", t.dataset.target === target);
  });
  updateTargetIndicator();
}

function updateTargetIndicator() {
  const badge = document.getElementById("active-target-badge");
  const target = state.activeTarget;
  if (target === "board") badge.textContent = "추가 대상: 필드(보드)";
  else if (target === "bench") badge.textContent = "추가 대상: 대기석(벤치)";
  else if (target === "shop") badge.textContent = `추가 대상: 상점 (슬롯 ${state.activeShopSlot + 1})`;

  renderShopSlots();
}

// ==============================================================================
// 4. Champion Pool & 1-Click Fast Add
// ==============================================================================

function renderChampionPoolGrid() {
  const container = document.getElementById("champion-pool-grid");
  container.innerHTML = "";

  const q = state.searchQuery.toLowerCase();
  const filtered = state.champions.filter(c => {
    if (state.costFilter !== "all" && String(c.cost) !== state.costFilter) return false;
    if (q) {
      const matchEng = c.name.toLowerCase().includes(q);
      const matchKo = c.name_ko && c.name_ko.toLowerCase().includes(q);
      if (!matchEng && !matchKo) return false;
    }
    return true;
  });

  filtered.forEach(c => {
    const card = document.createElement("div");
    card.className = "champ-card-mini";
    
    const imgSrc = c.splash_art ? `/img/champion/${c.splash_art}` : "";
    const imgHtml = imgSrc ? `<img src="${imgSrc}" alt="${c.name_ko || c.name}" onerror="this.style.display='none'">` : '';
    const displayName = c.name_ko || c.name;

    card.innerHTML = `
      ${imgHtml}
      <span class="c-name" title="${c.name_ko || c.name} (${c.name})">${displayName}</span>
      <span class="cost-tag c${c.cost}">${c.cost}G</span>
    `;

    card.onclick = () => onChampionPoolClick(c.name);
    container.appendChild(card);
  });
}

function getChampionDisplayName(name) {
  if (!name) return "";
  const found = state.champions.find(c => c.name.toLowerCase() === name.toLowerCase());
  return found?.name_ko || name;
}

function onChampionPoolClick(champName) {
  pushUndoState();
  const meta = getChampionMeta(champName);
  const displayName = meta.name_ko || meta.name;
  
  // Track Recent Champions
  if (!state.recentChampions.includes(displayName)) {
    state.recentChampions.unshift(displayName);
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
    state.activeShopSlot = (state.activeShopSlot + 1) % 5;
    document.getElementById("active-target-badge").textContent = `추가 대상: 상점 (슬롯 ${state.activeShopSlot + 1})`;
    renderShopSlots();
  }

  syncTopStatusBar();
}

function renderRecentChampions() {
  const container = document.getElementById("recent-chips-list");
  if (state.recentChampions.length === 0) {
    container.innerHTML = `<span class="no-recents">선택 기록 없음</span>`;
    return;
  }
  container.innerHTML = "";
  state.recentChampions.forEach(dispName => {
    const chip = document.createElement("span");
    chip.className = "recent-chip";
    chip.textContent = dispName;
    chip.onclick = () => onChampionPoolClick(dispName);
    container.appendChild(chip);
  });
}

function getChampionMeta(name) {
  if (!name) return { name: "Unknown", name_ko: "미정", cost: 1 };
  const found = state.champions.find(c => 
    c.name.toLowerCase() === name.toLowerCase() || 
    (c.name_ko && c.name_ko.toLowerCase() === name.toLowerCase())
  );
  return found || { name: name, name_ko: name, cost: 1 };
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
    container.innerHTML = `<span class="empty-hint">좌측 도감에서 챔피언을 클릭하면 필드에 즉시 배치됩니다</span>`;
    return;
  }

  state.boardUnits.forEach((u, idx) => {
    const chip = document.createElement("div");
    chip.className = "unit-chip-item";
    const displayName = getChampionDisplayName(u.champion);
    chip.innerHTML = `
      <span class="cost-tag c${u.cost}">${u.cost}G</span>
      <span class="u-name">${displayName}</span>
      <div class="unit-stars-toggle">
        <span class="star-tag ${u.star_level === 1 ? 'active' : ''}" onclick="toggleStar('board', ${idx}, 1)">1★</span>
        <span class="star-tag ${u.star_level === 2 ? 'active' : ''}" onclick="toggleStar('board', ${idx}, 2)">2★</span>
        <span class="star-tag ${u.star_level === 3 ? 'active' : ''}" onclick="toggleStar('board', ${idx}, 3)">3★</span>
      </div>
      <button class="btn-del-unit" onclick="removeUnitItem('board', ${idx})" title="기물 삭제">✕</button>
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
    container.innerHTML = `<span class="empty-hint">대기석이 비어 있습니다</span>`;
    return;
  }

  state.benchUnits.forEach((u, idx) => {
    const chip = document.createElement("div");
    chip.className = "unit-chip-item";
    const displayName = getChampionDisplayName(u.champion);
    chip.innerHTML = `
      <span class="cost-tag c${u.cost}">${u.cost}G</span>
      <span class="u-name">${displayName}</span>
      <div class="unit-stars-toggle">
        <span class="star-tag ${u.star_level === 1 ? 'active' : ''}" onclick="toggleStar('bench', ${idx}, 1)">1★</span>
        <span class="star-tag ${u.star_level === 2 ? 'active' : ''}" onclick="toggleStar('bench', ${idx}, 2)">2★</span>
        <span class="star-tag ${u.star_level === 3 ? 'active' : ''}" onclick="toggleStar('bench', ${idx}, 3)">3★</span>
      </div>
      <button class="btn-del-unit" onclick="removeUnitItem('bench', ${idx})" title="기물 삭제">✕</button>
    `;
    container.appendChild(chip);
  });
}

function renderShopSlots() {
  const container = document.getElementById("shop-slots-container");
  container.innerHTML = "";

  for (let i = 0; i < 5; i++) {
    const champ = state.shop[i];
    const isTargetSlot = state.activeTarget === "shop" && state.activeShopSlot === i;
    const slotBtn = document.createElement("div");
    slotBtn.className = `shop-slot-btn ${champ ? 'filled' : 'empty'} ${isTargetSlot ? 'active-slot' : ''}`;

    if (champ) {
      const meta = getChampionMeta(champ);
      const displayName = meta.name_ko || meta.name;
      slotBtn.innerHTML = `
        <span class="cost-tag c${meta.cost}">${meta.cost}G</span>
        <span class="slot-name">${displayName}</span>
        <button class="btn-clear-slot" onclick="event.stopPropagation(); clearShopSlot(${i});">✕</button>
      `;
    } else {
      slotBtn.innerHTML = `
        <span class="slot-num">슬롯 ${i + 1}</span>
        <span class="slot-empty-label">비어있음</span>
      `;
    }

    slotBtn.onclick = () => {
      setTarget("shop");
      state.activeShopSlot = i;
      updateTargetIndicator();
    };

    container.appendChild(slotBtn);
  }
}

function toggleStar(target, index, star) {
  pushUndoState();
  const list = target === "board" ? state.boardUnits : state.benchUnits;
  if (list[index]) {
    list[index].star_level = star;
    if (target === "board") renderBoardUnits();
    else renderBenchUnits();
  }
}

function removeUnitItem(target, index) {
  pushUndoState();
  if (target === "board") {
    state.boardUnits.splice(index, 1);
    renderBoardUnits();
  } else {
    state.benchUnits.splice(index, 1);
    renderBenchUnits();
  }
  syncTopStatusBar();
}

function clearShopSlot(slotIdx) {
  pushUndoState();
  state.shop[slotIdx] = null;
  renderShopSlots();
}

// ==============================================================================
// 6. Filter & Search Handlers
// ==============================================================================

function initFiltersAndSearch() {
  const pills = document.querySelectorAll(".filter-pill");
  pills.forEach(pill => {
    pill.addEventListener("click", () => {
      pills.forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      state.costFilter = pill.dataset.cost;
      renderChampionPoolGrid();
    });
  });

  const searchInput = document.getElementById("champ-quick-search");
  searchInput.addEventListener("input", (e) => {
    state.searchQuery = e.target.value.trim().toLowerCase();
    renderChampionPoolGrid();
  });
}

// ==============================================================================
// 7. DecisionEngine Analysis & Blind Review
// ==============================================================================

function initDecisionAndActions() {
  document.getElementById("btn-analyze").onclick = analyzeTurn;
  document.getElementById("btn-toggle-blind").onclick = toggleBlindMode;
  document.getElementById("btn-reveal-engine").onclick = revealBlindDecision;

  // Blind preference buttons
  document.querySelectorAll(".btn-pref").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".btn-pref").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.humanPreferredAction = btn.dataset.pref;
      document.getElementById("select-human-pref").value = btn.dataset.pref;
    });
  });

  // Human Feedback buttons
  document.querySelectorAll(".btn-fb").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".btn-fb").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      state.humanFeedback = btn.dataset.fb;
    });
  });

  // Select sync
  document.getElementById("select-actual-action").onchange = (e) => state.actualPlayerAction = e.target.value;
  document.getElementById("select-human-pref").onchange = (e) => state.humanPreferredAction = e.target.value;
  document.getElementById("input-turn-notes").oninput = (e) => state.turnNotes = e.target.value;

  document.getElementById("btn-save-turn").onclick = saveCurrentTurn;
  document.getElementById("btn-save-session").onclick = saveSessionToBackend;
  document.getElementById("btn-clear-history").onclick = clearTurnHistory;
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
      showValidationErrors(err.detail?.errors || [err.detail || "입력값 검증 오류가 발생했습니다."]);
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
    showValidationErrors([`네트워크/서버 오류: ${err.message}`]);
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

  const koreanActName = ACTION_MAP_KO[act] || act;
  document.getElementById("rec-action-name").textContent = koreanActName;
  document.getElementById("rec-gap-badge").textContent = `점수 격차: +${decision.action_score_gap.toFixed(4)}`;
  document.getElementById("rec-score-val").textContent = decision.score.toFixed(4);
  document.getElementById("rec-conf-val").textContent = decision.confidence.toFixed(2);
  document.getElementById("rec-engine-tag").textContent = decision.calibration.applied ? `보정 적용됨 (${decision.calibration.mode})` : `프로덕션 동결 코어 엔진`;

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
    const koDesc = REASON_MAP_KO[r.code] || r.summary;
    item.textContent = `[${r.code}] ${koDesc} (기여도: ${r.impact.toFixed(3)})`;
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
    const koActionLabel = ACTION_MAP_KO[asc.action] || asc.action;

    tr.innerHTML = `
      <td><strong>${koActionLabel}</strong></td>
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
    <div style="font-size:12px; display:flex; gap:16px; font-weight:500;">
      <span>체력(HP): <strong>${prev.hp} → ${curr.hp} (${hpDiff >= 0 ? '+' : ''}${hpDiff})</strong></span>
      <span>골드(G): <strong>${prev.gold} → ${curr.gold} (${goldDiff >= 0 ? '+' : ''}${goldDiff})</strong></span>
      <span>레벨: <strong>${prev.level} → ${curr.level} (${lvlDiff >= 0 ? '+' : ''}${lvlDiff})</strong></span>
    </div>
  `;
}

function copyPreviousTurn() {
  if (state.turnsHistory.length === 0) {
    alert("이 세션에 복사할 직전 턴 기록이 없습니다.");
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
    btn.innerHTML = `🔒 블라인드 켜짐 <span class="kbd-hint">[B]</span>`;
  } else {
    btn.innerHTML = `👁️ 블라인드 모드 <span class="kbd-hint">[B]</span>`;
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

// ==============================================================================
// 8. Session Persistence & Checkpoint History
// ==============================================================================

async function saveCurrentTurn() {
  if (!state.currentDecision) {
    alert("턴 저장을 위해 먼저 [🚀 턴 의사결정 분석]을 실행해 주세요.");
    return;
  }

  const turnRecord = {
    turn_index: state.turnsHistory.length,
    timestamp: Date.now(),
    state: {
      stage_round: state.stage,
      hp: state.hp,
      gold: state.gold,
      level: state.level,
      xp: state.xp,
      board_units: JSON.parse(JSON.stringify(state.boardUnits)),
      bench_units: JSON.parse(JSON.stringify(state.benchUnits)),
      shop_units: JSON.parse(JSON.stringify(state.shop)),
      video_timestamp_sec: state.videoTimestampSec
    },
    decision: state.currentDecision,
    actual_player_action: state.actualPlayerAction,
    human_preferred_action: state.humanPreferredAction,
    human_feedback: state.humanFeedback,
    human_judgment: state.humanFeedback,
    notes: state.turnNotes
  };

  state.turnsHistory.push(turnRecord);
  state.previousTurnState = JSON.parse(JSON.stringify(turnRecord.state));
  renderTurnHistoryList();

  // Save to Backend Session
  try {
    const sId = document.getElementById("session-id-input").value.trim() || state.sessionId;
    await fetch(`/api/sessions/${sId}/turns`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(turnRecord)
    });
  } catch (err) {
    console.error("Failed to persist turn to backend:", err);
  }
}

function renderTurnHistoryList() {
  const container = document.getElementById("history-timeline");
  const countSpan = document.getElementById("history-count");
  countSpan.textContent = state.turnsHistory.length;

  if (state.turnsHistory.length === 0) {
    container.innerHTML = `<div class="empty-history">아직 저장된 턴 기록이 없습니다.</div>`;
    return;
  }

  container.innerHTML = "";
  state.turnsHistory.slice().reverse().forEach((t, revIdx) => {
    const item = document.createElement("div");
    item.className = "history-item";
    const st = t.state;
    const dec = t.decision;
    const koRec = ACTION_MAP_KO[dec.recommended_action] || dec.recommended_action;

    item.innerHTML = `
      <div class="hist-header">
        <span class="hist-stage">스테이지 ${st.stage_round}</span>
        <span class="hist-hp">HP ${st.hp} | ${st.gold}G</span>
        <span class="hist-rec ${dec.recommended_action.toLowerCase()}">${koRec}</span>
      </div>
      <div class="hist-sub">
        <span>실제 행동: ${ACTION_MAP_KO[t.actual_player_action] || t.actual_player_action}</span>
        <span>선호: ${ACTION_MAP_KO[t.human_preferred_action] || t.human_preferred_action}</span>
        <span>평가: ${t.human_feedback}</span>
      </div>
    `;
    container.appendChild(item);
  });
}

function clearTurnHistory() {
  if (confirm("현재 세션의 모든 턴 기록을 초기화하시겠습니까?")) {
    state.turnsHistory = [];
    renderTurnHistoryList();
  }
}

async function saveSessionToBackend() {
  const sId = document.getElementById("session-id-input").value.trim() || state.sessionId;
  alert(`세션 '${sId}'이(가) 저장되었습니다.`);
}

// ==============================================================================
// 9. Undo Stack Management
// ==============================================================================

function pushUndoState() {
  const snap = {
    stage: state.stage,
    hp: state.hp,
    gold: state.gold,
    level: state.level,
    xp: state.xp,
    boardUnits: JSON.parse(JSON.stringify(state.boardUnits)),
    benchUnits: JSON.parse(JSON.stringify(state.benchUnits)),
    shop: JSON.parse(JSON.stringify(state.shop))
  };
  state.undoStack.push(snap);
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

  document.getElementById("input-stage").value = state.stage;
  document.getElementById("input-hp").value = state.hp;
  document.getElementById("input-gold").value = state.gold;
  document.getElementById("input-level").value = state.level;
  document.getElementById("input-xp").value = state.xp;

  renderAll();
}

// ==============================================================================
// 10. Video Assistant Modal
// ==============================================================================

function initVideoModal() {
  const modal = document.getElementById("video-assistant-modal");
  const btnToggle = document.getElementById("btn-toggle-video");
  const btnClose = document.getElementById("btn-close-video-modal");
  const btnLoad = document.getElementById("btn-load-video");
  const video = document.getElementById("replay-video");

  btnToggle.onclick = () => modal.classList.remove("hidden");
  btnClose.onclick = () => modal.classList.add("hidden");

  btnLoad.onclick = () => {
    const fn = document.getElementById("video-select").value;
    if (fn) {
      video.src = `/api/videos/${fn}/stream`;
      video.play();
    }
  };

  video.ontimeupdate = () => {
    const sec = video.currentTime;
    state.videoTimestampSec = sec;
    document.getElementById("video-time-sec").textContent = sec.toFixed(1);
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    const ms = Math.floor((sec % 1) * 100);
    document.getElementById("video-time-str").textContent = 
      `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${String(ms).padStart(2, '0')}`;
  };

  document.getElementById("btn-seek-m10").onclick = () => video.currentTime = Math.max(0, video.currentTime - 10);
  document.getElementById("btn-seek-m5").onclick = () => video.currentTime = Math.max(0, video.currentTime - 5);
  document.getElementById("btn-seek-p5").onclick = () => video.currentTime = video.currentTime + 5;
  document.getElementById("btn-seek-p10").onclick = () => video.currentTime = video.currentTime + 10;
  document.getElementById("video-speed-select").onchange = (e) => video.playbackRate = parseFloat(e.target.value);

  document.getElementById("btn-capture-checkpoint").onclick = () => {
    modal.classList.add("hidden");
    alert(`영상 타임스탬프 (${state.videoTimestampSec.toFixed(1)}초)가 현재 턴에 연결되었습니다.`);
  };
}

// ==============================================================================
// 11. Keyboard Shortcuts
// ==============================================================================

function initShortcuts() {
  const modal = document.getElementById("shortcuts-modal");
  document.getElementById("btn-shortcuts-modal").onclick = () => modal.classList.remove("hidden");
  document.getElementById("btn-close-shortcuts").onclick = () => modal.classList.add("hidden");

  window.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") {
      if (e.key === "Enter" && e.ctrlKey) {
        saveCurrentTurn();
      }
      return;
    }

    if (e.key === "Enter") {
      e.preventDefault();
      analyzeTurn();
    } else if (e.key === "s" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      saveCurrentTurn();
    } else if (e.key === "z" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      performUndo();
    } else if (e.key === "p" || e.key === "P") {
      e.preventDefault();
      copyPreviousTurn();
    } else if (e.key === "n" || e.key === "N") {
      e.preventDefault();
      resetCurrentTurn();
    } else if (e.key === "b" || e.key === "B") {
      e.preventDefault();
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

// ==============================================================================
// 12. Helper UI Rendering
// ==============================================================================

function renderAll() {
  syncTopStatusBar();
  renderBoardUnits();
  renderBenchUnits();
  renderShopSlots();
  renderRecentChampions();
}

function showValidationErrors(errs) {
  const box = document.getElementById("validation-error-box");
  const list = document.getElementById("validation-errors-list");
  list.innerHTML = "";
  errs.forEach(e => {
    const li = document.createElement("li");
    li.textContent = e;
    list.appendChild(li);
  });
  box.classList.remove("hidden");
}

function hideValidationErrors() {
  document.getElementById("validation-error-box").classList.add("hidden");
}
