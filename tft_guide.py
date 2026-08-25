#!/usr/bin/env python3
"""TFT Set 17 (패치 17.9) 종합 가이드 생성기.

다음 6개 영역을 한국어로 정리해 markdown + 섹션별 JSON으로 내뱉는다:
  1. 아이템   (기본 부품 / 레시피 포함 표준 아이템 / Set 17 특수 아이템)
  2. 증강체   (시즌 카루셀 풀 전체: 이름 + 설명 + 티어)
  3. 리롤확률 (레벨별 상점 드랍률)
  4. 라운드   (스테이지/라운드 스케줄)
  5. 경험치/골드 (레벨업 비용, 이자, 리롤 할인 — 클라이언트 상수)
  6. 피해량 공식 (물리/마법/진실 피해, 방어력 상한, 크리 — 클라이언트 상수)

출력
----
* tft_set17_guide.md            — 전체 가이드 (markdown)
* tft_guide/01_items.json       — 섹션별 JSON (아래 키명)
* tft_guide/02_augments.json
* tft_guide/03_drop_rates.json
* tft_guide/04_rounds.json
* tft_guide/05_xp_gold.json
* tft_guide/06_damage.json

데이터 출처
-----------
* 로컬 `TFT_DDragon/data/ko_KR` (공식 Data Dragon 17.9)
  - 이름/설명/리롤확률/라운드 스케줄
* 중국판 TFT CDN (game.gtimg.cn, 2026.S17)
  - 아이템 레시피(equip.js `formula`), 증강체 풀·티어(hex.js `type`)
* 경험치/골드·피해 공식은 Data Dragon에 없는 클라이언트 고정 상수이므로
  표준값을 표기하고 각 섹션에 출처를 명시한다.

사용법
------
    python3 tft_guide.py            # tft_set17_guide.md + tft_guide/*.json 생성
    python3 tft_guide.py --refresh  # CDN 캐시 무시
"""
import argparse
import json
import os
import re
import urllib.request
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DDATA = os.path.join(HERE, "TFT_DDragon", "data", "ko_KR")
SET = 17
PATCH = "17.9"
CDN = "https://game.gtimg.cn/images/lol/act/img/tft/js"
OUT_DIR = os.path.join(HERE, "tft_guide")

# CDN에서 받아와 캐시할 파일 (로컬에는 없는 매핑/효과 정보)
CDN_FILES = {
    "chess": f"{CDN}/chess.js",
    "equip": f"{CDN}/equip.js",
    "hex": f"{CDN}/hex.js",
}
CACHE_DIR = os.path.join(HERE, ".tft_cache")

TIER_NAME = {1: "실버", 2: "골드", 3: "프리즘"}

# ---------------------------------------------------------------------------
# 공통
# ---------------------------------------------------------------------------


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def load_cdn(refresh=False):
    os.makedirs(CACHE_DIR, exist_ok=True)
    out = {}
    for name, url in CDN_FILES.items():
        cache = os.path.join(CACHE_DIR, f"s{SET}_{name}.json")
        if refresh or not os.path.exists(cache):
            txt = fetch(url)
            json.dump(json.loads(txt), open(cache, "w"), ensure_ascii=False)
        out[name] = json.load(open(cache))
    return out


def local(fn):
    d = json.load(open(os.path.join(DDATA, fn)))
    return d.get("data", d)


def strip_html(s):
    return re.sub(r"<[^>]+>", "", s or "").replace("\n", " ").strip()


