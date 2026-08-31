"""TFT Decision Assistant FastAPI Web Server v1.1.

Provides REST API endpoints and static file serving for Human Input Turn-by-Turn Decision Assistant.
"""
from __future__ import annotations
import glob
import hashlib
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, "..", ".."))
_REPO = os.path.abspath(os.path.join(_SRC, ".."))

if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.domain.game_state import GameState
from tft.decision.engine import DecisionEngine
from tft.decision.scorer import DEFAULT_DECISION_CONFIG
from tft.calibration.integration.adapter import DecisionCalibrationAdapter, CalibrationMode
from tft.webapp.adapter import (
    HumanInputDTO,
    GameStateBuilder,
    DecisionPresenter,
    TurnDiffCalculator,
    SET18_CHAMPIONS,
    SET18_ITEMS,
    _KO_NAME_MAP,
    _SET18_CHAMPIONS_PATH,
    _SET18_ITEMS_PATH
)

# Paths
_DATA_DIR = os.path.join(_REPO, "data", "decision_assistant")
_SESSIONS_DIR = os.path.join(_DATA_DIR, "sessions")
_RECORDINGS_DIR = r"C:\Users\mrjdh\AppData\Roaming\TFTAcademy\tft-recordings"
_FRONTEND_DIR = os.path.join(_HERE, "frontend")
_DDRAGON_CHAMPS_DIR = os.path.join(_REPO, "data", "sets", "set18", "raw", "ddragon", "champions")

os.makedirs(_SESSIONS_DIR, exist_ok=True)

