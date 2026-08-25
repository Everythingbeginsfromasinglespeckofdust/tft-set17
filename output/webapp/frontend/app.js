// TFT Set 17 Frontend Application Logic
let CHAMPIONS = [];
let ITEMS = { basic_components: [], completed_items: [] };
let SCENARIOS = [];
let CURRENT_STRATEGIES = [];

document.addEventListener('DOMContentLoaded', async () => {
  await loadReferenceData();
  // 기본 1개 유닛 행 추가
  addUnitRow();
});

async function loadReferenceData() {
  try {
    const [champRes, itemRes, scenRes] = await Promise.all([
      fetch('/api/champions'),
      fetch('/api/items'),
      fetch('/api/scenarios')
    ]);
    CHAMPIONS = await champRes.json();
    ITEMS = await itemRes.json();
    SCENARIOS = await scenRes.json();
  } catch (err) {
    console.error('Failed to load reference data:', err);
  }
}

function updateUnitCount() {
  const container = document.getElementById('units-container');
  document.getElementById('unit-count').innerText = container.children.length;
}

function addUnitRow(unitData = null) {
  const container = document.getElementById('units-container');
  const row = document.createElement('div');
  row.className = 'unit-row';

  // 1. 챔피언 선택
  const champSelect = document.createElement('select');
  champSelect.className = 'select-champion';
  champSelect.innerHTML = `<option value="">-- 챔피언 선택 --</option>` +
    CHAMPIONS.map(c => `<option value="${c.name}" data-cost="${c.cost}">${c.name} (${c.cost}코)</option>`).join('');

  if (unitData && unitData.champion) {
    champSelect.value = unitData.champion;
  }

  // 2. 성급 선택
  const starSelect = document.createElement('select');
  starSelect.className = 'select-star';
  starSelect.innerHTML = `
    <option value="1">1★</option>
    <option value="2">2★</option>
    <option value="3">3★</option>
  `;
  if (unitData && unitData.star_level) {
    starSelect.value = String(unitData.star_level);
  }

  // 3. 아이템 선택 (3개)
  const allItems = [
    { cat: '미완성 부품', items: ITEMS.basic_components || [] },
    { cat: '완성/특수 아이템', items: ITEMS.completed_items || [] }
  ];

  const itemOptionsHtml = `<option value="">(아이템 없음)</option>` +
    allItems.map(group => `
      <optgroup label="${group.cat}">
        ${group.items.map(it => `<option value="${it}">${it}</option>`).join('')}
      </optgroup>
    `).join('');

  const itemSelects = [1, 2, 3].map((num, idx) => {
    const itSelect = document.createElement('select');
    itSelect.className = `select-item select-item-${num}`;
    itSelect.innerHTML = itemOptionsHtml;
    if (unitData && unitData.items && unitData.items[idx]) {
      itSelect.value = unitData.items[idx];
    }
    return itSelect;
  });

  // 4. 삭제 버튼
  const removeBtn = document.createElement('button');
  removeBtn.type = 'button';
  removeBtn.className = 'btn-remove';
  removeBtn.innerHTML = '✕';
  removeBtn.onclick = () => {
    row.remove();
    updateUnitCount();
  };

  row.appendChild(champSelect);
  row.appendChild(starSelect);
  itemSelects.forEach(s => row.appendChild(s));
  row.appendChild(removeBtn);

  container.appendChild(row);
  updateUnitCount();
}

function loadScenario(index) {
  if (!SCENARIOS[index]) return;
  const s = SCENARIOS[index];

  document.getElementById('stage-input').value = s.stage_round || '1-1';
  document.getElementById('level-input').value = s.level || 4;
  document.getElementById('xp-input').value = s.xp || 0;
  document.getElementById('gold-input').value = s.gold || 0;

  CURRENT_STRATEGIES = s.strategies || [];

  const container = document.getElementById('units-container');
  container.innerHTML = '';

  const units = (s.board && s.board.units) || [];
  units.forEach(u => addUnitRow(u));

  submitReport();
}

function getFormState() {
  const stage = document.getElementById('stage-input').value.trim() || '1-1';
  const level = parseInt(document.getElementById('level-input').value, 10) || 1;
  const xp = parseInt(document.getElementById('xp-input').value, 10) || 0;
  const gold = parseInt(document.getElementById('gold-input').value, 10) || 0;

  const unitRows = document.querySelectorAll('.unit-row');
  const units = [];

  unitRows.forEach(row => {
    const champSelect = row.querySelector('.select-champion');
    const cname = champSelect.value;
    if (!cname) return;

    const champObj = CHAMPIONS.find(c => c.name === cname);
    const cost = champObj ? champObj.cost : 1;
    const starLevel = parseInt(row.querySelector('.select-star').value, 10) || 1;

    const items = [];
    row.querySelectorAll('.select-item').forEach(s => {
      if (s.value) items.push(s.value);
    });

    units.push({
      champion: cname,
      cost: cost,
      star_level: starLevel,
      items: items
    });
  });

  return {
    stage_round: stage,
    level: level,
    xp: xp,
    gold: gold,
    board: { units: units },
    strategies: CURRENT_STRATEGIES,
    num_turns: 3
  };
}

