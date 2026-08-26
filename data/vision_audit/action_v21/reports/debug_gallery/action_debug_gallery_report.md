# 🎬 Action Detection Debug Gallery Report

- **Total Diagnostic Cases**: `106` (FP: `63`, FN: `43`)

## 1. False Positive Cases (Spurious or Misclassified Actions)

| Case ID | Time | Predicted | Ground Truth | Confidence | Reason | Evidence |
|---|---|---|---|---|---|---|
| `fa_358_1` | `358.0s` | **BUY_UNIT** | ROLL | `0.85` | Type Mismatch (predicted BUY_UNIT, actual ROLL) | Slot 4 (나서스, 1C) transitioned from RECOGNIZED to EMPTY |
| `fa_360_2` | `360.5s` | **BUY_UNIT** | ROLL | `0.85` | Type Mismatch (predicted BUY_UNIT, actual ROLL) | Slot 1 (다이애나, 3C) transitioned from RECOGNIZED to EMPTY |
| `fa_361_3` | `361.5s` | **ROLL** | BUY_UNIT | `0.925` | Type Mismatch (predicted ROLL, actual BUY_UNIT) | Shop refreshed across 3/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_364_4` | `364.0s` | **BUY_UNIT** | ROLL | `0.85` | Type Mismatch (predicted BUY_UNIT, actual ROLL) | Slot 4 (다이애나, 3C) transitioned from RECOGNIZED to EMPTY |
| `fa_364_5` | `364.5s` | **BUY_UNIT** | ROLL | `0.85` | Type Mismatch (predicted BUY_UNIT, actual ROLL) | Slot 5 (나미, 4C) transitioned from RECOGNIZED to EMPTY |
| `fa_366_6` | `366.5s` | **ROLL** | BUY_UNIT | `0.925` | Type Mismatch (predicted ROLL, actual BUY_UNIT) | Shop refreshed across 3/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_374_7` | `374.5s` | **BUY_UNIT** | NO_ACTION | `0.85` | Spurious Detection (No GT action within tolerance) | Slot 5 (나미, 4C) transitioned from RECOGNIZED to EMPTY |
| `fa_375_8` | `375.0s` | **ROLL** | NO_ACTION | `0.925` | Spurious Detection (No GT action within tolerance) | Shop refreshed across 3/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_376_9` | `376.0s` | **ROLL** | NO_ACTION | `0.925` | Spurious Detection (No GT action within tolerance) | Shop refreshed across 3/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_377_10` | `377.5s` | **ROLL** | NO_ACTION | `0.925` | Spurious Detection (No GT action within tolerance) | Shop refreshed across 3/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_379_11` | `379.0s` | **BUY_UNIT** | NO_ACTION | `0.85` | Spurious Detection (No GT action within tolerance) | Slot 4 (다이애나, 3C) transitioned from RECOGNIZED to EMPTY |
| `fa_379_12` | `379.5s` | **BUY_UNIT** | NO_ACTION | `0.85` | Spurious Detection (No GT action within tolerance) | Slot 5 (나미, 4C) transitioned from RECOGNIZED to EMPTY |
| `fa_381_13` | `381.5s` | **ROLL** | NO_ACTION | `0.925` | Spurious Detection (No GT action within tolerance) | Shop refreshed across 3/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_388_14` | `388.5s` | **ROLL** | NO_ACTION | `0.925` | Spurious Detection (No GT action within tolerance) | Shop refreshed across 3/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_393_15` | `393.0s` | **BUY_UNIT** | NO_ACTION | `0.85` | Spurious Detection (No GT action within tolerance) | Slot 1 (모르가나, 4C) transitioned from RECOGNIZED to EMPTY |
| `fa_395_16` | `395.0s` | **BUY_UNIT** | NO_ACTION | `0.85` | Spurious Detection (No GT action within tolerance) | Slot 5 (나미, 4C) transitioned from RECOGNIZED to EMPTY |
| `fa_398_17` | `398.0s` | **BUY_UNIT** | NO_ACTION | `0.85` | Spurious Detection (No GT action within tolerance) | Slot 3 (렉사이, 1C) transitioned from RECOGNIZED to EMPTY |
| `fa_400_18` | `400.0s` | **ROLL** | NO_ACTION | `0.925` | Spurious Detection (No GT action within tolerance) | Shop refreshed across 3/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_402_19` | `402.5s` | **ROLL** | NO_ACTION | `0.925` | Spurious Detection (No GT action within tolerance) | Shop refreshed across 3/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_404_20` | `404.0s` | **ROLL** | NO_ACTION | `0.925` | Spurious Detection (No GT action within tolerance) | Shop refreshed across 3/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_441_21` | `441.5s` | **ROLL** | NO_ACTION | `0.925` | Spurious Detection (No GT action within tolerance) | Shop refreshed across 3/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_450_22` | `450.0s` | **ROLL** | NO_ACTION | `0.925` | Spurious Detection (No GT action within tolerance) | Shop refreshed across 3/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_462_23` | `462.5s` | **ROLL** | NO_ACTION | `0.925` | Spurious Detection (No GT action within tolerance) | Shop refreshed across 3/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_471_24` | `471.5s` | **ROLL** | NO_ACTION | `0.925` | Spurious Detection (No GT action within tolerance) | Shop refreshed across 3/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_472_25` | `472.0s` | **ROLL** | NO_ACTION | `0.925` | Spurious Detection (No GT action within tolerance) | Shop refreshed across 3/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |

## 2. False Negative Cases (Missed Player Actions)

| Case ID | Time | Ground Truth Action | Reason | Notes |
|---|---|---|---|---|
| `fa_321_64` | `321.5s` | **BUY_UNIT** | Missed BUY_UNIT Event (미스 포츈) | Slot 3 purchased (미스 포츈) |
| `fa_340_65` | `340.0s` | **BUY_UNIT** | Missed BUY_UNIT Event (미스 포츈) | Slot 3 purchased (미스 포츈) |
| `fa_343_66` | `343.0s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_343_67` | `343.5s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_349_68` | `349.5s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_351_69` | `351.0s` | **BUY_UNIT** | Missed BUY_UNIT Event (소나) | Slot 2 purchased (소나) |
| `fa_352_70` | `352.0s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_353_71` | `353.0s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_354_72` | `354.5s` | **BUY_UNIT** | Missed BUY_UNIT Event (소나) | Slot 2 purchased (소나) |
| `fa_358_73` | `358.5s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_360_74` | `360.0s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_362_75` | `362.0s` | **BUY_UNIT** | Missed BUY_UNIT Event (쉔) | Slot 1 purchased (쉔) |
| `fa_364_76` | `364.5s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_366_77` | `366.0s` | **BUY_UNIT** | Missed BUY_UNIT Event (다리우스) | Slot 4 purchased (다리우스) |
| `fa_368_78` | `368.0s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_370_79` | `370.0s` | **BUY_UNIT** | Missed BUY_UNIT Event (조이) | Slot 5 purchased (조이) |
| `fa_420_80` | `420.0s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_421_81` | `421.0s` | **BUY_UNIT** | Missed BUY_UNIT Event (미스 포츈) | Slot 2 purchased (미스 포츈) |
| `fa_422_82` | `422.5s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_424_83` | `424.0s` | **BUY_UNIT** | Missed BUY_UNIT Event (소나) | Slot 1 purchased (소나) |
| `fa_425_84` | `425.0s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_428_85` | `428.5s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_430_86` | `430.0s` | **BUY_UNIT** | Missed BUY_UNIT Event (쉔) | Slot 3 purchased (쉔) |
| `fa_431_87` | `431.0s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_480_88` | `480.5s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |