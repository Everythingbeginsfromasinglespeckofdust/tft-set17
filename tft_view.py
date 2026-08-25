#!/usr/bin/env python3
"""TFT Set 17 (패치 17.9) 한국어 챔피언/시너지 뷰어.

데이터 소스
-----------
1. 로컬 `TFT_DDragon/data/ko_KR` (라이엇 공식 Data Dragon, 패치 17.9)
   - champion.json : 챔피언 이름 / 코스트 / 티어
   - trait.json    : 시너지(트라이브/클래스) 한국어 이름
2. 중국판 TFT CDN (game.gtimg.cn, "2026.S17") — 매핑만 사용
   - 라이엇 공식 Data Dragon에는 "챔피언→시너지" 매핑이 없기 때문에,
     champion->traits 매핑만 이 소스에서 받아온다 (한국어 이름은 전부 로컬 사용).
   - 매핑은 tft_mapping_<SET>.json 에 캐시되어 이후엔 오프라인 동작.

사용법
------
    python3 tft_view.py            # 터미널에 표 출력
    python3 tft_view.py --md       # 마크다운 (tft_set17.md)
    python3 tft_view.py --json     # JSON (tft_set17.json)
    python3 tft_view.py --refresh  # 매핑 캐시 무시하고 재다운로드
"""
import argparse
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DDATA = os.path.join(HERE, "TFT_DDragon", "data", "ko_KR")
SET = 17
CDN = "https://game.gtimg.cn/images/lol/act/img/tft/js"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


# 실제 상점 챔피언이 아닌 특수 유닛 마커 (소환수/가짜유닛/적대/클론 등)
SPECIAL = ("_TraitClone", "_FakeUnit", "_Enemy_", "_PVE_", "_Summon", "Tutorial", "Timebreaker", "_Core")


def is_real(cid):
    return not any(s in cid for s in SPECIAL)


def load_local():
    """패치 17.9 로컬 한국어 데이터에서 현재 세트 챔피언/시너지 추출."""
    champs = json.load(open(os.path.join(DDATA, "champion.json")))["data"]
    traits = json.load(open(os.path.join(DDATA, "trait.json")))["data"]
    tag = f"TFTSet{SET}/"
    champ = {v["id"]: v for k, v in champs.items() if tag in k and is_real(v["id"])}
    trait = {v["id"]: v for k, v in traits.items() if v["id"].startswith(f"TFT{SET}_")}
    return champ, trait


def load_mapping(refresh=False):
    """챔피언->시너지 매핑 로드 (캐시 우선, 없으면 CDN에서 받아 캐시)."""
    cache = os.path.join(HERE, f"tft_mapping_{SET}.json")
    if not refresh and os.path.exists(cache):
        return json.load(open(cache))

    chess = json.loads(fetch(f"{CDN}/chess.js"))["data"]
    race = {r["raceId"]: r for r in json.loads(fetch(f"{CDN}/race.js"))["data"]}
    job = {j["jobId"]: j for j in json.loads(fetch(f"{CDN}/job.js"))["data"]}

    mapping = {}
    for c in chess:
        en = c.get("hero_EN_name", "")
        if not en.startswith(f"TFT{SET}_"):
            continue  # 소환수(골렘/크랩/더미) 등은 제외
        tids = []
        for rid in (c.get("raceIds") or "").split(","):
            r = race.get(rid.strip())
            if r:
                tids.append(r["characterid"])
        for jid in (c.get("jobIds") or "").split(","):
            j = job.get(jid.strip())
            if j:
                tids.append(j["characterid"])
        mapping[en] = tids

    json.dump(mapping, open(cache, "w"), ensure_ascii=False, indent=1)
    return mapping


