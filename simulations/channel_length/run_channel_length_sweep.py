"""Sprint 3: channel length (L) sweep. Varies MOSFETParams.channel_length_cm
across three values around the Sprint 2 baseline (1 um), everything else
held fixed, and extracts V_TH/g_m/I_ON/I_OFF/SS at each via
src.simulation.characterization. See docs/roadmap.md Sprint 3 for the gate
criteria and docs/project_manual.md sec 4 for scope.

Expected direction (gradual-channel MOSFET theory): I_ON decreases as L
increases (channel resistance grows roughly linearly with L for a fixed
overdrive), independent of the ideal long-channel V_TH model used here
(no short-channel effects modeled -- see docs/limitations.md).
"""

import csv
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from src.device.mosfet_geometry import MOSFETParams
from src.simulation.parameter_sweep import (
    run_sweep, check_reproducibility, save_metrics_csv, save_id_vg_csv, save_plots, PROCESSED_DIR,
)

SWEEP_NAME = "channel_length"
PARAM_FIELD = "channel_length_cm"
PARAM_LABEL = "L (um)"
VALUES_CM = [0.5e-4, 1.0e-4, 2.0e-4]  # 0.5, 1.0 (baseline), 2.0 um


def main():
    base_params = MOSFETParams()
    results = run_sweep(SWEEP_NAME, PARAM_FIELD, VALUES_CM, base_params)

    print("\nReproducibility check (rerunning the baseline L = 1.0 um point)...")
    baseline_result = results[1]
    reproducible = check_reproducibility(SWEEP_NAME, PARAM_FIELD, VALUES_CM[1], base_params, baseline_result)
    print("  Reproducible:", "PASS" if reproducible else "FAIL")

    save_metrics_csv(SWEEP_NAME, "channel_length_cm", results)
    save_id_vg_csv(SWEEP_NAME, "channel_length_cm", results)
    save_plots(SWEEP_NAME, "channel_length_cm", PARAM_LABEL, results, display_scale=1e4)

    i_on = [r["i_on_A_per_cm"] for r in results]
    ion_decreases_with_length = all(i_on[i] > i_on[i + 1] for i in range(len(i_on) - 1))
    print("\nI_ON by L (um):", ["{0:.3e}".format(v) for v in i_on])
    print("I_ON strictly decreases with increasing L:", "PASS" if ion_decreases_with_length else "FAIL")

    checks = [
        ("reproducible on rerun", reproducible),
        ("I_ON decreases with increasing channel length", ion_decreases_with_length),
    ]

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROCESSED_DIR / "{0}_sweep_gate_summary.csv".format(SWEEP_NAME), "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["check", "passed"])
        for label, passed in checks:
            writer.writerow([label, passed])

    all_passed = all(passed for _, passed in checks)
    print("\nChannel length sweep gate:", "PASS" if all_passed else "FAIL")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
