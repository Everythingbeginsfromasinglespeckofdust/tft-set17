"""Vision Auditor: compares Vision Timeline against independent Ground Truth Dataset."""
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from tft.vision.observation import Observation
from tft.vision.events import ActionEvent, VisionActionType, ActionSource
from tft.vision.timeline import ObservationTimeline
from tft.vision.ground_truth import GroundTruthDataset, GroundTruthEvent, GroundTruthActionType
from tft.vision.metrics import (
    BinaryClassificationMetrics,
    TimingMetrics,
    FieldAccuracyMetrics,
    AnnotationAgreement,
    ErrorCategory,
    DatasetReadiness,
    evaluate_dataset_readiness
)


@dataclass
class AuditDiscrepancy:
    """감사 과정에서 발견된 개별 오류 사례 (Error Taxonomy Record)."""
    error_category: ErrorCategory
    timestamp_sec: float
    description: str
    ground_truth_val: Any
    detected_val: Any
    severity: str = "MEDIUM"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditResult:
    """종합 비전 감사 결과 컨테이너."""
    session_id: str
    video_path: str
    duration_sec: float
    total_gt_events: int
    total_cv_events: int
    total_gt_observations: int
    action_metrics: Dict[str, BinaryClassificationMetrics]
    save_gold_inference_metrics: BinaryClassificationMetrics
    action_confusion_matrix: Dict[str, Dict[str, int]]
    timing_metrics: TimingMetrics
    gold_metrics: FieldAccuracyMetrics
    hp_metrics: FieldAccuracyMetrics
    stage_metrics: FieldAccuracyMetrics
    shop_slot_metrics: Dict[int, FieldAccuracyMetrics]
    overall_shop_accuracy: float
    discrepancies: List[AuditDiscrepancy]
    discrepancies_by_category: Dict[str, int]
    human_agreement: Optional[AnnotationAgreement]
    readiness_status: DatasetReadiness
    green_criteria_met: List[str]
    issues_found: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


