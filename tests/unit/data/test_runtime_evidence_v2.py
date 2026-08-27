"""
TFT Real Runtime Validation v2 — Unit Tests

Tests verify:
- Evidence-First checkpoint state machine
- Label contamination detection
- Domain metric independence
- Frame hash verification
- REAL_LIVE rejection when TFT client absent
- Synthetic pattern detection
- Fake checkpoint detection
- Timestamp ordering
- No synthetic fallback
"""
import hashlib, json, os, tempfile, time, uuid
import pytest
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))

from tft.vision.runtime_v2.evidence_store import (
    EvidenceStore, EvidenceCheckpoint, CaptureEvidence, PredictionEvidence,
    HumanInputEvent, DomainReview, CheckpointState, SourceType, DomainVerdict,
)
from tft.vision.runtime_v2.evidence_validator import EvidenceValidator


# ── Fixtures ────────────────────────────────────────────────────────────────

def make_real_frame(tmp_dir):
    """Create a real PNG file with known hash."""
    import io
    from PIL import Image
    img = Image.new("RGB", (100, 100), color=(128, 64, 32))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png = buf.getvalue()
    sha = hashlib.sha256(png).hexdigest()
    path = os.path.join(tmp_dir, f"frame_{uuid.uuid4().hex[:8]}.png")
    with open(path, "wb") as f_:
        f_.write(png)
    return path, sha, png


def make_capture(frame_path, frame_sha256, mono=1000.0):
    return CaptureEvidence(
        frame_path=frame_path,
        frame_sha256=frame_sha256,
        capture_timestamp_iso="2026-08-27T05:00:00Z",
        capture_monotonic=mono,
        monitor_index=1,
        resolution_w=1920, resolution_h=1080,
        window_title_sanitized="Teamfight Tactics",
    )


def make_prediction(mono=1001.0, vision_source="REAL_FRAME", base_action="ROLL", final_action="ROLL"):
    return PredictionEvidence(
        prediction_id="PRED_TEST",
        prediction_timestamp_iso="2026-08-27T05:00:01Z",
        prediction_monotonic=mono,
        git_commit="abc1234",
        vision_hash="VHASH",
        decision_hash="DHASH",
        calibration_hash="CHASH",
        calibration_source_sha256="CSRCSHA",
        vision_source=vision_source,
        base_action=base_action,
        final_action=final_action,
    )


def make_human_input(key="C", mono=1002.0, chk_id="CHK_00000", session_id="TEST"):
    return HumanInputEvent(
        input_event_id="INPUT_TEST",
        key_pressed=key,
        timestamp_iso="2026-08-27T05:00:02Z",
        timestamp_monotonic=mono,
        checkpoint_id=chk_id,
        session_id=session_id,
    )


def make_review(verdict="CORRECT", human_pref=None, blind=False, reveal_mono=None):
    return DomainReview(
        shop_verdict=verdict,
        gold_verdict=verdict,
        board_verdict=verdict,
        action_verdict=verdict,
        state_verdict=verdict,
        human_preferred_action=human_pref,
        blind_mode=blind,
        reveal_monotonic=reveal_mono,
    )


# ── Tests: CheckpointState machine ──────────────────────────────────────────

