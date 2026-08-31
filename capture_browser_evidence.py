"""Playwright Real Browser Verification & Screenshot Evidence Generator for TFT Decision Assistant Web v1.1."""
import json
import os
import sys
import time
import subprocess
import requests
from playwright.sync_api import sync_playwright

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = _HERE
EVIDENCE_DIR = os.path.join(_REPO, "data", "decision_assistant", "evidence", "browser")
os.makedirs(EVIDENCE_DIR, exist_ok=True)

SERVER_PORT = 8000
SERVER_URL = f"http://127.0.0.1:{SERVER_PORT}"


def wait_for_server(timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{SERVER_URL}/api/data/champions")
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def run_browser_verification():
    print("=" * 80)
    print("[*] LAUNCHING REAL BROWSER (PLAYWRIGHT) FOR TFT DECISION ASSISTANT v1.1")
    print("=" * 80)

    # 1. Start Server Process in background if not already running
    server_process = None
    if not wait_for_server(1):
        print(f"[+] Starting Decision Assistant server on port {SERVER_PORT}...")
        server_process = subprocess.Popen(
            [sys.executable, "run_decision_assistant.py", "--host", "127.0.0.1", "--port", str(SERVER_PORT), "--no-browser"],
            cwd=_REPO,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        assert wait_for_server(15), "Failed to start web server."
    print("[+] Server is responsive at " + SERVER_URL)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Set standard 1920x1080 viewport
        page = browser.new_page(viewport={"width": 1920, "height": 1080})

        # ----------------------------------------------------------------------
        # Screenshot 01: Initial Load & Status Bar
        # ----------------------------------------------------------------------
        print("\n[Step 1] Loading initial web assistant page...")
        page.goto(SERVER_URL)
        page.wait_for_selector("#top-status-bar")
        page.wait_for_selector("#champion-pool-grid .champ-card-mini")
        time.sleep(0.5)
        
        shot1 = os.path.join(EVIDENCE_DIR, "01_initial.png")
        page.screenshot(path=shot1, full_page=True)
        print(f"  [+] Saved 01_initial.png to {shot1}")

        # ----------------------------------------------------------------------
        # Screenshot 02: HP, Gold, Stage, Level Manual Input & Status Bar Sync
        # ----------------------------------------------------------------------
        print("\n[Step 2] Inputting HP=42, Gold=38, Stage=4-2, Level=7, XP=18...")
        page.fill("#input-stage", "4-2")
        page.fill("#input-hp", "42")
        page.fill("#input-gold", "38")
        page.fill("#input-level", "7")
        page.fill("#input-xp", "18")
        page.dispatch_event("#input-stage", "input")
        page.dispatch_event("#input-hp", "input")
        page.dispatch_event("#input-gold", "input")
        page.dispatch_event("#input-level", "input")
        page.dispatch_event("#input-xp", "input")
        time.sleep(0.3)

        # Assert status bar reflects values immediately
        assert page.text_content("#top-bar-stage").strip() == "4-2"
        assert page.text_content("#top-bar-hp").strip() == "42"
        assert page.text_content("#top-bar-gold").strip() == "38"
        assert page.text_content("#top-bar-level").strip() == "7"
        assert page.text_content("#top-bar-xp").strip() == "18"
        print("  [+] Top Status Bar verified live-synced in real-time!")

        shot2 = os.path.join(EVIDENCE_DIR, "02_hp_gold.png")
        page.screenshot(path=shot2, full_page=True)
        print(f"  [+] Saved 02_hp_gold.png to {shot2}")

        # ----------------------------------------------------------------------
        # Screenshot 03: Champion Pool & Cost Filters
        # ----------------------------------------------------------------------
        print("\n[Step 3] Testing Champion Pool cost filters...")
        page.click(".filter-pill.cost-3")
        time.sleep(0.3)
        shot3 = os.path.join(EVIDENCE_DIR, "03_champion_pool.png")
        page.screenshot(path=shot3, full_page=True)
        print(f"  [+] Saved 03_champion_pool.png to {shot3}")

        # Reset filter to ALL
        page.click(".filter-pill[data-cost='all']")
        time.sleep(0.2)

        # ----------------------------------------------------------------------
        # Screenshot 04: Fast Click-to-Add to Board, Bench, and Shop
        # ----------------------------------------------------------------------
        print("\n[Step 4] Clicking champions to add to Board, Bench, and Shop...")
        # Add Diana to Board
        page.click("#tab-target-board")
        page.click("#champion-pool-grid .champ-card-mini:has-text('Diana')")
        # Add Akali to Board
        page.click("#champion-pool-grid .champ-card-mini:has-text('Akali')")
        
        # Upgrade Diana to 2-Star
        page.click("#board-units-chips .unit-chip-item:has-text('Diana') .star-tag:has-text('2★')")

        # Add Lux to Bench
        page.click("#tab-target-bench")
        page.click("#champion-pool-grid .champ-card-mini:has-text('Lux')")

        # Fill Shop slots
        page.click("#tab-target-shop")
        page.click("#shop-slots-container .shop-slot-btn:nth-child(1)")
        page.click("#champion-pool-grid .champ-card-mini:has-text('Diana')")
        page.click("#shop-slots-container .shop-slot-btn:nth-child(3)")
        page.click("#champion-pool-grid .champ-card-mini:has-text('Akali')")
        page.click("#shop-slots-container .shop-slot-btn:nth-child(4)")
        page.click("#champion-pool-grid .champ-card-mini:has-text('Yunara')")

        time.sleep(0.3)
        shot4 = os.path.join(EVIDENCE_DIR, "04_board_bench_shop.png")
        page.screenshot(path=shot4, full_page=True)
        print(f"  [+] Saved 04_board_bench_shop.png to {shot4}")

        # ----------------------------------------------------------------------
        # Screenshot 05: Decision Engine Analysis & Recommendation
        # ----------------------------------------------------------------------
        print("\n[Step 5] Clicking [ANALYZE TURN] to execute Frozen DecisionEngine...")
        page.click("#btn-analyze")
        page.wait_for_selector("#decision-active-content:not(.hidden)")
        time.sleep(0.5)

        rec_action = page.text_content("#rec-action-name").strip()
        gap_text = page.text_content("#rec-gap-badge").strip()
        dir_now = page.text_content("#dir-now-text").strip()
        print(f"  [+] Recommendation: {rec_action} ({gap_text})")
        print(f"  [+] Direction: {dir_now}")

        shot5 = os.path.join(EVIDENCE_DIR, "05_recommendation.png")
        page.screenshot(path=shot5, full_page=True)
        print(f"  [+] Saved 05_recommendation.png to {shot5}")

        # ----------------------------------------------------------------------
        # Screenshot 06: Save Turn & Copy Previous Turn Workflow
        # ----------------------------------------------------------------------
        print("\n[Step 6] Saving turn and testing [COPY PREVIOUS TURN]...")
        # Save Turn 4-2
        page.click("#btn-save-turn")
        time.sleep(0.3)

        # Copy Previous
        page.click("#btn-copy-prev")
        time.sleep(0.3)
        # Edit HP to 32 (-10) and Gold to 30 (-8) for Turn 4-3
        page.fill("#input-hp", "32")
        page.fill("#input-gold", "30")
        page.dispatch_event("#input-hp", "input")
        page.dispatch_event("#input-gold", "input")
        time.sleep(0.2)

        # Analyze Turn 4-3
        page.click("#btn-analyze")
        time.sleep(0.5)

        shot6 = os.path.join(EVIDENCE_DIR, "06_copy_previous.png")
        page.screenshot(path=shot6, full_page=True)
        print(f"  [+] Saved 06_copy_previous.png to {shot6}")

        # ----------------------------------------------------------------------
        # Screenshot 07: Video Assistant & Timestamp Checkpoint
        # ----------------------------------------------------------------------
        print("\n[Step 7] Opening Video Assistant modal...")
        page.click("#btn-toggle-video")
        page.wait_for_selector("#video-assistant-modal:not(.hidden)")
        time.sleep(0.5)

        shot7 = os.path.join(EVIDENCE_DIR, "07_video_checkpoint.png")
        page.screenshot(path=shot7, full_page=True)
        print(f"  [+] Saved 07_video_checkpoint.png to {shot7}")

        page.click("#btn-close-video-modal")
        time.sleep(0.2)

        # ----------------------------------------------------------------------
        # Screenshot 08: Blind Review Mode
        # ----------------------------------------------------------------------
        print("\n[Step 8] Testing Blind Review Mode...")
        page.click("#btn-toggle-blind")
        page.click("#btn-analyze")
        page.wait_for_selector("#blind-mode-banner:not(.hidden)")
        time.sleep(0.3)
        # Select human preferred action = ROLL
        page.click(".btn-pref[data-pref='ROLL']")
        time.sleep(0.3)

        shot8 = os.path.join(EVIDENCE_DIR, "08_blind_review.png")
        page.screenshot(path=shot8, full_page=True)
        print(f"  [+] Saved 08_blind_review.png to {shot8}")

        # Reveal
        page.click("#btn-reveal-engine")
        time.sleep(0.3)

        # ----------------------------------------------------------------------
        # Screenshot 09: Saved Session & Human Feedback
        # ----------------------------------------------------------------------
        print("\n[Step 9] Recording Human Feedback [QUESTIONABLE] and saving session...")
        page.click(".btn-fb[data-fb='QUESTIONABLE']")
        page.fill("#input-turn-notes", "Tested in real browser with full Set 18 roster")
        page.click("#btn-save-turn")
        time.sleep(0.3)

        shot9 = os.path.join(EVIDENCE_DIR, "09_saved_session.png")
        page.screenshot(path=shot9, full_page=True)
        print(f"  [+] Saved 09_saved_session.png to {shot9}")

        # ----------------------------------------------------------------------
        # Screenshot 10: Browser Reload & State Persistence
        # ----------------------------------------------------------------------
        print("\n[Step 10] Reloading browser and verifying session recovery...")
        page.reload()
        page.wait_for_selector("#top-status-bar")
        time.sleep(0.5)

        shot10 = os.path.join(EVIDENCE_DIR, "10_reload.png")
        page.screenshot(path=shot10, full_page=True)
        print(f"  [+] Saved 10_reload.png to {shot10}")

        browser.close()

    if server_process:
        server_process.terminate()

    print("\n" + "=" * 80)
    print(f"[SUCCESS] ALL 10 REAL SCREENSHOT ARTIFACTS CAPTURED IN: {EVIDENCE_DIR}")
    print("=" * 80)


if __name__ == "__main__":
    run_browser_verification()