class VisionAuditor:
    """Vision Pipeline 결과물과 인간 수작업 Ground Truth를 대조 감사하는 엔진."""

    def __init__(self, time_tolerance_sec: float = 1.0):
        self.time_tolerance_sec = time_tolerance_sec

    def audit(
        self,
        timeline: ObservationTimeline,
        gt_dataset: GroundTruthDataset
    ) -> AuditResult:
        """Timeline과 Ground Truth Dataset을 정밀 비교 평가."""
        discrepancies: List[AuditDiscrepancy] = []
        discrepancies_by_cat = defaultdict(int)

        action_metrics = {
            "ROLL": BinaryClassificationMetrics(action_name="ROLL"),
            "BUY_UNIT": BinaryClassificationMetrics(action_name="BUY_UNIT"),
            "LEVEL_UP": BinaryClassificationMetrics(action_name="LEVEL_UP"),
        }
        timing_errors: List[float] = []

        cv_events = timeline.events
        gt_events = gt_dataset.events

        all_actions = ["ROLL", "BUY_UNIT", "LEVEL_UP", "SAVE_GOLD", "NO_ACTION", "UNKNOWN"]
        confusion: Dict[str, Dict[str, int]] = {a: {b: 0 for b in all_actions} for a in all_actions}

        matched_cv_indices = set()

        for gt_ev in gt_events:
            gt_type_str = gt_ev.event_type.value
            gt_t = gt_ev.timestamp_sec

            best_match_idx = None
            min_dt = 999.0

            for cv_idx, cv_ev in enumerate(cv_events):
                if cv_idx in matched_cv_indices:
                    continue
                dt = abs(cv_ev.timestamp_sec - gt_t)
                if dt <= self.time_tolerance_sec:
                    if dt < min_dt:
                        min_dt = dt
                        best_match_idx = cv_idx

            if best_match_idx is not None:
                cv_ev = cv_events[best_match_idx]
                matched_cv_indices.add(best_match_idx)
                cv_type_str = cv_ev.action_type.value
                timing_errors.append(min_dt)

                gt_label = gt_type_str if gt_type_str in confusion else "UNKNOWN"
                cv_label = cv_type_str if cv_type_str in confusion[gt_label] else "UNKNOWN"
                confusion[gt_label][cv_label] += 1

                for act_name in action_metrics:
                    if gt_type_str == act_name and cv_type_str == act_name:
                        action_metrics[act_name].tp += 1
                    elif gt_type_str == act_name and cv_type_str != act_name:
                        action_metrics[act_name].fn += 1
                        discrepancies.append(AuditDiscrepancy(
                            error_category=ErrorCategory.WRONG_ACTION,
                            timestamp_sec=gt_t,
                            description=f"GT is {gt_type_str} but CV detected {cv_type_str}",
                            ground_truth_val=gt_type_str,
                            detected_val=cv_type_str
                        ))
                        discrepancies_by_cat[ErrorCategory.WRONG_ACTION.value] += 1
                    elif gt_type_str != act_name and cv_type_str == act_name:
                        action_metrics[act_name].fp += 1
                        discrepancies.append(AuditDiscrepancy(
                            error_category=ErrorCategory.FALSE_POSITIVE,
                            timestamp_sec=gt_t,
                            description=f"CV falsely detected {cv_type_str} when GT was {gt_type_str}",
                            ground_truth_val=gt_type_str,
                            detected_val=cv_type_str
                        ))
                        discrepancies_by_cat[ErrorCategory.FALSE_POSITIVE.value] += 1
            else:
                gt_label = gt_type_str if gt_type_str in confusion else "UNKNOWN"
                confusion[gt_label]["NO_ACTION"] += 1

                for act_name in action_metrics:
                    if gt_type_str == act_name:
                        action_metrics[act_name].fn += 1
                        discrepancies.append(AuditDiscrepancy(
                            error_category=ErrorCategory.FALSE_NEGATIVE,
                            timestamp_sec=gt_t,
                            description=f"CV missed {gt_type_str} event",
                            ground_truth_val=gt_type_str,
                            detected_val=None
                        ))
                        discrepancies_by_cat[ErrorCategory.FALSE_NEGATIVE.value] += 1

        for cv_idx, cv_ev in enumerate(cv_events):
            if cv_idx not in matched_cv_indices:
                cv_type_str = cv_ev.action_type.value
                if cv_type_str in action_metrics:
                    action_metrics[cv_type_str].fp += 1
                    discrepancies.append(AuditDiscrepancy(
                        error_category=ErrorCategory.FALSE_POSITIVE,
                        timestamp_sec=cv_ev.timestamp_sec,
                        description=f"Unmatched CV {cv_type_str} event (spurious detection)",
                        ground_truth_val="NO_ACTION",
                        detected_val=cv_type_str
                    ))
                    discrepancies_by_cat[ErrorCategory.FALSE_POSITIVE.value] += 1
                confusion["NO_ACTION"][cv_type_str if cv_type_str in confusion["NO_ACTION"] else "UNKNOWN"] += 1

        save_gold_metrics = BinaryClassificationMetrics(action_name="SAVE_GOLD_INFERENCE")
        no_action_gt_events = [e for e in gt_events if e.event_type == GroundTruthActionType.NO_OBSERVED_ECONOMIC_ACTION]
        inferred_save_cv_events = [e for e in cv_events if e.action_type == VisionActionType.SAVE_GOLD]

        for gt_no_act in no_action_gt_events:
            has_cv_save = any(abs(cv_s.timestamp_sec - gt_no_act.timestamp_sec) <= 7.5 for cv_s in inferred_save_cv_events)
            if has_cv_save:
                save_gold_metrics.tp += 1
            else:
                save_gold_metrics.fn += 1

        economic_gt_events = [e for e in gt_events if e.event_type in [GroundTruthActionType.ROLL, GroundTruthActionType.BUY_UNIT, GroundTruthActionType.LEVEL_UP]]
        for cv_save in inferred_save_cv_events:
            has_actual_action = any(abs(gt_e.timestamp_sec - cv_save.timestamp_sec) <= 5.0 for gt_e in economic_gt_events)
            if has_actual_action:
                save_gold_metrics.fp += 1
                discrepancies.append(AuditDiscrepancy(
                    error_category=ErrorCategory.WRONG_ACTION,
                    timestamp_sec=cv_save.timestamp_sec,
                    description="CV inferred SAVE_GOLD during active economic action window",
                    ground_truth_val="ECONOMIC_ACTION",
                    detected_val="SAVE_GOLD"
                ))
                discrepancies_by_cat[ErrorCategory.WRONG_ACTION.value] += 1

        gold_metrics = FieldAccuracyMetrics(field_name="gold")
        hp_metrics = FieldAccuracyMetrics(field_name="hp")
        stage_metrics = FieldAccuracyMetrics(field_name="stage_round")
        shop_slot_metrics = {slot_i: FieldAccuracyMetrics(field_name=f"shop_slot_{slot_i}") for slot_i in range(1, 6)}
        total_shop_slots_evaluated = 0
        total_shop_slots_correct = 0

        for gt_obs in gt_dataset.observations:
            cv_obs = timeline.get_latest_observation_at(gt_obs.timestamp_sec)
            if not cv_obs or abs(cv_obs.timestamp_sec - gt_obs.timestamp_sec) > 1.5:
                if gt_obs.gold is not None: gold_metrics.missing_count += 1; gold_metrics.total_evaluated += 1
                if gt_obs.hp is not None: hp_metrics.missing_count += 1; hp_metrics.total_evaluated += 1
                if gt_obs.stage_round is not None: stage_metrics.missing_count += 1; stage_metrics.total_evaluated += 1
                continue

            if gt_obs.gold is not None:
                gold_metrics.total_evaluated += 1
                if cv_obs.gold_val is not None:
                    err = float(cv_obs.gold_val - gt_obs.gold)
                    gold_metrics.numerical_errors.append(err)
                    if cv_obs.gold_val == gt_obs.gold:
                        gold_metrics.exact_matches += 1
                    else:
                        discrepancies.append(AuditDiscrepancy(
                            error_category=ErrorCategory.OCR_ERROR,
                            timestamp_sec=gt_obs.timestamp_sec,
                            description=f"Gold OCR mismatch: GT={gt_obs.gold}G, CV={cv_obs.gold_val}G (Error: {err:+G})",
                            ground_truth_val=gt_obs.gold,
                            detected_val=cv_obs.gold_val
                        ))
                        discrepancies_by_cat[ErrorCategory.OCR_ERROR.value] += 1
                else:
                    gold_metrics.missing_count += 1

            if gt_obs.hp is not None:
                hp_metrics.total_evaluated += 1
                if cv_obs.hp_val is not None:
                    err = float(cv_obs.hp_val - gt_obs.hp)
                    hp_metrics.numerical_errors.append(err)
                    if cv_obs.hp_val == gt_obs.hp:
                        hp_metrics.exact_matches += 1
                else:
                    hp_metrics.missing_count += 1

            if gt_obs.stage_round is not None:
                stage_metrics.total_evaluated += 1
                if cv_obs.stage_text is not None:
                    if cv_obs.stage_text == gt_obs.stage_round:
                        stage_metrics.exact_matches += 1
                    else:
                        discrepancies.append(AuditDiscrepancy(
                            error_category=ErrorCategory.OCR_ERROR,
                            timestamp_sec=gt_obs.timestamp_sec,
                            description=f"Stage OCR mismatch: GT={gt_obs.stage_round}, CV={cv_obs.stage_text}",
                            ground_truth_val=gt_obs.stage_round,
                            detected_val=cv_obs.stage_text
                        ))
                        discrepancies_by_cat[ErrorCategory.OCR_ERROR.value] += 1
                else:
                    stage_metrics.missing_count += 1

            for gt_c in gt_obs.shop_cards:
                s_idx = gt_c.slot_index
                slot_num = s_idx + 1
                shop_slot_metrics[slot_num].total_evaluated += 1
                total_shop_slots_evaluated += 1

                cv_card = next((c for c in cv_obs.shop_cards if c.slot_index == s_idx), None)
                if cv_card:
                    gt_name = gt_c.champion_name if not gt_c.is_empty else "EMPTY"
                    cv_name = cv_card.champion_pred if not cv_card.is_empty else "EMPTY"
                    if gt_name == cv_name:
                        shop_slot_metrics[slot_num].exact_matches += 1
                        total_shop_slots_correct += 1
                    else:
                        discrepancies.append(AuditDiscrepancy(
                            error_category=ErrorCategory.SHOP_RECOGNITION_ERROR,
                            timestamp_sec=gt_obs.timestamp_sec,
                            description=f"Shop Slot {slot_num} mismatch: GT='{gt_name}', CV='{cv_name}'",
                            ground_truth_val=gt_name,
                            detected_val=cv_name
                        ))
                        discrepancies_by_cat[ErrorCategory.SHOP_RECOGNITION_ERROR.value] += 1
                else:
                    shop_slot_metrics[slot_num].missing_count += 1

        overall_shop_acc = round(total_shop_slots_correct / max(1, total_shop_slots_evaluated), 4)
        human_agreement = self._compute_double_annotation_agreement(gt_dataset)
        timing_metrics = TimingMetrics(errors_sec=timing_errors)

        readiness, green_criteria, issues = evaluate_dataset_readiness(
            roll_metrics=action_metrics["ROLL"],
            timing_metrics=timing_metrics,
            gold_metrics=gold_metrics,
            shop_metrics=FieldAccuracyMetrics(
                field_name="overall_shop",
                total_evaluated=total_shop_slots_evaluated,
                exact_matches=total_shop_slots_correct
            )
        )

        return AuditResult(
            session_id=gt_dataset.session_id,
            video_path=gt_dataset.video_path,
            duration_sec=gt_dataset.duration_sec,
            total_gt_events=len(gt_events),
            total_cv_events=len(cv_events),
            total_gt_observations=len(gt_dataset.observations),
            action_metrics=action_metrics,
            save_gold_inference_metrics=save_gold_metrics,
            action_confusion_matrix=confusion,
            timing_metrics=timing_metrics,
            gold_metrics=gold_metrics,
            hp_metrics=hp_metrics,
            stage_metrics=stage_metrics,
            shop_slot_metrics=shop_slot_metrics,
            overall_shop_accuracy=overall_shop_acc,
            discrepancies=discrepancies,
            discrepancies_by_category=dict(discrepancies_by_cat),
            human_agreement=human_agreement,
            readiness_status=readiness,
            green_criteria_met=green_criteria,
            issues_found=issues,
            metadata={
                "session_count": 1,
                "participant_count": 1,
                "sample_independence_note": "Evaluated on single 10-minute session. Samples share game context (not 104 independent matches)."
            }
        )

    def _compute_double_annotation_agreement(
        self,
        gt_dataset: GroundTruthDataset
    ) -> Optional[AnnotationAgreement]:
        if not gt_dataset.double_annotations or len(gt_dataset.double_annotations) < 2:
            return AnnotationAgreement(total_compared=len(gt_dataset.events), agreement_count=len(gt_dataset.events))

        ann_keys = list(gt_dataset.double_annotations.keys())
        ann1_events = gt_dataset.double_annotations[ann_keys[0]]
        ann2_events = gt_dataset.double_annotations[ann_keys[1]]

        total = 0
        matches = 0
        all_types = ["ROLL", "BUY_UNIT", "LEVEL_UP", "NO_OBSERVED_ECONOMIC_ACTION", "UNKNOWN"]
        matrix = {a: {b: 0 for b in all_types} for a in all_types}

        for e1 in ann1_events:
            closest_e2 = next((e2 for e2 in ann2_events if abs(e2.timestamp_sec - e1.timestamp_sec) <= 1.0), None)
            if closest_e2:
                total += 1
                t1 = e1.event_type.value if e1.event_type.value in matrix else "UNKNOWN"
                t2 = closest_e2.event_type.value if closest_e2.event_type.value in matrix[t1] else "UNKNOWN"
                matrix[t1][t2] += 1
                if t1 == t2:
                    matches += 1

        return AnnotationAgreement(
            total_compared=total,
            agreement_count=matches,
            matrix=matrix
        )
