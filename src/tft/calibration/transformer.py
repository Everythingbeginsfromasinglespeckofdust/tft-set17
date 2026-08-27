"""Statistical Transformers and Shrinkage Estimators for MetaTFT Calibration."""
import math
from typing import List, Tuple
from tft.calibration.models import TransformationType, CalibrationRecord


class CalibrationTransformer:
    """Transforms raw observational metrics into bounded, shrunk utility scales."""

    POPULATION_PRIOR_AVG = 4.50
    PRIOR_PSEUDO_COUNT = 50

    @staticmethod
    def raw_placement_to_score(avg_placement: float) -> float:
        """Convert 1.0~8.0 placement into 0.0~1.0 score (1.0 = best, 8.0 = worst)."""
        # Clamp bounds
        clamped = max(1.0, min(8.0, avg_placement))
        return (8.0 - clamped) / 7.0

    @staticmethod
    def place_change_to_sigmoid_utility(place_change: float, k: float = 1.2) -> float:
        """Convert placement change (-2.0 to +2.0) into bounded utility bonus (-0.5 to +0.5).
        
        Negative place_change means placement improved (e.g. -0.54 means 4.0 -> 3.46).
        """
        # Negative place_change is good (lower placement number)
        val = -place_change
        sigmoid = 1.0 / (1.0 + math.exp(-k * val))
        # Center at 0.0, bounded in [-0.5, +0.5]
        return sigmoid - 0.5

    @staticmethod
    def empirical_bayes_shrinkage(
        sample_avg: float,
        sample_n: int,
        prior_avg: float = POPULATION_PRIOR_AVG,
        prior_n: int = PRIOR_PSEUDO_COUNT
    ) -> Tuple[float, float]:
        """Apply James-Stein / Empirical Bayes shrinkage towards population prior.
        
        Returns:
            (shrunken_avg, shrinkage_weight)
        """
        if sample_n <= 0:
            return prior_avg, 0.0
        
        weight = sample_n / (sample_n + prior_n)
        shrunken = weight * sample_avg + (1.0 - weight) * prior_avg
        return shrunken, weight

    @staticmethod
    def apply_transformation(
        record: CalibrationRecord,
        transformation: TransformationType,
        threshold_n: int = 30
    ) -> CalibrationRecord:
        """Apply specified statistical transformation to a record."""
        if record.sample_size < threshold_n:
            record.is_filtered_out = True
            record.transformed_score = 0.0
            record.shrinkage_factor = 0.0
            return record

        record.is_filtered_out = False

        if transformation == TransformationType.B0_RAW_BASELINE:
            record.transformed_score = 0.0
            record.shrinkage_factor = 1.0

        elif transformation == TransformationType.B1_RAW_METRIC:
            record.transformed_score = CalibrationTransformer.raw_placement_to_score(record.raw_metric_value)
            record.shrinkage_factor = 1.0

        elif transformation == TransformationType.B2_SAMPLE_WEIGHTED:
            base_score = CalibrationTransformer.raw_placement_to_score(record.raw_metric_value)
            weight = min(1.0, record.sample_size / 500.0)
            record.transformed_score = weight * base_score + (1.0 - weight) * 0.50
            record.shrinkage_factor = weight

        elif transformation == TransformationType.B3_EMPIRICAL_SHRUNK:
            shrunk_avg, weight = CalibrationTransformer.empirical_bayes_shrinkage(
                sample_avg=record.raw_metric_value,
                sample_n=record.sample_size
            )
            record.transformed_score = CalibrationTransformer.raw_placement_to_score(shrunk_avg)
            record.shrinkage_factor = weight

        elif transformation == TransformationType.SIGMOID_NORMALIZED:
            pc = record.place_change if record.place_change is not None else (4.50 - record.raw_metric_value)
            record.transformed_score = CalibrationTransformer.place_change_to_sigmoid_utility(pc)
            record.shrinkage_factor = 1.0

        return record
