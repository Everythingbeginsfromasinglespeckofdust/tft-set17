# 🎬 Action Detection Debug Gallery Report

- **Total Diagnostic Cases**: `164` (FP: `125`, FN: `39`)

## 1. False Positive Cases (Spurious or Misclassified Actions)

| Case ID | Time | Predicted | Ground Truth | Confidence | Reason | Evidence |
|---|---|---|---|---|---|---|
| `fa_312_1` | `312.5s` | **ROLL** | NO_ACTION | `0.925` | Spurious Detection (No GT action within tolerance) | Shop refreshed across 5/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_313_2` | `313.0s` | **ROLL** | NO_ACTION | `0.925` | Spurious Detection (No GT action within tolerance) | Shop refreshed across 4/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_358_3` | `358.0s` | **BUY_UNIT** | ROLL | `0.85` | Type Mismatch (predicted BUY_UNIT, actual ROLL) | Slot 4 (나서스, 1C) transitioned from RECOGNIZED to EMPTY |
| `fa_360_4` | `360.5s` | **BUY_UNIT** | NO_ACTION | `0.85` | Spurious Detection (No GT action within tolerance) | Slot 1 (다이애나, 3C) transitioned from RECOGNIZED to EMPTY |
| `fa_361_5` | `361.5s` | **ROLL** | BUY_UNIT | `0.925` | Type Mismatch (predicted ROLL, actual BUY_UNIT) | Shop refreshed across 3/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_364_6` | `364.0s` | **BUY_UNIT** | ROLL | `0.85` | Type Mismatch (predicted BUY_UNIT, actual ROLL) | Slot 4 (다이애나, 3C) transitioned from RECOGNIZED to EMPTY |
| `fa_364_7` | `364.5s` | **BUY_UNIT** | ROLL | `0.85` | Type Mismatch (predicted BUY_UNIT, actual ROLL) | Slot 5 (나미, 4C) transitioned from RECOGNIZED to EMPTY |
| `fa_366_8` | `366.5s` | **ROLL** | BUY_UNIT | `0.925` | Type Mismatch (predicted ROLL, actual BUY_UNIT) | Shop refreshed across 3/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_367_9` | `367.5s` | **BUY_UNIT** | ROLL | `0.85` | Type Mismatch (predicted BUY_UNIT, actual ROLL) | Slot 2 (일라오이, 3C) transitioned from RECOGNIZED to EMPTY |
| `fa_374_10` | `374.5s` | **BUY_UNIT** | NO_ACTION | `0.85` | Spurious Detection (No GT action within tolerance) | Slot 5 (나미, 4C) transitioned from RECOGNIZED to EMPTY |
| `fa_375_11` | `375.0s` | **ROLL** | NO_ACTION | `0.925` | Spurious Detection (No GT action within tolerance) | Shop refreshed across 3/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_376_12` | `376.0s` | **ROLL** | NO_ACTION | `0.925` | Spurious Detection (No GT action within tolerance) | Shop refreshed across 3/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_377_13` | `377.5s` | **ROLL** | NO_ACTION | `0.925` | Spurious Detection (No GT action within tolerance) | Shop refreshed across 3/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_379_14` | `379.0s` | **BUY_UNIT** | NO_ACTION | `0.85` | Spurious Detection (No GT action within tolerance) | Slot 4 (다이애나, 3C) transitioned from RECOGNIZED to EMPTY |
| `fa_379_15` | `379.5s` | **BUY_UNIT** | NO_ACTION | `0.85` | Spurious Detection (No GT action within tolerance) | Slot 5 (나미, 4C) transitioned from RECOGNIZED to EMPTY |
| `fa_381_16` | `381.0s` | **ROLL** | NO_ACTION | `0.925` | Spurious Detection (No GT action within tolerance) | Shop refreshed across 4/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_381_17` | `381.5s` | **ROLL** | NO_ACTION | `0.925` | Spurious Detection (No GT action within tolerance) | Shop refreshed across 3/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_385_18` | `385.0s` | **ROLL** | NO_ACTION | `0.925` | Spurious Detection (No GT action within tolerance) | Shop refreshed across 4/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_388_19` | `388.5s` | **ROLL** | NO_ACTION | `0.925` | Spurious Detection (No GT action within tolerance) | Shop refreshed across 3/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_391_20` | `391.5s` | **ROLL** | NO_ACTION | `0.925` | Spurious Detection (No GT action within tolerance) | Shop refreshed across 4/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_393_21` | `393.0s` | **BUY_UNIT** | NO_ACTION | `0.85` | Spurious Detection (No GT action within tolerance) | Slot 1 (모르가나, 4C) transitioned from RECOGNIZED to EMPTY |
| `fa_395_22` | `395.0s` | **BUY_UNIT** | NO_ACTION | `0.85` | Spurious Detection (No GT action within tolerance) | Slot 5 (나미, 4C) transitioned from RECOGNIZED to EMPTY |
| `fa_398_23` | `398.0s` | **BUY_UNIT** | NO_ACTION | `0.85` | Spurious Detection (No GT action within tolerance) | Slot 3 (렉사이, 1C) transitioned from RECOGNIZED to EMPTY |
| `fa_398_24` | `398.5s` | **ROLL** | NO_ACTION | `0.925` | Spurious Detection (No GT action within tolerance) | Shop refreshed across 5/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |
| `fa_400_25` | `400.0s` | **ROLL** | NO_ACTION | `0.925` | Spurious Detection (No GT action within tolerance) | Shop refreshed across 3/5 slots simultaneously<br>Board and bench remained unchanged during shop refresh |

