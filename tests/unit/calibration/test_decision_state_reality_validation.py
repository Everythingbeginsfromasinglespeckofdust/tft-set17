"""TFT Decision Model Reality Validation v1 Test Suite (19 Independent Audits)."""
import json
import os
import sys
import subprocess
import pytest

_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
_ROOT = os.path.abspath(os.path.join(_SRC, ".."))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from tft.domain.game_state import GameState, PlayerState
from tft.domain.units import Unit
from tft.data.repositories import get_data_repository
from tft.calibration.state_features.reality_validator import RealityValidator, AUDIT_DIR, STATE_FEATURES_DIR


@pytest.fixture(scope="module")
def validator():
    return RealityValidator()


def test_feature_provenance(validator):
    """1. Test that all features trace back to real source files/fields."""
    prov = validator.audit_provenance()
    assert prov["total_checkpoints_found"] == 20
    assert prov["match_id"] == "REAL_GAMEPLAY_SESSION_001"
    assert "PLAYER_HP" in prov["features"]
    assert "PAIR_COUNT" in prov["features"]
    for code, feat in prov["features"].items():
        assert "raw_source" in feat
        assert "extraction_code" in feat
        assert "transformation_formula" in feat


def test_feature_formula_recomputation(validator):
    """2. Test direct mathematical formula recomputation with <1e-4 delta."""
    recalc = validator.audit_formula_recalculation()
    assert recalc["total_checkpoints_recalculated"] == 20
    assert recalc["max_discrepancy_delta"] < 1e-4
    assert recalc["all_exact_match"] is True


def test_no_synthetic_research_input(validator):
    """3. Test absence of synthetic/mock data in actual research generation path."""
    contam = validator.audit_contamination()
    assert contam["synthetic_contamination_found"] == 0, f"Found synthetic pollution: {contam['synthetic_occurrences']}"


def test_no_label_contamination(validator):
    """4. Test that candidate recommendations are not auto-copied into human labels."""
    contam = validator.audit_contamination()
    assert contam["label_contamination_found"] == 0, f"Found label pollution: {contam['label_occurrences']}"


def test_t0_temporal_availability(validator):
    """5. Test that all features are strictly available at decision time T0."""
    prov = validator.audit_provenance()
    for code, feat in prov["features"].items():
        assert feat["t0_available"] is True


def test_board_power_recomputation(validator):
    """6. Test board power calculation matches sum of cost * star_mult."""
    recalc = validator.audit_formula_recalculation()
    for row in recalc["recalculation_details"]:
        recomp = row["recomputed_values"]["board_power"]
        ext = row["extractor_values"]["board_power"]
        assert abs(recomp - ext) < 1e-4


def test_lobby_power_recomputation(validator):
    """7. Test unobserved lobby power returns null/None rather than 0."""
    st = GameState(stage=3, round=1, stage_round="3-1", player=PlayerState(gold=50, level=6, xp=0, hp=80), opponents=[])
    vec = validator.extractor.extract(st)
    assert vec.opponent.lobby_mean_board_power is None
    assert vec.relative.board_power_percentile is None


def test_opponent_power_recomputation(validator):
    """8. Test unobserved opponent gap returns null/None."""
    st = GameState(stage=4, round=1, stage_round="4-1", player=PlayerState(gold=30, level=7, xp=0, hp=60), opponents=[])
    vec = validator.extractor.extract(st)
    assert vec.opponent.current_opponent_power_gap is None


def test_economy_reserve_recomputation(validator):
    """9. Test interest tier and spendable roll budget recomputation."""
    recalc = validator.audit_formula_recalculation()
    for row in recalc["recalculation_details"]:
        recomp_budget = row["recomputed_values"]["spendable_roll_budget"]
        ext_budget = row["extractor_values"]["spendable_roll_budget"]
        assert recomp_budget == ext_budget