def build(champ, trait, mapping):
    """챔피언 리스트 + 시너지별 요약 생성 (한국어 이름 join)."""
    rows = []
    for cid, c in champ.items():
        tids = mapping.get(cid, [])
        names = [trait[t]["name"] for t in tids if t in trait]
        rows.append({
            "id": cid,
            "name": c["name"],
            "cost": c.get("cost", 0),
            "tier": c.get("tier", 0),
            "traits": names,
            "trait_ids": tids,
        })
    rows.sort(key=lambda r: (r["cost"], r["name"]))

    # 선택형 시너지(별돌보미 등)는 "_Huntress" 같은 하위 변형 ID가 있어 베이스 ID로 묶음
    def base_id(t):
        parts = t.split("_")
        return "_".join(parts[:2]) if len(parts) >= 2 else t

    trait_summary = {}
    for t, v in trait.items():
        trait_summary.setdefault(base_id(t), {"name": v["name"], "count": 0})
    for r in rows:
        for t in r["trait_ids"]:
            b = base_id(t)
            if b in trait_summary:
                trait_summary[b]["count"] += 1
    trait_summary = [
        {"id": b, **s} for b, s in sorted(trait_summary.items(), key=lambda kv: (-kv[1]["count"], kv[1]["name"]))
        if s["count"] > 0
    ]
    return rows, trait_summary


def disp_width(s):
    """한글/풀width 문자 2로 치환한 표시 폭 (정렬용)."""
    w = 0
    for ch in s:
        w += 2 if ord(ch) > 0x2E7F else 1
    return w


def pad(s, width):
    return s + " " * (width - disp_width(s))


def print_table(rows, trait_summary):
    print(f"\n=== Set {SET} 챔피언 ({len(rows)}명) ===\n")
    cost_w = 4
    name_w = max(disp_width(r["name"]) for r in rows)
    cost_w = max(disp_width(str(r["cost"])) for r in rows)
    header = pad("코스트", cost_w) + "  " + pad("챔피언", name_w) + "  시너지"
    print(header)
    print("-" * disp_width(header))
    for r in rows:
        line = pad(str(r["cost"]), cost_w) + "  " + pad(r["name"], name_w) + "  " + " · ".join(r["traits"])
        print(line)

    print(f"\n=== 시너지별 챔피언 수 ({len(trait_summary)}개) ===\n")
    tw = max(disp_width(t["name"]) for t in trait_summary)
    print(pad("시너지", tw) + "   수")
    print("-" * (tw + 5))
    for t in trait_summary:
        print(pad(t["name"], tw) + f"   {t['count']}")
    print()


def to_markdown(rows, trait_summary):
    out = [f"# TFT Set {SET} (패치 17.9) — 챔피언 & 시너지", ""]
    out += ["## 챔피언", "", f"| 코스트 | 챔피언 | 시너지 |", "|---|---|---|"]
    for r in rows:
        out.append(f"| {r['cost']} | {r['name']} | {', '.join(r['traits'])} |")
    out += ["", "## 시너지 (챔피언 수)", "", "| 시너지 | 챔피언 수 |", "|---|---|"]
    for t in trait_summary:
        out.append(f"| {t['name']} | {t['count']} |")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description="TFT Set 17 한국어 챔피언/시너지 뷰어")
    ap.add_argument("--md", action="store_true", help="마크다운 파일 출력")
    ap.add_argument("--json", action="store_true", help="JSON 파일 출력")
    ap.add_argument("--refresh", action="store_true", help="매핑 캐시 무시")
    args = ap.parse_args()

    champ, trait = load_local()
    mapping = load_mapping(refresh=args.refresh)
    rows, trait_summary = build(champ, trait, mapping)

    if args.md:
        p = os.path.join(HERE, f"tft_set{SET}.md")
        open(p, "w").write(to_markdown(rows, trait_summary))
        print(f"[saved] {p}", file=sys.stderr)
    if args.json:
        p = os.path.join(HERE, f"tft_set{SET}.json")
        json.dump({"set": SET, "patch": "17.9", "champions": rows,
                   "traits": trait_summary}, open(p, "w"), ensure_ascii=False, indent=1)
        print(f"[saved] {p}", file=sys.stderr)

    print_table(rows, trait_summary)


if __name__ == "__main__":
    main()
