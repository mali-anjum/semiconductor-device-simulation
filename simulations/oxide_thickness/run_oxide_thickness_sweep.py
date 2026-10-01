"""Sprint 3: gate oxide thickness (t_ox) sweep. Varies
MOSFETParams.oxide_thickness_cm across three values around the Sprint 2
baseline (10 nm), everything else held fixed. See docs/roadmap.md Sprint 3
for gate criteria and docs/project_manual.md sec 4 for scope.

Expected direction: thinner oxide -> higher gate capacitance C_ox = eps_ox
eps0 / t_ox -> lower V_TH and higher I_ON (docs/physics.md sec 7 V_TH
formula: the body-charge term is divided by C_ox, so V_TH increases with
t_ox; stronger gate coupling at a given V_G also drives more channel
charge, raising I_ON).
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

SWEEP_NAME = "oxide_thickness"
PARAM_FIELD = "oxide_thickness_cm"
PARAM_LABEL = "t_ox (nm)"
VALUES_CM = [0.5e-6, 1.0e-6, 2.0e-6]  # 5, 10 (baseline), 20 nm


def main():
    base_params = MOSFETParams()
    results = run_sweep(SWEEP_NAME, PARAM_FIELD, VALUES_CM, base_params)

    print("\nReproducibility check (rerunning the baseline t_ox = 10 nm point)...")
    baseline_result = results[1]
    reproducible = check_reproducibility(SWEEP_NAME, PARAM_FIELD, VALUES_CM[1], base_params, baseline_result)
    print("  Reproducible:", "PASS" if reproducible else "FAIL")

    save_metrics_csv(SWEEP_NAME, "oxide_thickness_cm", results)
    save_id_vg_csv(SWEEP_NAME, "oxide_thickness_cm", results)
    save_plots(SWEEP_NAME, "oxide_thickness_cm", PARAM_LABEL, results, display_scale=1e7)

    vth = [r["vth_V"] for r in results]
    i_on = [r["i_on_A_per_cm"] for r in results]
    vth_increases_with_tox = all(vth[i] < vth[i + 1] for i in range(len(vth) - 1))
    ion_decreases_with_tox = all(i_on[i] > i_on[i + 1] for i in range(len(i_on) - 1))
    print("\nV_TH by t_ox (cm):", ["{0:.4f}".format(v) for v in vth])
    print("I_ON by t_ox (cm):", ["{0:.3e}".format(v) for v in i_on])
    print("V_TH strictly increases with increasing t_ox:", "PASS" if vth_increases_with_tox else "FAIL")
    print("I_ON strictly decreases with increasing t_ox:", "PASS" if ion_decreases_with_tox else "FAIL")

    checks = [
        ("reproducible on rerun", reproducible),
        ("V_TH increases with increasing oxide thickness", vth_increases_with_tox),
        ("I_ON decreases with increasing oxide thickness", ion_decreases_with_tox),
    ]

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROCESSED_DIR / "{0}_sweep_gate_summary.csv".format(SWEEP_NAME), "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["check", "passed"])
        for label, passed in checks:
            writer.writerow([label, passed])

    all_passed = all(passed for _, passed in checks)
    print("\nOxide thickness sweep gate:", "PASS" if all_passed else "FAIL")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