# FastAPI App
app = FastAPI(
    title="TFT Decision Assistant API",
    description="Human Input GameState Decision Assistant for TFT Set 18",
    version="1.1.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Engine & Adapter Singletons (Frozen Core)
_engine = DecisionEngine(config=DEFAULT_DECISION_CONFIG)
_calib_adapter = DecisionCalibrationAdapter(engine=_engine)


# ==============================================================================
# 1. Reference Data Endpoints
# ==============================================================================

@app.get("/api/data/champions")
def get_champions() -> List[Dict[str, Any]]:
    """Return all 64 Set 18 normalized champions sorted by cost then Korean name."""
    if not os.path.exists(_SET18_CHAMPIONS_PATH):
        return []
    with open(_SET18_CHAMPIONS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    for c in data:
        name = c.get("name", "")
        char_id = c.get("character_id", "").lower()
        c["name_ko"] = _KO_NAME_MAP.get(char_id) or _KO_NAME_MAP.get(name.lower()) or name
    data.sort(key=lambda c: (c.get("cost", 1), c.get("name_ko", c.get("name", ""))))
    return data


@app.get("/api/data/items")
def get_items() -> List[Dict[str, Any]]:
    """Return normalized items catalog."""
    if not os.path.exists(_SET18_ITEMS_PATH):
        return []
    with open(_SET18_ITEMS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


@app.get("/api/data/augments")
def get_augments() -> List[Dict[str, Any]]:
    """Return normalized augments catalog."""
    p = os.path.join(_REPO, "data", "sets", "set18", "normalized", "augments.json")
    if not os.path.exists(p):
        return []
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


# ==============================================================================
# 2. Decision Engine Analysis Endpoint
# ==============================================================================

@app.post("/api/validate")
def validate_draft_state(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Real-time validation & completeness calculation on draft state."""
    dto = HumanInputDTO.from_dict(payload)
    is_valid, errors = GameStateBuilder.validate_input(dto)
    completeness = GameStateBuilder.calculate_completeness(dto)
    return {
        "is_valid": is_valid,
        "errors": errors,
        "completeness": completeness
    }


@app.post("/api/decide")
def analyze_and_decide(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate Human Input DTO, build GameState, execute DecisionEngine and return Recommendation."""
    try:
        dto = HumanInputDTO.from_dict(payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid payload format: {str(e)}")

    # Domain Validation
    is_valid, errors = GameStateBuilder.validate_input(dto)
    if not is_valid:
        raise HTTPException(
            status_code=422,
            detail={"message": "GameState validation failed", "errors": errors}
        )

    # Build GameState
    state = GameStateBuilder.build_game_state(dto)

    # Calibration Mode
    calib_mode_str = dto.calibration_mode.upper()
    calib_mode = CalibrationMode.OFF
    if calib_mode_str == "ON":
        calib_mode = CalibrationMode.ON
    elif calib_mode_str == "SHADOW":
        calib_mode = CalibrationMode.SHADOW

    # Execute Frozen Core
    base_rec = _engine.decide(state)
    calib_res = _calib_adapter.decide(state, override_mode=calib_mode)

    # Format Presentation Response
    response = DecisionPresenter.format_decision_response(
        state=state,
        rec=base_rec,
        calib_res=calib_res,
        calib_mode=calib_mode_str
    )
    return response


@app.post("/api/diff")
def compute_turn_diff(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Compute state delta between previous and current turn."""
    prev_raw = payload.get("previous_state", {})
    curr_raw = payload.get("current_state", {})
    prev_dto = HumanInputDTO.from_dict(prev_raw)
    curr_dto = HumanInputDTO.from_dict(curr_raw)
    diff = TurnDiffCalculator.compute_turn_diff(prev_dto, curr_dto)
    return diff


# ==============================================================================
# 3. Local Video Files Streaming & Linking
# ==============================================================================

@app.get("/api/videos")
def list_local_videos() -> List[Dict[str, Any]]:
    """List MP4 recording files available in the user's recordings directory."""
    if not os.path.exists(_RECORDINGS_DIR):
        return []

    files = glob.glob(os.path.join(_RECORDINGS_DIR, "*.mp4"))
    videos = []
    for fp in files:
        fname = os.path.basename(fp)
        sz_bytes = os.path.getsize(fp)
        videos.append({
            "filename": fname,
            "path": fp,
            "size_bytes": sz_bytes,
            "size_mb": round(sz_bytes / (1024 * 1024), 1)
        })
    videos.sort(key=lambda x: x["filename"], reverse=True)
    return videos


@app.get("/api/videos/{video_filename}/stream")
def stream_video(video_filename: str, request: Request):
    """Stream MP4 video with HTTP Range header support for seeking in HTML5 player."""
    video_path = os.path.join(_RECORDINGS_DIR, video_filename)
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found")

    file_size = os.path.getsize(video_path)
    range_header = request.headers.get("Range")

    if not range_header:
        def iterfile():
            with open(video_path, "rb") as f:
                while chunk := f.read(65536 * 16):
                    yield chunk
        return StreamingResponse(
            iterfile(),
            status_code=200,
            media_type="video/mp4",
            headers={"Content-Length": str(file_size), "Accept-Ranges": "bytes"}
        )

    # Parse Range: bytes=START-END
    range_match = range_header.replace("bytes=", "").split("-")
    start = int(range_match[0]) if range_match[0] else 0
    end = int(range_match[1]) if len(range_match) > 1 and range_match[1] else file_size - 1
    end = min(end, file_size - 1)
    chunk_size = end - start + 1

    def iterfile_range():
        with open(video_path, "rb") as f:
            f.seek(start)
            bytes_left = chunk_size
            while bytes_left > 0:
                read_size = min(65536 * 16, bytes_left)
                data = f.read(read_size)
                if not data:
                    break
                bytes_left -= len(data)
                yield data

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(chunk_size),
        "Content-Type": "video/mp4"
    }
    return StreamingResponse(iterfile_range(), status_code=206, headers=headers)


# ==============================================================================
# 4. Session Persistence & Checkpoints
# ==============================================================================

def get_session_dir(session_id: str) -> str:
    s_dir = os.path.join(_SESSIONS_DIR, session_id)
    os.makedirs(s_dir, exist_ok=True)
    return s_dir


@app.get("/api/sessions")
def list_sessions() -> List[str]:
    """List all saved sessions."""
    if not os.path.exists(_SESSIONS_DIR):
        return []
    return [d for d in os.listdir(_SESSIONS_DIR) if os.path.isdir(os.path.join(_SESSIONS_DIR, d))]


@app.get("/api/sessions/{session_id}")
def load_session(session_id: str) -> Dict[str, Any]:
    """Load session data and turns history."""
    s_dir = get_session_dir(session_id)
    manifest_path = os.path.join(s_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        return {"session_id": session_id, "turns": []}

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Load individual turns
    turns = []
    turns_path = os.path.join(s_dir, "turns.jsonl")
    if os.path.exists(turns_path):
        with open(turns_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    turns.append(json.loads(line))

    manifest["turns"] = turns
    return manifest


@app.post("/api/sessions/{session_id}/turns")
def save_turn(session_id: str, turn_data: Dict[str, Any]) -> Dict[str, Any]:
    """Append a turn checkpoint to session."""
    s_dir = get_session_dir(session_id)
    turns_path = os.path.join(s_dir, "turns.jsonl")
    manifest_path = os.path.join(s_dir, "manifest.json")

    turn_idx = 0
    if os.path.exists(turns_path):
        with open(turns_path, "r", encoding="utf-8") as f:
            turn_idx = sum(1 for l in f if l.strip())

    turn_data["turn_index"] = turn_idx
    turn_data["timestamp_saved"] = time.time()

    with open(turns_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(turn_data, ensure_ascii=False) + "\n")

    # Update manifest
    manifest = {
        "session_id": session_id,
        "last_updated": time.time(),
        "total_turns": turn_idx + 1
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return {"status": "success", "turn_index": turn_idx}


@app.get("/api/export/dataset")
def export_dataset(session_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Export turns dataset across sessions in backtest JSONL format."""
    dataset = []
    sessions_to_scan = [session_id] if session_id else list_sessions()

    for s_id in sessions_to_scan:
        s_dir = os.path.join(_SESSIONS_DIR, s_id)
        turns_path = os.path.join(s_dir, "turns.jsonl")
        if os.path.exists(turns_path):
            with open(turns_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        t_data = json.loads(line)
                        dataset.append({
                            "session_id": s_id,
                            "turn_index": t_data.get("turn_index"),
                            "stage_round": t_data.get("state", {}).get("stage_round"),
                            "video_timestamp_sec": t_data.get("state", {}).get("video_timestamp_sec"),
                            "recommended_action": t_data.get("decision", {}).get("recommended_action"),
                            "action_score_gap": t_data.get("decision", {}).get("action_score_gap"),
                            "actual_player_action": t_data.get("actual_player_action"),
                            "human_preferred_action": t_data.get("human_preferred_action"),
                            "human_feedback": t_data.get("human_feedback"),
                            "human_judgment": t_data.get("human_judgment") or t_data.get("human_feedback"),
                            "notes": t_data.get("notes"),
                            "state": t_data.get("state")
                        })
    return dataset


# ==============================================================================
# 5. Static Web UI & Image Assets Mount
# ==============================================================================

if os.path.exists(_DDRAGON_CHAMPS_DIR):
    app.mount("/img/champion", StaticFiles(directory=_DDRAGON_CHAMPS_DIR), name="champion_images")

if os.path.exists(_FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=_FRONTEND_DIR), name="static")

    @app.get("/")
    def serve_frontend_index():
        return FileResponse(os.path.join(_FRONTEND_DIR, "index.html"))