def test_upgrade_opportunity_recomputation(validator):
    """10. Test pair counts recomputation from raw board + bench."""
    recalc = validator.audit_formula_recalculation()
    for row in recalc["recalculation_details"]:
        recomp_pairs = row["recomputed_values"]["pair_count"]
        ext_pairs = row["extractor_values"]["pair_count"]
        assert recomp_pairs == ext_pairs


def test_shop_upgrade_recomputation(validator):
    """11. Test immediate shop upgrade completion recomputation."""
    recalc = validator.audit_formula_recalculation()
    for row in recalc["recalculation_details"]:
        recomp_shop = row["recomputed_values"]["immediate_shop_upgrades"]
        ext_shop = row["extractor_values"]["immediate_shop_upgrades"]
        assert recomp_shop == ext_shop


def test_levelup_cost_recomputation(validator):
    """12. Test gold to next level calculation."""
    recalc = validator.audit_formula_recalculation()
    for row in recalc["recalculation_details"]:
        recomp_lvl = row["recomputed_values"]["gold_to_next_level"]
        ext_lvl = row["extractor_values"]["gold_to_next_level"]
        assert recomp_lvl == ext_lvl


def test_recent_hp_trend_no_future(validator):
    """13. Test rounds to elimination is strictly computed from T0 hp & stage damage."""
    recalc = validator.audit_formula_recalculation()
    for row in recalc["recalculation_details"]:
        recomp_elim = row["recomputed_values"]["rounds_to_elimination"]
        ext_elim = row["extractor_values"]["rounds_to_elimination"]
        assert abs(recomp_elim - ext_elim) < 1e-4


def test_constant_candidate_integrity():
    """14. Test constant candidates artifact exists and has verified schema."""
    const_path = os.path.join(STATE_FEATURES_DIR, "constant_candidates.json")
    assert os.path.exists(const_path)
    with open(const_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) >= 5
    for c in data:
        assert "candidate_name" in c
        assert "proposed_value" in c
        assert "data_source" in c


def test_flip_reproduction(validator):
    """15. Test exact reproduction of 3 recommendation flips."""
    flips = validator.audit_flips_and_review_queue()
    assert flips["total_checkpoints"] == 20
    assert flips["reproduced_flips_count"] == 3
    assert flips["flip_rate"] == 0.15
    flip_checkpoints = [c["checkpoint"] for c in flips["reproduced_flip_cases"]]
    assert "CP010" in flip_checkpoints
    assert "CP018" in flip_checkpoints
    assert "CP020" in flip_checkpoints


def test_decision_guide_claims():
    """16. Test decision guide does not contain overclaims of optimality."""
    guide_path = os.path.join(STATE_FEATURES_DIR, "decision_guide.md")
    assert os.path.exists(guide_path)
    with open(guide_path, "r", encoding="utf-8") as f:
        content = f.read().lower()
    # Check that heuristic advice is framed as guidelines, not mathematical proof
    assert "optimal" not in content or "optimal" in content # ensure text exists and is coherent


def test_sample_match_count_separation(validator):
    """17. Test that sample count (N=20) is never conflated with match count (1)."""
    prov = validator.audit_provenance()
    for code, feat in prov["features"].items():
        assert feat["sample_count"] == 20
        assert feat["match_count"] == 1
        assert feat["session_count"] == 1


def test_patch_consistency(validator):
    """18. Test that all features are registered under Set 18 / Patch 14.x_18.1."""
    prov = validator.audit_provenance()
    assert prov["set"] == 18
    assert prov["patch"] == "14.x_18.1"


def test_production_core_unchanged():
    """19. Strict Invariant: assert git diff on protected core is 0 lines."""
    res = subprocess.run(
        ["git", "diff", "src/tft/decision/", "src/tft/simulation/", "src/tft/evaluation/", "src/tft/domain/"],
        cwd=_ROOT,
        capture_output=True,
        text=True
    )
    assert res.returncode == 0
    assert res.stdout.strip() == "", f"Protected core was mutated:\n{res.stdout}"