async function submitReport() {
  const state = getFormState();
  const btn = document.getElementById('btn-submit');
  btn.disabled = true;
  btn.innerText = '⏳ 리포트 계산 중...';

  try {
    const res = await fetch('/api/report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(state)
    });

    if (!res.ok) {
      const errData = await res.json();
      alert(`오류: ${errData.detail || '리포트 생성 실패'}`);
      return;
    }

    const data = await res.json();
    renderReport(data);
  } catch (err) {
    alert(`네트워크 오류: ${err.message}`);
  } finally {
    btn.disabled = false;
    btn.innerText = '🚀 종합 리포트 생성 및 분석';
  }
}

function renderReport(data) {
  document.getElementById('report-empty').classList.add('hidden');
  const content = document.getElementById('report-content');
  content.classList.remove('hidden');

  // 1. 상태
  const s = data.state;
  document.getElementById('res-stage-badge').innerText = `Stage ${s.stage_round}`;
  document.getElementById('res-level').innerText = `${s.level} Lv`;
  document.getElementById('res-xp').innerText = `${s.xp} XP`;
  document.getElementById('res-gold').innerText = `${s.gold} G`;
  document.getElementById('res-units-count').innerText = `${s.units_count} 명`;

  // 2. 보드 파워
  const bp = data.board_power;
  const bk = bp.breakdown;
  document.getElementById('res-total-power').innerText = bp.total_power.toFixed(2);
  document.getElementById('res-unit-power').innerText = `${bk.unit_power.toFixed(2)}점`;
  document.getElementById('res-item-score').innerText = `${bk.item_score.toFixed(2)}점`;
  document.getElementById('res-synergy-bonus').innerText = `${bk.synergy_bonus.toFixed(2)}점`;

  const synContainer = document.getElementById('res-synergies-list');
  synContainer.innerHTML = '';
  if (bk.active_synergies && bk.active_synergies.length > 0) {
    bk.active_synergies.forEach(syn => {
      const tag = document.createElement('span');
      tag.className = 'synergy-tag';
      tag.innerText = `${syn.trait} (${syn.unit_count}명/단계${syn.breakpoint_reached}: +${syn.bonus.toFixed(1)}점)`;
      synContainer.appendChild(tag);
    });
  } else {
    synContainer.innerHTML = '<span style="color: var(--text-muted); font-size: 0.85rem;">활성 시너지 없음</span>';
  }

  // 3. 경제
  const eco = data.economy;
  document.getElementById('res-interest').innerText = `+${eco.next_turn_interest} G`;
  if (eco.next_level > s.level) {
    document.getElementById('res-next-level-label').innerText = `${eco.next_level}레벨 도달 필요 골드`;
    document.getElementById('res-gold-needed').innerText = `${eco.gold_to_next_level} G`;
    const statusBadge = document.getElementById('res-level-status');
    if (s.gold >= eco.gold_to_next_level) {
      statusBadge.innerText = '도달 가능';
      statusBadge.className = 'badge badge-success';
    } else {
      statusBadge.innerText = '골드 부족';
      statusBadge.className = 'badge badge-warning';
    }
  } else {
    document.getElementById('res-next-level-label').innerText = `최고 레벨`;
    document.getElementById('res-gold-needed').innerText = `최대 레벨 도달`;
    document.getElementById('res-level-status').className = 'badge badge-success';
    document.getElementById('res-level-status').innerText = '10 Lv 완료';
  }

  // 4. 전략 비교
  const stratCard = document.getElementById('strat-card');
  const stratList = data.strategies_comparison;
  const tbody = document.getElementById('strat-table-body');
  tbody.innerHTML = '';

  if (stratList && stratList.length > 0) {
    stratCard.classList.remove('hidden');
    document.getElementById('res-turns').innerText = data.num_turns || 3;
    stratList.forEach(st => {
      const sInfo = st.strategy;
      const name = sInfo.name || sInfo.type;
      let hitStr = '-';
      if (st.target_hit_prob_cumulative !== null && st.target_hit_prob_cumulative !== undefined) {
        const pVal = (st.target_hit_prob_cumulative * 100).toFixed(1);
        const tChamp = sInfo.target_champion || '기물';
        hitStr = `<strong style="color: var(--accent);">${tChamp}</strong> (${pVal}%)`;
      }

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong>${name}</strong></td>
        <td><span style="color: var(--gold);">${st.final_gold.toFixed(0)} G</span></td>
        <td>${st.final_level} Lv</td>
        <td>${hitStr}</td>
      `;
      tbody.appendChild(tr);
    });
  } else {
    stratCard.classList.add('hidden');
  }

  // 5. 전술적 조언
  document.getElementById('res-tactical-comment').innerText = data.tactical_comment;
}