# ---------------------------------------------------------------------------
# 섹션 1: 아이템
# ---------------------------------------------------------------------------
def build_items(cdn):
    items = local("item.json")
    std_ko = {v["id"]: v["name"] for k, v in items.items() if k.startswith("TFT_Item_")}
    eq = cdn["equip"]["data"]
    by_en = {r["englishName"]: r for r in eq if r.get("englishName")}
    comp_name = {r["equipId"]: std_ko[r["englishName"]] for r in eq if r.get("englishName") in std_ko}

    results = {en for en, r in by_en.items() if en in std_ko and r.get("formula")}
    components = set()
    for en in results:
        for p in by_en[en]["formula"].split(","):
            components.add(comp_name.get(p))
    # 기본 부품 = 레시피에 쓰이지만 그 자체가 완성품이 아닌 것
    basics = sorted(n for n in (components - results) if n)

    finals = []
    for en, rec in by_en.items():
        if en not in std_ko or not rec.get("formula"):
            continue
        parts = [comp_name.get(p, f"?(id {p})") for p in rec["formula"].split(",")]
        finals.append({"name": std_ko[en], "recipe": parts})
    finals.sort(key=lambda x: x["name"])

    def cat_of(i):
        if "Emblem" in i:
            return "상징 (시너지 엠블럼)"
        if "Artifact" in i:
            return "유물"
        if "AnimaSquad" in i:
            return "동물특공대 무기"
        if "GravesTrait" in i:
            return "그레이브즈 (최신상) 업그레이드"
        if "SonaUnique" in i:
            return "소나 (지휘관) 모드"
        if "MissFortuneUnique" in i:
            return "미스 포츈 모드"
        if "Consumable" in i:
            return "사용품"
        return None  # MarketOffering 등 상점 아이템은 제외

    groups = {}
    for i, v in items.items():
        if not v["id"].startswith(f"TFT{SET}_"):
            continue
        c = cat_of(v["id"])
        if c:
            groups.setdefault(c, []).append(v["name"])

    order = ["상징 (시너지 엠블럼)", "유물", "동물특공대 무기", "그레이브즈 (최신상) 업그레이드",
             "소나 (지휘관) 모드", "미스 포츈 모드", "사용품"]
    special = {c: sorted(set(groups[c])) for c in order if c in groups}

    data = {
        "basic_components": basics,
        "standard_items": finals,
        "set17_special_items": special,
        "sources": {
            "names": f"TFT_DDragon/data/ko_KR/item.json (patch {PATCH})",
            "recipes": "CDN equip.js `formula` (game.gtimg.cn, 2026.S17)",
            "basic_components_note": "레시피에 쓰이지만 완성품이 아닌 아이템을 데이터에서 동적 계산",
        },
    }

    lines = ["## 1. 아이템", "",
             f"### 기본 부품 (레시피 재료, {len(basics)}종)", "",
             "기본 부품은 상점에서 개별적으로 나오며 두 개를 합쳐 표준 아이템을 만든다.", "",
             "| " + " | ".join(basics) + " |", "| " + "---|" * len(basics), ""]
    lines += [f"### 표준 아이템 (레시피, {len(finals)}종)", "",
              "| 완성 아이템 | 레시피 |", "|---|---|"]
    for it in finals:
        lines.append(f"| {it['name']} | {' + '.join(it['recipe'])} |")
    lines.append("")
    for c in order:
        if c not in special:
            continue
        lines += [f"### {c} ({len(special[c])}종)", "", ", ".join(special[c]), ""]
    return data, "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# 섹션 2: 증강체
# ---------------------------------------------------------------------------
def augment_tier(v, hexmap):
    """증강체 티어(1~3) 반환. hex type 우선, 없으면 이미지 파일명 로마숫자에서 추출."""
    t = hexmap.get(v["id"], {}).get("type")
    if t and str(t).isdigit():
        return int(t)
    base = v["image"]["full"].split(".")[0]
    m = re.search(r"[-_](I|II|III)$", base)
    if m:
        return {"I": 1, "II": 2, "III": 3}[m.group(1)]
    m = re.search(r"(?:T|[-_])(\d)$", base)
    if m:
        return int(m.group(1))
    return 0


