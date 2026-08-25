#!/usr/bin/env python3
"""TFT Set 17 (패치 17.9) 시각화 웹 뷰어.

이미지(챔피언/시너지/증강체/아이템 아이콘)가 포함된 인터랙티브 웹 페이지를
생성해 로컬 HTTP 서버로 연다. 이미지는 로컬 `TFT_DDragon/img`만 사용하므로
외부 네트워크가 필요 없다.

사용법
------
    python3 tft_viewer.py             # http://localhost:18080 열림
    python3 tft_viewer.py --port 9000 # 다른 포트
    python3 tft_viewer.py --no-browser

의존성: Python 표준 라이브러리만.
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
DDATA = os.path.join(HERE, "TFT_DDragon", "data", "ko_KR")
IMG = os.path.join(HERE, "TFT_DDragon", "img")
SET = 17
PATCH = "17.9"

TIER_NAME = {1: "실버", 2: "골드", 3: "프리즘"}


# ---------------------------------------------------------------------------
# 데이터 조립
# ---------------------------------------------------------------------------
def _local(fn):
    d = json.load(open(os.path.join(DDATA, fn)))
    return d.get("data", d)


def _img_path(subdir, fname):
    """로컬 이미지 존재 시 브라우저 상대 경로 반환, 없으면 None."""
    if not fname:
        return None
    p = os.path.join(IMG, subdir, fname)
    return f"TFT_DDragon/img/{subdir}/{fname}" if os.path.exists(p) else None


def build_data():
    data = {}

    # --- 챔피언 / 시너지 (tft_view.py 산출물) ---
    champ_file = os.path.join(HERE, "tft_set17.json")
    if not os.path.exists(champ_file):
        sys.exit("tft_set17.json 없음. 먼저 `python3 tft_view.py --md --json` 실행하세요.")
    cs = json.load(open(champ_file))

    traits_raw = _local("trait.json")
    trait_img = {v["id"]: v["image"]["full"] for v in traits_raw.values()}
    trait_name = {v["id"]: v["name"] for v in traits_raw.values()}
    champs_raw = {v["id"]: v for v in _local("champion.json").values()}

    champions = []
    for c in cs["champions"]:
        champions.append({
            "id": c["id"],
            "name": c["name"],
            "cost": c["cost"],
            "traits": c["traits"],
            "trait_ids": c["trait_ids"],
            "img": _img_path("champion", champs_raw[c["id"]]["image"]["full"]),
        })
    data["champions"] = champions

    traits = []
    for t in cs["traits"]:
        traits.append({
            "id": t["id"],
            "name": t["name"],
            "count": t["count"],
            "img": _img_path("trait", trait_img.get(t["id"])),
        })
    data["traits"] = traits
    data["trait_name"] = {tid: trait_name.get(tid, tid) for tid in trait_img}

    # --- 증강체 (tft_guide/02_augments.json) ---
    g = os.path.join(HERE, "tft_guide")
    augs = json.load(open(os.path.join(g, "02_augments.json")))
    augs_raw = {v["id"]: v for v in _local("augments.json").values()}
    pool = []
    for a in augs["augments"]:
        img = None
        if a.get("in_local_datadragon"):
            img = _img_path("augment", augs_raw[a["id"]]["image"]["full"])
        pool.append({
            "id": a["id"], "name": a["name"], "tier": a["tier"],
            "tier_name": a["tier_name"], "new": a["is_set17_new"],
            "desc": a.get("description"), "img": img,
        })
    data["augments"] = pool
    data["augment_tier_counts"] = augs["tier_counts"]

    # --- 아이템 (tft_guide/01_items.json) ---
    items_g = json.load(open(os.path.join(g, "01_items.json")))
    items_raw = {v["name"]: v for v in _local("item.json").values()}
    def item_of(name):
        v = items_raw.get(name)
        return _img_path("item", v["image"]["full"]) if v else None

    basics = [{"name": n, "img": item_of(n)} for n in items_g["basic_components"]]
    standard = [{"name": s["name"], "recipe": s["recipe"], "img": item_of(s["name"]),
                 "recipe_imgs": [item_of(r) for r in s["recipe"]]} for s in items_g["standard_items"]]
    special = {cat: [{"name": n, "img": item_of(n)} for n in names]
               for cat, names in items_g["set17_special_items"].items()}
    data["items"] = {"basics": basics, "standard": standard, "special": special}

    # --- 나머지 섹션 ---
    data["drop_rates"] = json.load(open(os.path.join(g, "03_drop_rates.json")))
    data["rounds"] = json.load(open(os.path.join(g, "04_rounds.json")))
    data["xp_gold"] = json.load(open(os.path.join(g, "05_xp_gold.json")))
    data["damage"] = json.load(open(os.path.join(g, "06_damage.json")))

    data["meta"] = {"set": SET, "patch": PATCH,
                    "champ_count": len(champions), "trait_count": len(traits),
                    "augment_count": len(pool)}
    return data


def load_or_build():
    """이미 생성된 뷰어 데이터를 재사용할 수 있지만 항상 최신으로 재생성한다."""
    return build_data()


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
HTML = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TFT Set 17 (17.9) 뷰어</title>
<style>
:root{
  --bg:#0d1017; --panel:#151a26; --panel2:#1c2333; --line:#2a3348;
  --txt:#dfe5f1; --dim:#8b96ad; --acc:#e8c56a;
  --t1:#c3cad6; --t2:#f0c040; --t3:#c86bd8;
  --c1:#3aa0ff; --c2:#5ad45a; --c3:#ff9d3a; --c4:#c07bff; --c5:#ff5b5b;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);
  font-family:"Malgun Gothic","Apple SD Gothic Neo","Noto Sans KR",system-ui,sans-serif;font-size:14px}
header{position:sticky;top:0;z-index:20;background:linear-gradient(180deg,#0d1017f2,#0d1017e0);
  backdrop-filter:blur(6px);border-bottom:1px solid var(--line);padding:10px 18px}
h1{font-size:17px;margin:0 0 8px;color:var(--acc);letter-spacing:.5px}
h1 small{color:var(--dim);font-weight:400;margin-left:8px}
nav{display:flex;gap:6px;flex-wrap:wrap}
nav button{background:var(--panel);border:1px solid var(--line);color:var(--txt);
  padding:6px 13px;border-radius:8px;cursor:pointer;font-size:13.5px}
nav button:hover{background:var(--panel2)}
nav button.on{background:var(--acc);color:#14100a;border-color:var(--acc);font-weight:700}
main{padding:16px 18px 60px;max-width:1500px;margin:0 auto}
.toolbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:14px}
.toolbar input{background:var(--panel);border:1px solid var(--line);color:var(--txt);
  padding:7px 12px;border-radius:8px;width:230px;font-size:13.5px}
.toolbar .chip{background:var(--panel);border:1px solid var(--line);color:var(--dim);
  padding:5px 11px;border-radius:20px;cursor:pointer;font-size:12.5px}
.toolbar .chip.on{background:var(--panel2);color:var(--txt);border-color:var(--acc)}
.toolbar .chip.x{color:var(--c5);border-color:#5a2b2b}
.count{color:var(--dim);font-size:12.5px;margin-left:auto}
.grid{display:grid;gap:12px}
.g-champ{grid-template-columns:repeat(auto-fill,minmax(150px,1fr))}
.g-aug{grid-template-columns:repeat(auto-fill,minmax(200px,1fr))}
.g-item{grid-template-columns:repeat(auto-fill,minmax(170px,1fr))}
.g-trait{grid-template-columns:repeat(auto-fill,minmax(120px,1fr))}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px;
  position:relative;transition:transform .08s,border-color .08s}
.card:hover{border-color:#4a5878;transform:translateY(-2px)}
.c-portrait{width:100%;aspect-ratio:1/1;object-fit:cover;border-radius:9px;background:#0a0d13}
.c-name{margin-top:7px;font-weight:700;text-align:center;font-size:14px}
.cost{position:absolute;top:6px;left:6px;width:22px;height:22px;border-radius:50%;
  display:flex;align-items:center;justify-content:center;font-weight:800;font-size:13px;color:#fff}
.traits{margin-top:7px;display:flex;flex-wrap:wrap;gap:4px;justify-content:center}
.tchip{background:var(--panel2);border:1px solid var(--line);color:var(--dim);
  font-size:11px;padding:2px 7px;border-radius:10px;cursor:pointer;white-space:nowrap}
.tchip:hover{color:var(--txt);border-color:var(--acc)}
.aug-img{width:96px;height:96px;object-fit:contain;margin:4px auto;display:block;
  background:radial-gradient(circle at 50% 40%,#222b40,#11151f);border-radius:12px;padding:6px}
.tier-badge{position:absolute;top:8px;left:8px;font-size:11px;font-weight:800;
  padding:3px 8px;border-radius:10px;color:#10131a}
.tier1 .tier-badge{background:var(--t1)} .tier2 .tier-badge{background:var(--t2)}
.tier3 .tier-badge{background:var(--t3);color:#fff}
.new-badge{position:absolute;top:8px;right:8px;font-size:11px;font-weight:800;
  background:var(--c3);color:#fff;padding:3px 8px;border-radius:10px}
.aug-name{text-align:center;font-weight:700;margin-top:6px;font-size:13.5px;min-height:20px}
.desc{color:var(--dim);font-size:11.5px;margin-top:5px;line-height:1.45;
  display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.section-h{font-size:16px;margin:26px 0 10px;color:var(--acc);border-bottom:1px solid var(--line);
  padding-bottom:6px}
.section-h small{color:var(--dim);font-weight:400;margin-left:8px}
table{border-collapse:collapse;width:100%;background:var(--panel);border-radius:10px;overflow:hidden}
th,td{border:1px solid var(--line);padding:7px 10px;text-align:center;font-size:13px}
th{background:var(--panel2);color:var(--acc)}
tr.dim td{color:var(--dim);text-decoration:line-through}
.note{color:var(--dim);font-size:12px;margin:8px 0;line-height:1.5}
.warn{border-left:3px solid var(--c3);background:#241d12;padding:8px 12px;border-radius:0 8px 8px 0;
  color:#e8d9b0;font-size:12.5px;margin:10px 0;line-height:1.5}
.stage-row{display:flex;gap:8px;align-items:center;margin-bottom:8px;flex-wrap:wrap}
.stage-lbl{width:70px;color:var(--acc);font-weight:800;font-size:13px;flex:none}
.round-chip{background:var(--panel);border:1px solid var(--line);border-radius:8px;
  padding:5px 9px;font-size:12px;color:var(--txt)}
.round-chip b{color:var(--dim);font-weight:700;margin-right:5px}
.icon-row{display:flex;flex-wrap:wrap;gap:10px}
.icon-item{display:flex;align-items:center;gap:7px;background:var(--panel);border:1px solid var(--line);
  border-radius:10px;padding:6px 12px}
.icon-item img{width:44px;height:44px;object-fit:contain}
.icon-item span{font-size:12.5px}
.recipe{display:flex;align-items:center;justify-content:center;gap:5px;margin-top:6px;flex-wrap:wrap}
.recipe img{width:30px;height:30px;object-fit:contain}
.recipe .plus{color:var(--dim)}
.recipe .arrow{color:var(--acc)}
.lvlbar{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}
.lvl{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:8px 12px;
  text-align:center;min-width:84px}
.lvl .n{font-size:17px;font-weight:800;color:var(--acc)}
.lvl .xp{font-size:12px;color:var(--dim);margin-top:3px}
.fbox{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 16px;margin:8px 0}
.fbox b{color:var(--acc)}
.fbox code{background:#0a0d13;padding:2px 7px;border-radius:6px;color:#9fd0ff}
#tooltip{position:fixed;z-index:99;background:#0a0d13f5;border:1px solid var(--acc);
  border-radius:10px;padding:10px 12px;max-width:320px;font-size:12.5px;line-height:1.5;
  pointer-events:none;display:none;box-shadow:0 6px 24px #000a}
#tooltip .tt-t{font-weight:800;color:var(--acc);margin-bottom:4px}
footer{color:#5a647a;font-size:11.5px;text-align:center;padding:20px;line-height:1.6}
.img-fallback{width:100%;height:100%;display:flex;align-items:center;justify-content:center;
  background:#0a0d13;border-radius:9px;color:#3a4356;font-size:30px}
.empty{color:var(--dim);text-align:center;padding:40px;font-size:14px}
</style>
</head>
<body>
<header>
  <h1>⚔ TFT Set 17 <small>패치 17.9 · 한국어 · 이미지 포함 뷰어</small></h1>
  <nav id="nav">
    <button data-tab="champions" class="on">챔피언</button>
    <button data-tab="traits">시너지</button>
    <button data-tab="augments">증강체</button>
    <button data-tab="items">아이템</button>
    <button data-tab="drops">리롤확률</button>
    <button data-tab="rounds">라운드</button>
    <button data-tab="xpgold">경험치/골드</button>
    <button data-tab="damage">피해 공식</button>
  </nav>
</header>
<main>
  <div id="view"></div>
</main>
<div id="tooltip"></div>
<footer>
  데이터: TFT_DDragon (Data Dragon 17.9, ko_KR) + 중국판 TFT CDN (2026.S17) · 이미지: TFT_DDragon/img (로컬)<br>
  경험치/골드·피해 공식은 클라이언트 고정 상수(패치 17.9 기준 표준값) · 레벨 11 드랍률은 Set 14 잔재(게임에 없음)
</footer>
<script>
const DATA = __DATA__;
const COST_COLOR = {1:'var(--c1)',2:'var(--c2)',3:'var(--c3)',4:'var(--c4)',5:'var(--c5)'};
const state = {tab:'champions', q:'', cost:0, trait:'', augTier:0, augNew:false};
const $ = s => document.querySelector(s);
const esc = s => (s||'').replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

function img(src, alt, cls){
  if(!src) return `<div class="img-fallback">?</div>`;
  return `<img class="${cls||''}" src="${src}" alt="${esc(alt)}" loading="lazy"
    onerror="this.outerHTML='<div class=img-fallback>?</div>'">`;
}

/* ---------- 탭: 챔피언 ---------- */
function vChampions(){
  const list = DATA.champions.filter(c =>
    (!state.cost || c.cost === state.cost) &&
    (!state.trait || c.trait_ids.includes(state.trait)) &&
    (!state.q || c.name.includes(state.q)));
  const traitName = id => DATA.trait_name[id] || id;
  const costBtns = [1,2,3,4,5].map(n =>
    `<span class="chip ${state.cost===n?'on':''}" onclick="setCost(${n})">${n}코스트</span>`).join('');
  const traitChip = state.trait ?
    `<span class="chip x" onclick="clearTrait()">× ${esc(traitName(state.trait))} (클릭해 해제)</span>` : '';
  return `
  <div class="toolbar">
    <input placeholder="챔피언 검색…" value="${esc(state.q)}" oninput="state.q=this.value;render()">
    ${costBtns}${traitChip}
    <span class="count">${list.length} / ${DATA.champions.length}명</span>
  </div>
  ${list.length?`<div class="grid g-champ">`+list.map(c=>`
    <div class="card">
      <span class="cost" style="background:${COST_COLOR[c.cost]}">${c.cost}</span>
      ${img(c.img, c.name, 'c-portrait')}
      <div class="c-name">${esc(c.name)}</div>
      <div class="traits">${c.traits.map((t,i)=>
        `<span class="tchip" onclick="filterTrait('${c.trait_ids[i]}')"
          onmousemove="tip(event,'${esc(c.name)}','${esc(c.traits.join(', '))}')"
          onmouseleave="untip()">${esc(t)}</span>`).join('')}
      </div>
    </div>`).join('')+`</div>`:`<div class="empty">조건에 맞는 챔피언 없음</div>`}`;
}
function setCost(n){ state.cost = state.cost===n?0:n; render(); }
function filterTrait(id){ state.trait=id; state.tab='champions'; render(); }
function clearTrait(){ state.trait=''; render(); }

/* ---------- 탭: 시너지 ---------- */
function vTraits(){
  const list = DATA.traits.filter(t=>!state.q||t.name.includes(state.q));
  return `
  <div class="toolbar"><input placeholder="시너지 검색…" value="${esc(state.q)}"
    oninput="state.q=this.value;render()">
    <span class="count">${list.length} / ${DATA.traits.length}개 · 챔피언 수 표기 · 클릭하면 챔피언으로 필터</span></div>
  <div class="grid g-trait">`+list.map(t=>`
    <div class="card" onclick="filterTrait('${t.id}')" style="cursor:pointer">
      <img src="${t.img||''}" style="width:56px;height:56px;object-fit:contain;margin:0 auto;display:block"
        alt="" onerror="this.style.display='none'">
      <div class="c-name">${esc(t.name)}</div>
      <div class="desc" style="text-align:center">${t.count}명</div>
    </div>`).join('')+`</div>`;
}

/* ---------- 탭: 증강체 ---------- */
function vAugments(){
  const list = DATA.augments.filter(a =>
    (!state.augTier || a.tier===state.augTier) &&
    (!state.augNew || a.new) &&
    (!state.q || a.name.includes(state.q)));
  const tb = [1,2,3].map(n=>
    `<span class="chip ${state.augTier===n?'on':''}" onclick="state.augTier=state.augTier===${n}?0:${n};render()">${DATA.augment_tier_counts[TIERN[n]]}종 ${TIERN[n]}</span>`).join('')
    + `<span class="chip ${state.augNew?'on':''}" onclick="state.augNew=!state.augNew;render()">🆕 Set 17 신규</span>`;
  return `
  <div class="toolbar"><input placeholder="증강체 검색 (272종)…" value="${esc(state.q)}"
    oninput="state.q=this.value;render()"> ${tb}
    <span class="count">${list.length} / ${DATA.augments.length}종</span></div>
  ${list.length?`<div class="grid g-aug">`+list.map(a=>`
    <div class="card tier${a.tier}" onmousemove="tip(event,'${esc(a.name)} · ${a.tier_name}${a.new?' · Set 17 신규':''}','${esc(a.desc||'설명 없음 (17.9 DDragon 미포함)')}')" onmouseleave="untip()">
      <span class="tier-badge">${a.tier_name}</span>
      ${a.new?'<span class="new-badge">🆕</span>':''}
      ${img(a.img, a.name, 'aug-img')}
      <div class="aug-name">${esc(a.name)}</div>
      <div class="desc">${esc(a.desc||'설명 없음 (17.9 DDragon 미포함)')}</div>
    </div>`).join('')+`</div>`:`<div class="empty">조건에 맞는 증강체 없음</div>`}`;
}
const TIERN = {1:'실버',2:'골드',3:'프리즘'};

/* ---------- 탭: 아이템 ---------- */
function vItems(){
  const I = DATA.items;
  const match = x => !state.q || x.name.includes(state.q);
  const basics = I.basics.filter(match);
  const std = I.standard.filter(match);
  const special = {};
  for(const cat in I.special){ const arr = I.special[cat].filter(match); if(arr.length) special[cat]=arr; }
  return `
  <div class="toolbar"><input placeholder="아이템 검색…" value="${esc(state.q)}"
    oninput="state.q=this.value;render()">
    <span class="count">기본 ${basics.length} · 표준 ${std.length} · 특수 ${Object.values(special).reduce((a,b)=>a+b.length,0)}</span></div>
  <div class="section-h">기본 부품 <small>레시피 재료 · 두 개 합치기</small></div>
  <div class="icon-row">${basics.map(b=>`<div class="icon-item">${img(b.img,b.name)}<span>${esc(b.name)}</span></div>`).join('')||'<span class=note>없음</span>'}</div>
  <div class="section-h">표준 아이템 <small>레시피 포함</small></div>
  <div class="grid g-item">${std.map(s=>`
    <div class="card" onmousemove="tip(event,'${esc(s.name)}','레시피: ${esc(s.recipe.join(' + '))}')" onmouseleave="untip()">
      ${img(s.img, s.name, 'c-portrait')}
      <div class="c-name">${esc(s.name)}</div>
      <div class="recipe">${s.recipe_imgs.map((p,i)=>
        `${i>0?'<span class=arrow>+</span>':''}${p?`<img src="${p}" onerror="this.style.display='none'">`:'<span class=plus>?</span>'}`).join('')}</div>
      <div class="desc" style="text-align:center">${esc(s.recipe.join(' + '))}</div>
    </div>`).join('')||'<div class=empty>없음</div>'}</div>
  ${Object.keys(special).map(cat=>`
    <div class="section-h">${esc(cat)} <small>${special[cat].length}종</small></div>
    <div class="icon-row">${special[cat].map(b=>`<div class="icon-item"
      title="${esc(b.name)}">${img(b.img,b.name)}<span>${esc(b.name)}</span></div>`).join('')}</div>`).join('')}`;
}

/* ---------- 탭: 드랍률 ---------- */
function vDrops(){
  const D = DATA.drop_rates;
  return `
  <div class="warn">⚠️ 레벨 11 행은 **Set 14(14.23)에서 이 파일이 처음 생겼을 때의 잔재**입니다.
  Set 15~17은 최대 레벨 10이므로 실제 게임에는 없습니다 (표에서 취소선).</div>
  <table><tr><th>레벨</th><th>1코스트</th><th>2코스트</th><th>3코스트</th><th>4코스트</th><th>5코스트</th></tr>
  ${D.shop_drop_rates.map(r=>{
    const d=r.drop_rate_percent;
    return `<tr class="${r.exists_in_game?'':'dim'}">
      <td><b>${r.level}</b>${r.exists_in_game?'':' (데이터 잔재)'}</td>
      <td>${d['1cost']}%</td><td>${d['2cost']}%</td><td>${d['3cost']}%</td>
      <td>${d['4cost']}%</td><td>${d['5cost']}%</td></tr>`;
  }).join('')}</table>`;
}

/* ---------- 탭: 라운드 ---------- */
function vRounds(){
  const rows = DATA.rounds.rounds;
  const stages = {};
  rows.forEach(r=>{ (stages[r.stage]=stages[r.stage]||[]).push(r); });
  return `<div class="note">공식 Data Dragon <code>stage-round-data.json</code> 기준 · 스테이지 ${Object.keys(stages).length}개, 라운드 ${rows.length}개</div>`
  + Object.keys(stages).sort((a,b)=>a-b).map(s=>`
    <div class="stage-row"><span class="stage-lbl">스테이지 ${s}</span>
      ${stages[s].map(r=>`<span class="round-chip"><b>${r.round}</b>${esc(r.label)}</span>`).join('')}
    </div>`).join('');
}

/* ---------- 탭: 경험치/골드 ---------- */
function vXP(){
  const D = DATA.xp_gold;
  return `
  <div class="warn">⚠️ Data Dragon에 없는 **클라이언트 고정 상수**(표준 모드). 최대 레벨 10 — 레벨 11은 존재하지 않는다.</div>
  <div class="section-h">레벨업 필요 경험치 <small>매 라운드 +2 XP</small></div>
  <div class="lvlbar">${D.level_up_xp.map(r=>`
    <div class="lvl"><div class="n">Lv.${r.to_level}</div><div class="xp">${r.xp_required} XP 필요</div></div>`).join('')}</div>
  <div class="section-h">골드 이자 <small>floor(보유 골드 / 10) · 최대 5골드 · 50골드 이상 시 상한 · 보유 상한 50</small></div>
  <table><tr><th>보유 골드</th>${D.gold.interest_table.map(r=>`<th>${esc(r.gold)}</th>`).join('')}</tr>
  <tr><td>이자</td>${D.gold.interest_table.map(r=>`<td><b>${r.interest}</b>골드</td>`).join('')}</tr></table>
  <div class="section-h">상점 리롤(새로고침) <small>고정 ${D.reroll_cost}골드 · 가능 횟수 = floor(보유 골드 / ${D.reroll_cost})</small></div>
  <p>상점 리롤은 항상 <b>고정 ${D.reroll_cost}골드</b>이다. 보유 골드로 계산된 가능 리롤 횟수:</p>
  <table><tr><th>보유 골드</th><th>10</th><th>15</th><th>20</th><th>30</th><th>50</th></tr>
  <tr><td>리롤 가능 횟수</td>${[10,15,20,30,50].map(g=>`<td><b>${Math.floor(g/D.reroll_cost)}</b>회 (${g}골드)</td>`).join('')}</tr></table>`;
}

/* ---------- 탭: 피해 공식 ---------- */
function vDamage(){
  const D = DATA.damage;
  const bs = D.base_stats;
  return `
  <div class="warn">⚠️ Data Dragon에 없는 **클라이언트 고정 공식**(표준값, 세트별 일부 수치 차이 가능)</div>
  <div class="section-h">기본 능력치</div>
  <table><tr><th>능력치</th><th>레벨 1</th><th>레벨당 성장</th></tr>
  <tr><td>최대 체력</td><td>${bs.max_hp.level1}</td><td>+${bs.max_hp.per_level}</td></tr>
  <tr><td>공격력 (AD)</td><td>${bs.ad.level1}</td><td>+${bs.ad.per_level}</td></tr>
  <tr><td>마법력 (AP)</td><td>${bs.ap.level1}</td><td>+${bs.ap.per_level}</td></tr>
  <tr><td>방어력</td><td>${bs.armor.level1}</td><td>+${bs.armor.per_level}</td></tr>
  <tr><td>마법 저항</td><td>${bs.magic_resist.level1}</td><td>+${bs.magic_resist.per_level}</td></tr></table>
  <div class="section-h">피해 계산 공식</div>
  <div class="fbox"><b>물리 피해</b> = <code>${esc(D.damage_formulas.physical)}</code></div>
  <div class="fbox"><b>마법 피해</b> = <code>${esc(D.damage_formulas.magic)}</code></div>
  <div class="fbox"><b>진실 피해</b> = <code>${esc(D.damage_formulas.true)}</code></div>
  <div class="section-h">방어력 / 마법 저항 상한</div>
  ${D.armor_mr_caps.map(s=>`<div class="fbox">• ${esc(s)}</div>`).join('')}
  <div class="section-h">기타</div>
  ${D.other.map(s=>`<div class="fbox">• ${esc(s)}</div>`).join('')}`;
}

/* ---------- 툴팁 ---------- */
const tt = $('#tooltip');
function tip(ev, title, body){
  tt.innerHTML = `<div class="tt-t">${title}</div>${body}`;
  tt.style.display='block';
  const r = tt.getBoundingClientRect();
  let x = ev.clientX+14, y = ev.clientY+14;
  if(x+r.width > innerWidth-8) x = ev.clientX-r.width-14;
  if(y+r.height > innerHeight-8) y = ev.clientY-r.height-14;
  tt.style.left=x+'px'; tt.style.top=y+'px';
}
function untip(){ tt.style.display='none'; }

/* ---------- 렌더 ---------- */
const VIEWS = {champions:vChampions, traits:vTraits, augments:vAugments, items:vItems,
  drops:vDrops, rounds:vRounds, xpgold:vXP, damage:vDamage};
function render(){
  document.querySelectorAll('#nav button').forEach(b=>b.classList.toggle('on', b.dataset.tab===state.tab));
  $('#view').innerHTML = VIEWS[state.tab]();
}
document.querySelectorAll('#nav button').forEach(b=>
  b.onclick = ()=>{ state.tab=b.dataset.tab; state.q=''; state.augTier=0; state.augNew=false; state.cost=0; state.trait=''; render(); });
render();
</script>
</body>
</html>
"""


def generate_html(data, out_path):
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = HTML.replace("__DATA__", payload)
    open(out_path, "w").write(html)
    return out_path


# ---------------------------------------------------------------------------
# 서버
# ---------------------------------------------------------------------------
class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass


def find_port(preferred):
    for p in [preferred] + [preferred + i for i in range(1, 50)]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return preferred


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=18080)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    print("[build] 데이터 조립 중…")
    data = load_or_build()
    m = data["meta"]
    out = os.path.join(HERE, "tft_set17_viewer.html")
    generate_html(data, out)
    print(f"[build] {out}")
    print(f"        챔피언 {m['champ_count']} · 시너지 {m['trait_count']} · "
          f"증강체 {m['augment_count']} · 이미지: 로컬 TFT_DDragon/img")

    port = find_port(args.port)
    handler = lambda *a, **k: QuietHandler(*a, directory=HERE, **k)
    httpd = HTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{port}/tft_set17_viewer.html"
    print(f"[serve] {url}  (Ctrl+C 로 종료)")
    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[bye]")


if __name__ == "__main__":
    main()