## 2. False Negative Cases (Missed Player Actions)

| Case ID | Time | Ground Truth Action | Reason | Notes |
|---|---|---|---|---|
| `fa_321_126` | `321.5s` | **BUY_UNIT** | Missed BUY_UNIT Event (미스 포츈) | Slot 3 purchased (미스 포츈) |
| `fa_340_127` | `340.0s` | **BUY_UNIT** | Missed BUY_UNIT Event (미스 포츈) | Slot 3 purchased (미스 포츈) |
| `fa_343_128` | `343.0s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_343_129` | `343.5s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_349_130` | `349.5s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_351_131` | `351.0s` | **BUY_UNIT** | Missed BUY_UNIT Event (소나) | Slot 2 purchased (소나) |
| `fa_352_132` | `352.0s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_353_133` | `353.0s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_354_134` | `354.5s` | **BUY_UNIT** | Missed BUY_UNIT Event (소나) | Slot 2 purchased (소나) |
| `fa_358_135` | `358.5s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_362_136` | `362.0s` | **BUY_UNIT** | Missed BUY_UNIT Event (쉔) | Slot 1 purchased (쉔) |
| `fa_364_137` | `364.5s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_366_138` | `366.0s` | **BUY_UNIT** | Missed BUY_UNIT Event (다리우스) | Slot 4 purchased (다리우스) |
| `fa_368_139` | `368.0s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_370_140` | `370.0s` | **BUY_UNIT** | Missed BUY_UNIT Event (조이) | Slot 5 purchased (조이) |
| `fa_420_141` | `420.0s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_421_142` | `421.0s` | **BUY_UNIT** | Missed BUY_UNIT Event (미스 포츈) | Slot 2 purchased (미스 포츈) |
| `fa_422_143` | `422.5s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_424_144` | `424.0s` | **BUY_UNIT** | Missed BUY_UNIT Event (소나) | Slot 1 purchased (소나) |
| `fa_425_145` | `425.0s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_428_146` | `428.5s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_430_147` | `430.0s` | **BUY_UNIT** | Missed BUY_UNIT Event (쉔) | Slot 3 purchased (쉔) |
| `fa_431_148` | `431.0s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_480_149` | `480.5s` | **ROLL** | Missed ROLL Event | Shop reroll animation confirmed |
| `fa_482_150` | `482.0s` | **BUY_UNIT** | Missed BUY_UNIT Event (소나) | Slot 2 purchased (소나) |