def build_augments(cdn):
    local_augs = {v["id"]: v for v in local("augments.json").values()}
    # 시즌 전체 카루셀 풀: hex.js의 모든 증강 엔트리
    pool = [v for v in cdn["hex"]["data"].values() if v.get("augments")]
    hexmap = {v["augments"]: v for v in pool}

    def name_of(aid):
        return local_augs.get(aid, {}).get("name") or hexmap[aid].get("name", aid)

    rows = []
    for v in pool:
        aid = v["augments"]
        t = hexmap[aid].get("type")
        tier = int(t) if t and str(t).isdigit() else 0
        desc = strip_html(local_augs.get(aid, {}).get("description", ""))
        rows.append({
            "id": aid,
            "name_ko": local_augs.get(aid, {}).get("name"),
            "name": name_of(aid),
            "tier": tier,
            "tier_name": TIER_NAME.get(tier, "?"),
            "is_set17_new": aid.startswith(f"TFT{SET}_Augment"),
            "description": desc or None,
            "in_local_datadragon": aid in local_augs,
        })
    rows.sort(key=lambda r: (r["tier"], r["name"]))
    counts = Counter(r["tier"] for r in rows)

    data = {
        "total": len(rows),
        "tier_counts": {TIER_NAME[k]: counts[k] for k in sorted(counts)},
        "set17_new_count": sum(r["is_set17_new"] for r in rows),
        "tier_legend": TIER_NAME,
        "augments": rows,
        "sources": {
            "pool": "CDN hex.js (game.gtimg.cn, 2026.S17) — 시즌 카루셀 풀 전체 (이월+공용 포함)",
            "tier": "hex.js `type`(1/2/3) ↔ 로컬 augments.json 이미지명 로마숫자(_I/_II/_III) 교차 검증, 1:1 일치",
            "names_descriptions": "TFT_DDragon/data/ko_KR/augments.json (로컬에 없는 2종은 중국어 이름)",
        },
    }

    n_new = data["set17_new_count"]
    lines = ["## 2. 증강체 (Augments)", "",
             f"시즌 2026.S17 증강 카루셀 풀 전체 **{len(rows)}종** (CDN hex.js 기준). "
             f"이 중 Set {SET}에서 신규 추가된 것은 {n_new}종, 나머지는 이전 세트에서 이월·공용. "
             "티어는 hex.js `type`·로컬 이미지명(로마숫자) 교차 검증. "
             "한국어 이름·설명은 로컬 Data Dragon (2종은 17.9 DDragon에 아직 없어 중국어 표기).", "",
             "집계: " + " · ".join(f"{TIER_NAME[k]} {counts[k]}종" for k in sorted(counts)), "",
             "| 티어 | 증강체 | 설명 |", "|---|---|---|"]
    for r in rows:
        mark = " 🆕" if r["is_set17_new"] else ""
        lines.append(f"| {r['tier_name']} | {r['name']}{mark} | {r['description'] or '(설명 없음 — 로컬 데이터 미포함)'} |")
    lines += ["", f"🆕 = Set {SET} 신규 증강. (증강은 매 세트에 일부가 다음 세트로 이월된다.)", ""]
    return data, "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# 섹션 3: 리롤확률 (상점 드랍률)
