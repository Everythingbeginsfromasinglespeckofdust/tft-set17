#!/usr/bin/env python3
"""TFT Set 17 상점 드랍풀 크기 제공 모듈.

K_c = 코스트 c의 챔피언 1종이 드랍풀에서 가진 카피 수.
    {1: 29, 2: 22, 3: 18, 4: 10, 5: 9}
외부(실게임) 검증으로 확정된 값이며, DDragon/CDN 데이터에는 존재하지 않는
클라이언트 상수이므로 pool_sizes.json에 직접 저장하고 이 모듈은
load_pool_sizes()로 JSON에서 로드한다. (수정 시 pool_sizes.json만 갱신.)
"""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
POOL_SIZES_JSON = os.path.join(_HERE, "pool_sizes.json")
COSTS = (1, 2, 3, 4, 5)


def load_pool_sizes(path: str = POOL_SIZES_JSON) -> dict:
    """pool_sizes.json에서 코스트별 카피 수를 {int: int}로 로드.

    Returns:
        {1: 29, 2: 22, 3: 18, 4: 10, 5: 9} 형태의 dict.

    Raises:
        ValueError: 코스트 1~5가 빠지거나 값이 양의 정수가 아니면.
    """
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    table = raw.get("copies_per_champion_by_cost", {})
    out = {}
    for cost in COSTS:
        try:
            value = table[str(cost)]
        except KeyError:
            raise ValueError(f"pool_sizes.json에 {cost}코스트 항목이 없습니다: {sorted(table)}")
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"{cost}코스트 풀사이즈는 양의 정수여야 합니다: {value!r}")
        out[cost] = value
    return out


if __name__ == "__main__":
    sizes = load_pool_sizes()
    print(sizes)
