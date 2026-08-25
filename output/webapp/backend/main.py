#!/usr/bin/env python3
"""TFT Set 17 대시보드 웹 애플리케이션 백엔드 API (FastAPI).

통합 모듈:
- output/dashboard/report.py (generate_dashboard_report 재사용)
- output/economy/board_power.py (_load_champions_db, _load_items_db)

엔드포인트:
- POST /api/report: 게임 상태를 전달받아 5단계 통합 리포트 반환
- GET  /api/champions: 챔피언 참조 데이터 목록 반환
- GET  /api/items: 아이템(부품/완성품) 참조 데이터 반환
- GET  /api/scenarios: 예시 시나리오 3종 반환
"""
import json
import os
import sys
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_HERE = os.path.dirname(os.path.abspath(__file__))
_WEBAPP = os.path.dirname(_HERE)
_OUTPUT = os.path.dirname(_WEBAPP)
_DASHBOARD = os.path.join(_OUTPUT, "dashboard")
_ECONOMY = os.path.join(_OUTPUT, "economy")
_FRONTEND = os.path.join(_WEBAPP, "frontend")

for p in [_DASHBOARD, _ECONOMY, _OUTPUT]:
    if p not in sys.path:
        sys.path.insert(0, p)

import board_power as bp
import report as rep

app = FastAPI(
    title="TFT Set 17 Dashboard API",
    description="TFT Set 17 경제 및 보드 파워 통합 분석 API",
    version="1.0.0",
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/champions")
def get_champions() -> List[Dict[str, Any]]:
    """Set 17 챔피언 목록 및 코스트/시너지 정보 반환."""
    db = bp._load_champions_db()
    sorted_champs = sorted(db.values(), key=lambda c: (c["cost"], c["name"]))
    return sorted_champs


@app.get("/api/items")
def get_items() -> Dict[str, List[str]]:
    """기본 부품 및 완성 아이템 목록 반환."""
    components, completed = bp._load_items_db()
    return {
        "basic_components": sorted(list(components)),
        "completed_items": sorted(list(completed)),
    }


@app.get("/api/scenarios")
def get_example_scenarios() -> List[Dict[str, Any]]:
    """사전 정의된 3가지 예시 시나리오 반환."""
    scenarios_dir = os.path.join(_DASHBOARD, "example_scenarios")
    scenarios = []
    if os.path.exists(scenarios_dir):
        for fname in sorted(os.listdir(scenarios_dir)):
            if fname.endswith(".json"):
                fpath = os.path.join(scenarios_dir, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    scenarios.append(json.load(f))
    return scenarios


@app.post("/api/report")
def create_report(state: Dict[str, Any]) -> Dict[str, Any]:
    """게임 상태를 입력받아 통합 리포트 생성 및 반환.
    
    도메인 모듈(board_power, strategy_comparator 등)의 유효성 검증 예외(ValueError)를
    포착하여 400 Bad Request로 변환.
    """
    try:
        report_data = rep.generate_dashboard_report(state)
        return report_data
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"리포트 생성 중 오류 발생: {str(e)}")


# 프론트엔드 정적 파일 서빙
if os.path.exists(_FRONTEND):
    app.mount("/static", StaticFiles(directory=_FRONTEND), name="static")

    @app.get("/")
    def serve_index():
        index_path = os.path.join(_FRONTEND, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"message": "Frontend index.html not found"}