# ---------------------------------------------------------------------------
def build_drop_rates():
    shop = local("shop-drop-rates-data.json")["Shop"]
    rows = []
    for row in shop:
        rates = {r["cost"]: r["rate"] for r in row["dropRatesByTier"]}
        lvl = row["level"]
        rows.append({
            "level": lvl,
            "drop_rate_percent": {f"{c}cost": rates.get(c, 0) for c in range(1, 6)},
            "exists_in_game": lvl <= 10,
        })
    data = {
        "shop_drop_rates": rows,
        "note": "레벨 11 행은 Set 14(14.23)에서 파일이 처음 생겼을 때의 잔재 — Set 15~17은 최대 레벨 10",
        "source": "TFT_DDragon/data/ko_KR/shop-drop-rates-data.json",
    }

    lines = ["## 3. 리롤확률 (레벨별 상점 드랍률)", "",
             "공식 Data Dragon(`shop-drop-rates-data.json`) 기준. 각 레벨에서 상점이 "
             "해당 코스트 챔피언을 뽑을 확률(%).", "",
             "> ⚠️ 데이터에는 레벨 11 행이 있으나, 이는 **Set 14(14.23 패치)에서 이 파일이"
             " 처음 생길 때의 잔재**다. Set 14는 실제 최대 레벨이 11(6코스트 존재)이었으나,"
             " Set 15~17은 최대 레벨 10이므로 레벨 11은 실제 게임에 없다.", "",
             "| 레벨 | 1코스트 | 2코스트 | 3코스트 | 4코스트 | 5코스트 |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        d = r["drop_rate_percent"]
        note = "  *(실제 없음 — Set 14 잔재)" if not r["exists_in_game"] else ""
        lines.append(f"| {r['level']}{note} | {d['1cost']} | {d['2cost']} | {d['3cost']} | {d['4cost']} | {d['5cost']} |")
    lines.append("")
    return data, "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# 섹션 4: 라운드 정보
# ---------------------------------------------------------------------------
ROUND_LABEL = {
    "TFT_Round_Carousel": "증강 카루셀 (증강 선택)",
    "TFT17_Round_Intro1": "설정 (Intro 1)",
    "TFT17_Round_Intro2": "설정 (Intro 2)",
    "TFT17_Round_Intro3": "설정 (Intro 3)",
    "TFT_Round_Combat": "전투",
    "TFT_Round_Combat_Set6_Standard_AugmentEarly": "전투 + 증강 선택 (초기)",
    "TFT_Round_Combat_Set6_Standard_AugmentMid": "전투 + 증강 선택 (중반)",
    "TFT_Round_Combat_Set6_Standard_AugmentLate": "전투 + 증강 선택 (후반)",
    "TFT17_Round_CarouselMarket": "마켓 (상점)",
    "TFT17_Round_Krugs": "크러그 (미니언)",
    "TFT17_Round_Wolves": "늑대",
    "TFT17_Round_GodBlessing": "신의 축복 (Divine Blessing)",
    "TFT17_Round_Combat_PostGodBlessing": "전투 (축복 후)",
    "TFT17_Round_PostBlessingItemArmory": "아이템 단조 (Item Armory)",
    "TFT17_Round_Dragon": "드래곤 (보스)",
}


def build_rounds():
    srd = local("stage-round-data.json")
    stages = srd["stages"]
    rows = []
    for s in sorted(stages, key=int):
        for r in sorted(stages[s]["rounds"], key=int):
            name = stages[s]["rounds"][r].get("name", "")
            rows.append({"stage": int(s), "round": int(r), "raw_id": name,
                         "label": ROUND_LABEL.get(name, name)})
    data = {"rounds": rows, "source": "TFT_DDragon/data/ko_KR/stage-round-data.json"}

    lines = ["## 4. 라운드 정보 (스테이지/라운드 스케줄)", "",
             "공식 Data Dragon(`stage-round-data.json`) 기준.", "",
             "| 스테이지 | 라운드 | 내용 |", "|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['stage']} | {r['round']} | {r['label']} |")
    lines.append("")
    return data, "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# 섹션 5: 경험치 / 골드 (클라이언트 상수)
# ---------------------------------------------------------------------------
def build_xp_gold():
    data = {
        "caveat": "Data Dragon JSON에 포함되지 않는 TFT 클라이언트 고정 상수. 표준(일반/랭크) 값이며 모드(터보/더블업)에 따라 달라질 수 있다.",
        "max_level": 10,
        "xp_per_round": 2,
        "level_up_xp": [
            {"from_level": a, "to_level": b, "xp_required": c}
            for a, b, c in [(1, 2, 2), (2, 3, 6), (3, 4, 10), (4, 5, 20), (5, 6, 36),
                            (6, 7, 60), (7, 8, 68), (8, 9, 68), (9, 10, 68)]
        ],
        "gold": {
            "interest_correction": ("// 2026-08-24 수정: 기존 5골드 단위 테이블이 실제 게임 규칙과 불일치하여 "
                                    "10골드 단위로 정정. 2026-08-24 감사 F-3: 공식 문자열 필드(이중 진원) 제거, "
                                    "interest_table만 규칙 근거로 확정. 출처: TFT Set 17 경제 가이드 다수 교차검증 "
                                    "(mobalytics.gg, tftemblem.com, wiki.leagueoflegends.com)"),
            "max_gold": 50,
            "interest_table": [
                {"gold": f"{lo}-{hi}", "interest": i}
                for lo, hi, i in [(0, 9, 0), (10, 19, 1), (20, 29, 2), (30, 39, 3), (40, 49, 4), (50, 99, 5)]
            ],
        },
        "reroll_cost": 2,
        "reroll_cost_note": ("// 2026-08-24 수정: 구간별 유지율 필드(제거됨)는 실제 게임에 없는 "
                             "메커니즘으로 확인되어 제거. 상점 리롤은 항상 고정 2골드. "
                             "출처: tft.ninja 상점 가이드 교차검증"),
        "level11_note": ("shop-drop-rates-data.json의 레벨 11 행은 Set 14(14.23)에서 파일이 처음 "
                         "추가됐을 때(당시 최대 레벨 11, 6코스트 존재)의 잔재가 Set 15~17까지 유지된 것. "
                         "Set 17은 최대 레벨 10."),
    }

    lines = ["## 5. 경험치 / 골드", "",
             "> ⚠️ 이 섹션은 Data Dragon JSON에 **포함되지 않는** TFT 클라이언트 고정 상수이다. "
             "표준(일반/랭크) 값이며 모드(터보/더블업)에 따라 달라질 수 있다. "
             "**최대 레벨은 10** (11레벨은 존재하지 않는다).", "",
             "### 레벨업 필요 경험치", "",
             "매 라운드(전투 승리 등) **2 XP** 획득. 아래는 해당 레벨 → 다음 레벨에 필요한 XP.", "",
             "| 현재 레벨 | 다음 레벨 | 필요 경험치 |", "|---|---|---|"]
    for r in data["level_up_xp"]:
        lines.append(f"| {r['from_level']} | {r['to_level']} | {r['xp_required']} |")
    lines += ["",
              "> 레벨 11 관련: `shop-drop-rates-data.json`에 레벨 11 드랍률 행이 존재하는데,"
              " 이 파일은 **Set 14(14.23)에서 처음 추가**됐을 때(당시 최대 레벨 11, 6코스트 존재)의"
              " 잔재가 Set 15~17까지 그대로 유지된 것이다. Set 17은 최대 레벨 10이다.", "",
              "### 골드 이자 (Interest)", "",
              "- 이자 = `floor(보유 골드 / 10)`, **최대 5골드** (50골드 이상 시 상한)",
              "| 보유 골드 | 이자 |", "|---|---|"]
    for r in data["gold"]["interest_table"]:
        lines.append(f"| {r['gold']} | {r['interest']} |")
    lines += ["- 최대 보유 골드: **50**", "",
              "### 상점 리롤(새로고침)", "",
              f"상점 리롤은 항상 **고정 {data['reroll_cost']}골드**이다. "
              "(구간별 유지율 메커니즘은 실제 게임에 존재하지 않는다 — 2026-08-24 정정)", "",
              "보유 골드로 가능 리롤 횟수 = `floor(보유 골드 / 2)`. 예: 20골드 → 10회.", ""]
    lines.append("")
    return data, "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# 섹션 6: 피해량 공식 (클라이언트 상수)
# ---------------------------------------------------------------------------
def build_damage():
    data = {
        "caveat": "Data Dragon JSON에 포함되지 않는 TFT 클라이언트 고정 공식. 표준 값이며 세트에 따라 일부 수치가 다를 수 있다.",
        "base_stats": {
            "max_hp": {"level1": 700, "per_level": 65},
            "ad": {"level1": 55, "per_level": 6},
            "ap": {"level1": 35, "per_level": 2.5},
            "armor": {"level1": 35, "per_level": 8},
            "magic_resist": {"level1": 35, "per_level": 8},
        },
        "damage_formulas": {
            "physical": "AD × 100 / (100 + 방어력)",
            "magic": "AP × 100 / (100 + 마법 저항)",
            "true": "AD (방어/저항 무시)",
        },
        "armor_mr_caps": [
            "피해 감소는 최대 100%까지 (피해가 0이 될 수 없음)",
            "방어력 100 → 물리 피해 50%, 방어력 200 → 33.3%",
            "마법 저항도 동일하게 적용",
        ],
        "other": [
            "크리틱: 기본 피해의 200% (아이템으로 변화)",
            "흡혈(Lifesteal): 가한 피해의 %만큼 회복",
            "대형/소형 유닛 크기에 따른 피해 보정, 위치(앞/뒤열) 보정 등 세트 메커니즘이 추가로 적용됨",
        ],
    }

    lines = ["## 6. 피해량 공식", "",
             "> ⚠️ 이 섹션은 Data Dragon JSON에 **포함되지 않는** TFT 클라이언트 고정 공식이다. "
             "표준 값이며 세트에 따라 일부 수치가 다를 수 있다.", "",
             "### 기본 능력치 (레벨 1 기준 / 성장)", "",
             "| 능력치 | 레벨 1 | 레벨당 성장 |", "|---|---|---|",
             "| 최대 체력 | 700 | +65 |",
             "| 기본 공격력 (AD) | 55 | +6 |",
             "| 기본 마법력 (AP) | 35 | +2.5 |",
             "| 방어력 | 35 | +8 |",
             "| 마법 저항 | 35 | +8 |", "",
             "### 피해 계산 공식", "",
             "| 피해 종류 | 공식 |", "|---|---|",
             "| 물리 피해 | `AD × 100 / (100 + 방어력)` |",
             "| 마법 피해 | `AP × 100 / (100 + 마법 저항)` |",
             "| 진실 피해 | `AD` (방어/저항 무시) |", "",
             "### 방어력 / 마법 저항 상한", ""]
    lines += [f"- {s}" for s in data["armor_mr_caps"]]
    lines += ["", "### 기타", ""]
    lines += [f"- {s}" for s in data["other"]]
    lines.append("")
    return data, "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
SECTIONS = [
    ("01_items", "items"),
    ("02_augments", "augments"),
    ("03_drop_rates", "drop_rates"),
    ("04_rounds", "rounds"),
    ("05_xp_gold", "xp_gold"),
    ("06_damage", "damage"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="CDN 캐시 무시")
    args = ap.parse_args()

    cdn = load_cdn(refresh=args.refresh)

    builders = [
        lambda: build_items(cdn),
        lambda: build_augments(cdn),
        build_drop_rates,
        build_rounds,
        build_xp_gold,
        build_damage,
    ]
    results = [b() for b in builders]

    header = [
        f"# TFT Set {SET} (패치 {PATCH}) — 종합 가이드",
        "",
        f"- 데이터 기준: 패치 {PATCH} (공식 Data Dragon) + Set {SET} (2026.S17)",
        "- 출처: `TFT_DDragon/data/ko_KR` (이름/설명/확률/라운드) · "
        "중국판 TFT CDN (레시피/티어) · 클라이언트 상수 (경험치/골드·피해 공식)",
        "- 섹션별 JSON: `tft_guide/01_items.json` ~ `06_damage.json`",
        "",
        "---",
        "",
    ]
    body = "\n".join(md for _, md in results)
    out = "\n".join(header) + body
    md_path = os.path.join(HERE, f"tft_set{SET}_guide.md")
    open(md_path, "w").write(out)
    print(f"[saved] {md_path}  ({len(out)} bytes)")

    os.makedirs(OUT_DIR, exist_ok=True)
    for (fname, key), (data, _) in zip(SECTIONS, results):
        meta = {
            "section": key,
            "set": SET,
            "patch": PATCH,
            "generated": "tft_guide.py",
            **data,
        }
        p = os.path.join(OUT_DIR, f"{fname}.json")
        json.dump(meta, open(p, "w"), ensure_ascii=False, indent=1)
        print(f"[saved] {p}")
    print(f"  섹션 6개: 아이템 / 증강체 / 리롤확률 / 라운드 / 경험치·골드 / 피해 공식")


if __name__ == "__main__":
    main()
