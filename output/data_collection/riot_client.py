#!/usr/bin/env python3
"""Riot API 클라이언트 모듈 (TFT League-V1, Match-V1).

보안 원칙:
- API 키는 절대 코드/로그/예외 메시지에 평문으로 노출하지 않음
- 반드시 환경변수 RIOT_API_KEY (또는 .env)에서만 로드
- URL/헤더 에러 로깅 시 키 마스킹

Rate Limit 정책 (개발 키 기준):
- 20 req / 1 sec, 100 req / 120 sec (2 min)
- 요청 간 최소 지연(기본 1.25초) 및 슬라이딩 윈도우 기반 속도 조절
- HTTP 429 수신 시 Retry-After 헤더 기반 지수 백오프 및 재시도
"""
import collections
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger("RiotClient")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(asctime)s][%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def _load_env_file():
    """상위 디렉토리의 .env 파일을 찾아 환경변수에 로드 (외부 라이브러리 의존성 없음)."""
    cur = os.path.dirname(os.path.abspath(__file__))
    for _ in range(4):
        env_path = os.path.join(cur, ".env")
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, _, v = line.partition("=")
                        k = k.strip()
                        v = v.strip().strip("'").strip('"')
                        if k and k not in os.environ:
                            os.environ[k] = v
            except Exception:
                pass
            break
        cur = os.path.dirname(cur)


class RiotClient:
    """TFT API 통신 및 Rate Limiting을 담당하는 클라이언트."""

    def __init__(
        self,
        api_key: str = None,
        region: str = "kr",
        routing: str = "asia",
        min_request_interval: float = 1.25,
        max_retries: int = 5,
    ):
        _load_env_file()
        self._api_key = api_key or os.environ.get("RIOT_API_KEY")
        if not self._api_key or not isinstance(self._api_key, str):
            raise ValueError(
                "RIOT_API_KEY 환경변수가 설정되지 않았습니다. "
                ".env 파일 또는 환경변수에 유효한 Riot API 키를 지정하세요."
            )

        self.region = region.lower()
        self.routing = routing.lower()
        self.min_request_interval = max(0.1, min_request_interval)
        self.max_retries = max_retries

        self._last_request_time = 0.0
        # 120초 윈도우 내 요청 타임스탬프 기록
        self._request_history = collections.deque()

    def __repr__(self) -> str:
        return f"<RiotClient region='{self.region}' routing='{self.routing}'>"

    def _mask_text(self, text: str) -> str:
        """텍스트 내 API 키를 마스킹."""
        if not text:
            return ""
        if self._api_key:
            text = text.replace(self._api_key, "***MASKED_KEY***")
        # RGAPI 정규식 패턴 마스킹
        text = re.sub(r"RGAPI-[0-9a-fA-F\-]{36}", "***MASKED_KEY***", text)
        return text

    def _wait_for_rate_limit(self):
        """요청 간격 및 슬라이딩 윈도우 기반 rate limit 대기."""
        now = time.time()

        # 1. 이전 요청과의 최소 간격 준수
        elapsed = now - self._last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            time.sleep(sleep_time)
            now = time.time()

        # 2. 120초 윈도우 정리 (최대 100 req / 120s)
        cutoff_120s = now - 120.0
        while self._request_history and self._request_history[0] < cutoff_120s:
            self._request_history.popleft()

        if len(self._request_history) >= 95:  # 여유 버퍼 두고 대기
            oldest = self._request_history[0]
            wait_120 = 120.0 - (now - oldest) + 0.5
            if wait_120 > 0:
                logger.info(f"Rate limit 윈도우 보호를 위해 {wait_120:.2f}초 대기합니다...")
                time.sleep(wait_120)
                now = time.time()

        self._last_request_time = now
        self._request_history.append(now)

    def request(self, url: str, params: dict = None) -> dict | list:
        """Rate limit 및 429 재시도를 포함한 HTTP GET 요청 수행."""
        if params:
            query = urllib.parse.urlencode(params)
            sep = "&" if "?" in url else "?"
            full_url = f"{url}{sep}{query}"
        else:
            full_url = url

        headers = {
            "X-Riot-Token": self._api_key,
            "User-Agent": "TFT-Set17-DataCollector/1.0",
            "Accept": "application/json",
        }

        for attempt in range(1, self.max_retries + 1):
            self._wait_for_rate_limit()

            req = urllib.request.Request(full_url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = resp.read().decode("utf-8")
                    return json.loads(data)
            except urllib.error.HTTPError as e:
                masked_url = self._mask_text(full_url)
                if e.code == 429:
                    # 429 Rate Limit
                    retry_after_hdr = e.headers.get("Retry-After")
                    try:
                        retry_after = float(retry_after_hdr) if retry_after_hdr else (2.0 ** attempt)
                    except ValueError:
                        retry_after = 5.0
                    wait_sec = retry_after + 0.5
                    logger.warning(
                        f"HTTP 429 Rate Limit 감지됨 ({masked_url}). "
                        f"Retry-After={retry_after}s -> {wait_sec:.1f}초 대기 후 재시도 (시도 {attempt}/{self.max_retries})"
                    )
                    time.sleep(wait_sec)
                    continue
                elif e.code in (500, 502, 503, 504):
                    # 서버 오류 시 지수 백오프
                    wait_sec = 2.0 * attempt
                    logger.warning(f"HTTP {e.code} 서버 에러 ({masked_url}). {wait_sec:.1f}초 후 재시도 (시도 {attempt}/{self.max_retries})")
                    time.sleep(wait_sec)
                    continue
                else:
                    err_body = ""
                    try:
                        err_body = self._mask_text(e.read().decode("utf-8", "replace"))
                    except Exception:
                        pass
                    raise RuntimeError(
                        f"Riot API 요청 실패 (HTTP {e.code}): {masked_url} - {err_body}"
                    ) from None
            except Exception as e:
                masked_err = self._mask_text(str(e))
                if attempt == self.max_retries:
                    raise RuntimeError(f"Riot API 연결 오류: {masked_err}") from None
                time.sleep(1.5 * attempt)

        raise RuntimeError(f"최대 재시도 횟수({self.max_retries})를 초과하여 요청 실패: {self._mask_text(full_url)}")

    def get_top_puuids(self, tier: str = "challenger", limit: int = None) -> list[str]:
        """지정 리그(challenger/grandmaster)의 상위 랭커 PUUID 목록을 LP 내림차순으로 반환."""
        tier = tier.lower()
        if tier not in ("challenger", "grandmaster", "master"):
            raise ValueError(f"지원하지 않는 리그 티어입니다: {tier}")

        url = f"https://{self.region}.api.riotgames.com/tft/league/v1/{tier}"
        logger.info(f"[{self.region.upper()}] {tier.upper()} 리그 랭커 목록 요청 중...")
        data = self.request(url)

        entries = data.get("entries", [])
        # LP 기준 내림차순 정렬
        entries.sort(key=lambda x: x.get("leaguePoints", 0), reverse=True)

        puuids = [e["puuid"] for e in entries if "puuid" in e]
        if limit:
            puuids = puuids[:limit]

        logger.info(f"{tier.upper()} 랭커 {len(puuids)}명 PUUID 확보 완료 (최고 LP: {entries[0].get('leaguePoints', 0) if entries else 0})")
        return puuids

    def get_match_ids_by_puuid(self, puuid: str, count: int = 20) -> list[str]:
        """PUUID 기준 최근 매치 ID 목록을 반환."""
        if not puuid or not isinstance(puuid, str):
            raise ValueError(f"유효하지 않은 PUUID입니다: {puuid!r}")

        url = f"https://{self.routing}.api.riotgames.com/tft/match/v1/matches/by-puuid/{puuid}/ids"
        data = self.request(url, params={"count": count})
        if isinstance(data, list):
            return data
        return []