class TestCheckpointStateMachine:

    def test_valid_transition_sequence(self, tmp_path):
        fp, sha, _ = make_real_frame(str(tmp_path))
        chk = EvidenceCheckpoint("CHK_00000", "TEST", SourceType.REAL_LIVE.value)
        assert chk.state == CheckpointState.CAPTURED.value

        chk.capture = make_capture(fp, sha)
        chk.prediction = make_prediction()
        ok = chk.transition(CheckpointState.PREDICTED)
        assert ok
        assert chk.state == CheckpointState.PREDICTED.value

        ok = chk.transition(CheckpointState.AWAITING_REVIEW)
        assert ok

        chk.human_input = make_human_input()
        chk.review = make_review()
        ok = chk.transition(CheckpointState.REVIEWED)
        assert ok

        ok = chk.transition(CheckpointState.VERIFIED)
        assert ok
        assert chk.state == CheckpointState.VERIFIED.value
        assert chk.finalized_at is not None

    def test_no_skip_captured_to_verified(self, tmp_path):
        fp, sha, _ = make_real_frame(str(tmp_path))
        chk = EvidenceCheckpoint("CHK_00000", "TEST", SourceType.REAL_LIVE.value)
        chk.capture = make_capture(fp, sha)
        chk.prediction = make_prediction()
        chk.human_input = make_human_input()
        chk.review = make_review()
        # Cannot jump from CAPTURED -> VERIFIED
        ok = chk.transition(CheckpointState.VERIFIED)
        assert not ok

    def test_invalid_transition_blocked(self):
        chk = EvidenceCheckpoint("CHK_00000", "TEST", SourceType.REAL_LIVE.value)
        # Cannot go from CAPTURED -> REVIEWED (skipping PREDICTED)
        ok = chk.transition(CheckpointState.REVIEWED)
        assert not ok

    def test_no_evidence_prevents_verified(self):
        chk = EvidenceCheckpoint("CHK_00000", "TEST", SourceType.REAL_LIVE.value)
        chk.state = CheckpointState.REVIEWED.value  # force manually
        ok = chk.transition(CheckpointState.VERIFIED)
        assert not ok
        assert chk.state == CheckpointState.INVALID.value
        assert chk.invalidation_reason == "EVIDENCE_INCOMPLETE"

    def test_verified_requires_all_evidence(self, tmp_path):
        fp, sha, _ = make_real_frame(str(tmp_path))
        chk = EvidenceCheckpoint("CHK_00000", "TEST", SourceType.REAL_LIVE.value)
        # Only capture, no prediction, no human_input, no review
        chk.capture = make_capture(fp, sha)
        chk.state = CheckpointState.REVIEWED.value
        ok = chk.transition(CheckpointState.VERIFIED)
        assert not ok

    def test_no_valid_transition_from_verified(self, tmp_path):
        fp, sha, _ = make_real_frame(str(tmp_path))
        chk = EvidenceCheckpoint("CHK_00000", "TEST", SourceType.REAL_LIVE.value)
        chk.capture = make_capture(fp, sha)
        chk.prediction = make_prediction()
        chk.human_input = make_human_input()
        chk.review = make_review()
        chk.state = CheckpointState.REVIEWED.value
        chk.transition(CheckpointState.VERIFIED)
        # Nothing allowed from VERIFIED
        ok = chk.transition(CheckpointState.INVALID)
        assert not ok


# ── Tests: EvidenceStore ─────────────────────────────────────────────────────

class TestEvidenceStore:

    def test_new_checkpoint_has_unique_ids(self, tmp_path):
        store = EvidenceStore(str(tmp_path), "TEST", SourceType.REAL_LIVE)
        ids = [store.new_checkpoint().checkpoint_id for _ in range(10)]
        assert len(set(ids)) == 10

    def test_frame_save_and_hash(self, tmp_path):
        import io
        from PIL import Image
        store = EvidenceStore(str(tmp_path), "TEST", SourceType.REAL_LIVE)
        img = Image.new("RGB", (50, 50), (255, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png = buf.getvalue()
        path, sha = store.save_frame(png, "CHK_00000", "frame")
        assert os.path.exists(path)
        with open(path, "rb") as f:
            assert hashlib.sha256(f.read()).hexdigest() == sha

    def test_finalize_requires_complete_evidence(self, tmp_path):
        fp, sha, _ = make_real_frame(str(tmp_path))
        store = EvidenceStore(str(tmp_path), "TEST", SourceType.REAL_LIVE)
        chk = store.new_checkpoint()
        # Without evidence, finalize should INVALID
        ok = store.finalize_checkpoint(chk)
        assert not ok
        assert chk.state == CheckpointState.INVALID.value

    def test_finalize_with_complete_evidence(self, tmp_path):
        fp, sha, _ = make_real_frame(str(tmp_path))
        store = EvidenceStore(str(tmp_path), "TEST", SourceType.REAL_LIVE)
        chk = store.new_checkpoint()
        chk.capture = make_capture(fp, sha)
        chk.prediction = make_prediction()
        chk.human_input = make_human_input(chk_id=chk.checkpoint_id)
        chk.review = make_review()
        # Advance through state machine
        chk.transition(CheckpointState.PREDICTED)
        chk.transition(CheckpointState.AWAITING_REVIEW)
        chk.transition(CheckpointState.REVIEWED)
        ok = store.finalize_checkpoint(chk)
        assert ok
        assert chk.state == CheckpointState.VERIFIED.value

    def test_stats_counts_correctly(self, tmp_path):
        fp, sha, _ = make_real_frame(str(tmp_path))
        store = EvidenceStore(str(tmp_path), "TEST", SourceType.REAL_LIVE)
        # One valid
        chk1 = store.new_checkpoint()
        chk1.capture = make_capture(fp, sha)
        chk1.prediction = make_prediction()
        chk1.human_input = make_human_input(chk_id=chk1.checkpoint_id)
        chk1.review = make_review()
        chk1.transition(CheckpointState.PREDICTED)
        chk1.transition(CheckpointState.AWAITING_REVIEW)
        chk1.transition(CheckpointState.REVIEWED)
        store.finalize_checkpoint(chk1)
        # One invalid
        chk2 = store.new_checkpoint()
        store.finalize_checkpoint(chk2)  # invalid, no evidence
        stats = store.stats()
        assert stats["valid"] == 1
        assert stats["invalid"] == 1


# ── Tests: Label Contamination Detection ─────────────────────────────────────

class TestLabelContamination:

    def test_human_input_derive_verdict_from_key(self):
        hi = make_human_input(key="C")
        assert hi.derive_verdict() == DomainVerdict.CORRECT.value

        hi_w = make_human_input(key="W")
        assert hi_w.derive_verdict() == DomainVerdict.WRONG.value

        hi_x = make_human_input(key="X")
        assert hi_x.derive_verdict() == DomainVerdict.UNKNOWN.value

    def test_human_action_from_key_not_prediction(self):
        hi_r = make_human_input(key="R")
        assert hi_r.derive_preferred_action() == "ROLL"

        hi_l = make_human_input(key="L")
        assert hi_l.derive_preferred_action() == "LEVEL_UP"

        hi_c = make_human_input(key="C")
        assert hi_c.derive_preferred_action() is None

    def test_review_human_pref_not_auto_set(self):
        # DomainReview.human_preferred_action should default to None
        review = DomainReview()
        assert review.human_preferred_action is None

    def test_label_contamination_detected_by_validator(self, tmp_path):
        """Validator detects human_pref == final_action without action key."""
        fp, sha, _ = make_real_frame(str(tmp_path))
        chk = EvidenceCheckpoint("CHK_00000", "TEST", SourceType.REAL_LIVE.value)
        chk.capture = make_capture(fp, sha)
        chk.prediction = make_prediction(final_action="ROLL")
        # Contamination: preferred_action set to ROLL without action key (key='C')
        chk.human_input = make_human_input(key="C")
        chk.review = make_review(human_pref="ROLL")  # contaminated!
        chk.state = CheckpointState.REVIEWED.value

        validator = EvidenceValidator()
        valid, issues = validator.validate_checkpoint(chk)
        assert not valid
        assert any("LABEL_CONTAMINATION" in i for i in issues)

    def test_action_key_preferred_is_not_contamination(self, tmp_path):
        """Pressing 'R' key -> ROLL is NOT contamination even if prediction is ROLL."""
        fp, sha, _ = make_real_frame(str(tmp_path))
        chk = EvidenceCheckpoint("CHK_00000", "TEST", SourceType.REAL_LIVE.value)
        chk.capture = make_capture(fp, sha)
        chk.prediction = make_prediction(final_action="ROLL")
        chk.human_input = make_human_input(key="R")  # action key pressed
        chk.review = make_review(human_pref="ROLL")  # same but via key
        chk.state = CheckpointState.REVIEWED.value

        validator = EvidenceValidator()
        valid, issues = validator.validate_checkpoint(chk)
        # No label contamination (key was 'R' which maps to ROLL)
        contamination_issues = [i for i in issues if "LABEL_CONTAMINATION" in i]
        assert len(contamination_issues) == 0


# ── Tests: Domain Metrics Independence ───────────────────────────────────────

class TestDomainMetricsIndependence:

    def test_independent_reviews_produce_different_results(self):
        """Different per-domain verdicts should produce different metrics."""
        from tft.vision.runtime_v2.evidence_validator import EvidenceAuditResult
        r = EvidenceAuditResult()
        # Manually set different per-domain counts
        r.domain_metrics["shop"]["total"] = 10
        r.domain_metrics["shop"]["correct"] = 9
        r.domain_metrics["gold"]["total"] = 10
        r.domain_metrics["gold"]["correct"] = 8  # different
        r.domain_metrics["board"]["total"] = 10
        r.domain_metrics["board"]["correct"] = 7
        r.domain_metrics["action"]["total"] = 10
        r.domain_metrics["action"]["correct"] = 6
        assert r.shop_accuracy() != r.gold_accuracy()
        assert r.are_domain_metrics_independent()

    def test_shared_flag_detected_as_not_independent(self):
        from tft.vision.runtime_v2.evidence_validator import EvidenceAuditResult
        r = EvidenceAuditResult()
        # All same: sign of shared boolean flag
        for d in ["shop","gold","board","action"]:
            r.domain_metrics[d]["total"] = 10
            r.domain_metrics[d]["correct"] = 9
        assert not r.are_domain_metrics_independent()

    def test_evidence_backed_accuracy_uses_own_denominator(self):
        from tft.vision.runtime_v2.evidence_validator import EvidenceAuditResult
        r = EvidenceAuditResult()
        r.domain_metrics["shop"]["total"] = 20
        r.domain_metrics["shop"]["correct"] = 18
        r.domain_metrics["gold"]["total"] = 15
        r.domain_metrics["gold"]["correct"] = 15
        assert r.shop_accuracy() == pytest.approx(18/20)
        assert r.gold_accuracy() == pytest.approx(1.0)


# ── Tests: EvidenceValidator ─────────────────────────────────────────────────

class TestEvidenceValidator:

    def test_missing_frame_file_invalid(self, tmp_path):
        chk = EvidenceCheckpoint("CHK_00000", "TEST", SourceType.REAL_LIVE.value)
        chk.capture = CaptureEvidence(
            frame_path="/nonexistent/frame.png",
            frame_sha256="abc",
            capture_timestamp_iso="2026-08-27T05:00:00Z",
            capture_monotonic=1000.0,
            monitor_index=1, resolution_w=1920, resolution_h=1080,
            window_title_sanitized="TFT",
        )
        chk.prediction = make_prediction()
        chk.human_input = make_human_input()
        chk.review = make_review()
        chk.state = CheckpointState.REVIEWED.value
        validator = EvidenceValidator()
        valid, issues = validator.validate_checkpoint(chk)
        assert not valid
        assert any("MISSING_FRAME" in i for i in issues)

    def test_hash_mismatch_detected(self, tmp_path):
        fp, sha, _ = make_real_frame(str(tmp_path))
        chk = EvidenceCheckpoint("CHK_00000", "TEST", SourceType.REAL_LIVE.value)
        chk.capture = make_capture(fp, "WRONG_HASH_000")
        chk.prediction = make_prediction()
        chk.human_input = make_human_input()
        chk.review = make_review()
        chk.state = CheckpointState.REVIEWED.value
        validator = EvidenceValidator()
        valid, issues = validator.validate_checkpoint(chk)
        assert not valid
        assert any("HASH_MISMATCH" in i for i in issues)

    def test_synthetic_vision_source_rejected(self, tmp_path):
        fp, sha, _ = make_real_frame(str(tmp_path))
        chk = EvidenceCheckpoint("CHK_00000", "TEST", SourceType.REAL_LIVE.value)
        chk.capture = make_capture(fp, sha)
        chk.prediction = make_prediction(vision_source="SYNTHETIC")  # rejected
        chk.human_input = make_human_input()
        chk.review = make_review()
        chk.state = CheckpointState.REVIEWED.value
        validator = EvidenceValidator()
        valid, issues = validator.validate_checkpoint(chk)
        assert not valid
        assert any("NON_REAL_VISION_SOURCE" in i for i in issues)

    def test_timestamp_inversion_detected(self, tmp_path):
        fp, sha, _ = make_real_frame(str(tmp_path))
        chk = EvidenceCheckpoint("CHK_00000", "TEST", SourceType.REAL_LIVE.value)
        chk.capture = make_capture(fp, sha, mono=1000.0)
        chk.prediction = make_prediction(mono=999.0)  # prediction BEFORE capture
        chk.human_input = make_human_input()
        chk.review = make_review()
        chk.state = CheckpointState.REVIEWED.value
        validator = EvidenceValidator()
        valid, issues = validator.validate_checkpoint(chk)
        assert not valid
        assert any("TIMESTAMP_INVERSION" in i for i in issues)

    def test_blind_order_violation_detected(self, tmp_path):
        fp, sha, _ = make_real_frame(str(tmp_path))
        chk = EvidenceCheckpoint("CHK_00000", "TEST", SourceType.REAL_LIVE.value)
        chk.capture = make_capture(fp, sha)
        chk.prediction = make_prediction()
        chk.human_input = make_human_input(mono=2000.0)  # after reveal
        chk.review = make_review(blind=True, reveal_mono=1500.0)  # reveal at 1500
        # human_input at 2000 > reveal at 1500 -> VIOLATION
        chk.state = CheckpointState.REVIEWED.value
        validator = EvidenceValidator()
        valid, issues = validator.validate_checkpoint(chk)
        assert not valid
        assert any("BLIND_ORDER_VIOLATION" in i for i in issues)

    def test_valid_checkpoint_passes(self, tmp_path):
        fp, sha, _ = make_real_frame(str(tmp_path))
        chk = EvidenceCheckpoint("CHK_00000", "TEST", SourceType.REAL_LIVE.value)
        chk.capture = make_capture(fp, sha, mono=1000.0)
        chk.prediction = make_prediction(mono=1001.0)
        chk.human_input = make_human_input(mono=1002.0)
        chk.review = make_review()
        chk.state = CheckpointState.REVIEWED.value
        validator = EvidenceValidator()
        valid, issues = validator.validate_checkpoint(chk)
        assert valid
        assert len(issues) == 0


# ── Tests: Synthetic Pattern Detection ───────────────────────────────────────

class TestSyntheticPatternDetection:

    def test_detects_range_loop_generation(self, tmp_path):
        p = os.path.join(str(tmp_path), "synthetic_eval.py")
        with open(p, "w") as f:
            f.write("for i in range(105):\n    checkpoint = generate(i)\n")
        validator = EvidenceValidator()
        findings = validator.scan_for_synthetic_patterns(p)
        assert len(findings) > 0

    def test_detects_hardcoded_human_label(self, tmp_path):
        p = os.path.join(str(tmp_path), "fake_eval.py")
        with open(p, "w") as f:
            f.write("human_preferred_action=dec_res.action\n")
        validator = EvidenceValidator()
        findings = validator.scan_for_synthetic_patterns(p)
        assert len(findings) > 0

    def test_detects_is_wrong_hardcoded(self, tmp_path):
        p = os.path.join(str(tmp_path), "old_eval.py")
        with open(p, "w") as f:
            f.write("is_wrong = (i == 42 or i == 88)\n")
        validator = EvidenceValidator()
        findings = validator.scan_for_synthetic_patterns(p)
        assert len(findings) > 0

    def test_clean_file_no_findings(self, tmp_path):
        p = os.path.join(str(tmp_path), "clean.py")
        with open(p, "w") as f:
            f.write("def compute_accuracy(verdicts):\n    return sum(v=='CORRECT' for v in verdicts)/len(verdicts)\n")
        validator = EvidenceValidator()
        findings = validator.scan_for_synthetic_patterns(p)
        assert len(findings) == 0


# ── Tests: HumanInputEvent key mapping ───────────────────────────────────────

class TestHumanInputKeyMapping:

    @pytest.mark.parametrize("key,expected_verdict", [
        ("C", "CORRECT"), ("W", "WRONG"), ("X", "UNKNOWN"), ("S", "SKIPPED"),
    ])
    def test_verdict_key_mapping(self, key, expected_verdict):
        hi = make_human_input(key=key)
        assert hi.derive_verdict() == expected_verdict

    @pytest.mark.parametrize("key,expected_action", [
        ("R", "ROLL"), ("B", "BUY"), ("L", "LEVEL_UP"), ("G", "SAVE_GOLD"),
        ("C", None), ("W", None),
    ])
    def test_action_key_mapping(self, key, expected_action):
        hi = make_human_input(key=key)
        assert hi.derive_preferred_action() == expected_action

    def test_lowercase_key_normalized(self):
        hi = HumanInputEvent("ID","c","ISO",1000.0,"CHK","SESS")
        assert hi.derive_verdict() == DomainVerdict.CORRECT.value


# ── Tests: Gate Verdict ───────────────────────────────────────────────────────

class TestGateVerdict:

    def test_zero_valid_is_unverifiable(self):
        from tft.vision.runtime_v2.evidence_validator import EvidenceAuditResult
        r = EvidenceAuditResult()
        assert r.final_gate() == "REAL_RUNTIME_UNVERIFIABLE"

    def test_label_contamination_blocks(self):
        from tft.vision.runtime_v2.evidence_validator import EvidenceAuditResult
        r = EvidenceAuditResult()
        r.valid_checkpoint_count = 50
        r.label_contamination_count = 1
        assert r.final_gate() == "REAL_RUNTIME_BLOCKED"

    def test_synthetic_contamination_blocks(self):
        from tft.vision.runtime_v2.evidence_validator import EvidenceAuditResult
        r = EvidenceAuditResult()
        r.valid_checkpoint_count = 50
        r.synthetic_contamination_found = ["PATTERN_FOUND"]
        assert r.final_gate() == "REAL_RUNTIME_BLOCKED"

    def test_less_than_30_is_preliminary(self):
        from tft.vision.runtime_v2.evidence_validator import EvidenceAuditResult
        r = EvidenceAuditResult()
        r.valid_checkpoint_count = 15
        assert r.final_gate() == "REAL_RUNTIME_PRELIMINARY"

    def test_30_or_more_is_confirmed(self):
        from tft.vision.runtime_v2.evidence_validator import EvidenceAuditResult
        r = EvidenceAuditResult()
        r.valid_checkpoint_count = 30
        assert r.final_gate() == "REAL_RUNTIME_CONFIRMED"

    def test_exactly_30_is_confirmed(self):
        from tft.vision.runtime_v2.evidence_validator import EvidenceAuditResult
        r = EvidenceAuditResult()
        r.valid_checkpoint_count = 30
        assert r.final_gate() == "REAL_RUNTIME_CONFIRMED"


# ── Tests: NO TFT CLIENT handling ───────────────────────────────────────────

class TestNoTFTClient:

    def test_real_capture_source_raises_when_no_tft(self):
        from tft.vision.runtime_v2.capture_source import RealCaptureSource
        # When no TFT window, must raise EnvironmentError
        with pytest.raises(EnvironmentError, match="NO_TFT_CLIENT"):
            src = RealCaptureSource(require_tft=True)

    def test_session_runner_returns_unverifiable_when_no_tft(self, tmp_path):
        from tft.vision.runtime_v2.session_runner import RuntimeSessionRunner
        from tft.vision.runtime_v2.evidence_store import SourceType
        runner = RuntimeSessionRunner(str(tmp_path), "TEST_NOTFT", SourceType.REAL_LIVE)
        result = runner.run_real_live(max_checkpoints=1, timeout_per_checkpoint=0.1)
        assert result["gate"] == "REAL_RUNTIME_UNVERIFIABLE"
        assert result["valid_checkpoints"] == 0
        # Must not create any synthetic checkpoints
        assert len(runner.store.checkpoints) == 0 or all(
            c.state == CheckpointState.INVALID.value for c in runner.store.checkpoints
        )


# ── Tests: Source type separation ────────────────────────────────────────────

class TestSourceTypeSeparation:

    def test_fixture_source_type_not_counted_as_real_live(self, tmp_path):
        store = EvidenceStore(str(tmp_path), "TEST", SourceType.FIXTURE)
        assert store.source_type == SourceType.FIXTURE
        assert store.source_type.value != SourceType.REAL_LIVE.value

    def test_source_type_stored_in_checkpoint(self):
        chk = EvidenceCheckpoint("CHK_00000", "TEST", SourceType.VIDEO_REPLAY.value)
        assert chk.source_type == "VIDEO_REPLAY"
        d = chk.to_dict()
        assert d["source_type"] == "VIDEO_REPLAY"

    def test_real_live_checkpoint_has_correct_source_type(self):
        chk = EvidenceCheckpoint("CHK_00000", "TEST", SourceType.REAL_LIVE.value)
        assert chk.source_type == "REAL_LIVE"


# ── Tests: PII audit ─────────────────────────────────────────────────────────

class TestPIIAudit:

    def test_pii_detected_in_json(self, tmp_path):
        p = os.path.join(str(tmp_path), "data.json")
        with open(p, "w") as f:
            json.dump({"puuid": "abc123"}, f)
        validator = EvidenceValidator()
        findings = validator.scan_for_pii(str(tmp_path))
        assert len(findings) > 0

    def test_no_pii_in_clean_data(self, tmp_path):
        p = os.path.join(str(tmp_path), "clean.json")
        with open(p, "w") as f:
            json.dump({"checkpoint_id": "CHK_00000", "gold": 30}, f)
        validator = EvidenceValidator()
        findings = validator.scan_for_pii(str(tmp_path))
        assert len(findings) == 0
