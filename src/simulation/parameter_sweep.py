"""Shared driver for Sprint 3's three parameter sweeps (channel length,
oxide thickness, channel doping -- docs/project_manual.md sec 4). Each
sweep varies exactly one src.device.mosfet_geometry.MOSFETParams field
across three values and runs src.simulation.characterization.characterize_device
per value; this module owns the repeated CSV/plot/reproducibility-check
plumbing so the three simulations/{channel_length,oxide_thickness,doping}
driver scripts stay thin and only state what's swept.
"""

import csv
import dataclasses
import pathlib

from src.device.mosfet_geometry import MOSFETParams
from src.simulation.characterization import characterize_device
from src.simulation.mosfet_solver import reset_devsim_clean

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "results" / "raw"
PROCESSED_DIR = REPO_ROOT / "results" / "processed"
FIGURES_DIR = REPO_ROOT / "results" / "figures"

METRIC_COLUMNS = [
    "vth_V", "gm_max_A_per_cm_per_V", "ss_mV_per_decade",
    "i_on_A_per_cm", "i_off_A_per_cm", "ion_ioff_ratio",
]


def run_one(tag: str, param_field: str, value: float, base_params: MOSFETParams) -> dict:
    # A fresh reset per run is required, not just tidiness: building a
    # second device in the same session without it hit a "Convergence
    # failure!" on the very first potential-only solve, on a device
    # configuration (the baseline point) that solves fine on its own --
    # leftover global state (parameter/model names shared across devices)
    # from the previous run corrupted the next one. Confirmed by direct
    # experiment while building this sweep. See reset_devsim_clean() in
    # mosfet_solver.py for why plain devsim.reset_devsim() isn't enough.
    reset_devsim_clean()
    params = dataclasses.replace(base_params, **{param_field: value})
    mesh_name = "{0}_mesh".format(tag)
    device_name = tag
    result = characterize_device(mesh_name, device_name, params)
    result["param_value"] = value
    return result


def run_sweep(sweep_name: str, param_field: str, values, base_params: MOSFETParams = MOSFETParams()) -> list:
    """Runs `characterize_device` once per value in `values`, varying only
    `param_field` on top of `base_params`. Each run gets its own DEVSIM
    mesh/device name so all runs can coexist in one process. Returns the
    list of per-value result dicts (see characterize_device), each tagged
    with `param_value`."""
    results = []
    for i, value in enumerate(values):
        tag = "{0}_run{1}".format(sweep_name, i)
        print("\n[{0}] {1} = {2:g}".format(sweep_name, param_field, value))
        result = run_one(tag, param_field, value, base_params)
        print("  V_TH = {0:.4f} V, g_m_max = {1:.3e} A/cm/V, SS = {2:.1f} mV/dec, "
              "I_ON = {3:.3e} A/cm, I_OFF = {4:.3e} A/cm, I_ON/I_OFF = {5:.3e}".format(
                  result["vth_V"], result["gm_max_A_per_cm_per_V"], result["ss_mV_per_decade"],
                  result["i_on_A_per_cm"], result["i_off_A_per_cm"], result["ion_ioff_ratio"]))
        results.append(result)
    return results


def check_reproducibility(sweep_name: str, param_field: str, value: float, base_params: MOSFETParams,
                           reference: dict, rtol: float = 1e-6) -> bool:
    """Reruns a single sweep point (fresh DEVSIM mesh/device name) and
    checks V_TH/I_ON/I_OFF match the first run's result within `rtol` --
    DEVSIM's solve is deterministic given the same inputs, so this is a
    real reproducibility check, not a formality."""
    tag = "{0}_repro_check".format(sweep_name)
    rerun = run_one(tag, param_field, value, base_params)
    for key in ("vth_V", "i_on_A_per_cm", "i_off_A_per_cm"):
        a, b = reference[key], rerun[key]
        scale = max(abs(a), abs(b)) or 1.0
        if abs(a - b) > rtol * scale:
            print("  Reproducibility check FAILED on {0}: {1} vs {2}".format(key, a, b))
            return False
    return True


def save_metrics_csv(sweep_name: str, param_name: str, results: list) -> pathlib.Path:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = PROCESSED_DIR / "{0}_sweep_metrics.csv".format(sweep_name)
    with open(out_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([param_name] + METRIC_COLUMNS)
        for r in results:
            writer.writerow([r["param_value"]] + [r[c] for c in METRIC_COLUMNS])
    return out_csv


def save_id_vg_csv(sweep_name: str, param_name: str, results: list) -> pathlib.Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = RAW_DIR / "{0}_sweep_id_vg.csv".format(sweep_name)
    with open(out_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([param_name, "gate_bias_V", "drain_current_A_per_cm"])
        for r in results:
            for vg, i_d in zip(r["gate_sweep_V"], r["id_vg_linear_A_per_cm"]):
                writer.writerow([r["param_value"], vg, i_d])
    return out_csv


def save_plots(sweep_name: str, param_name: str, param_label: str, results: list, display_scale: float = 1.0) -> None:
    """display_scale converts the stored param value (cgs) to the unit named in param_label, e.g. 1e4 for cm -> um."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    values = [r["param_value"] * display_scale for r in results]

    fig, axes = plt.subplots(1, 3, figsize=(13, 4))
    axes[0].plot(values, [r["vth_V"] for r in results], marker="o")
    axes[0].set_ylabel("V_TH (V)")
    axes[1].semilogy(values, [r["i_on_A_per_cm"] for r in results], marker="o", label="I_ON")
    axes[1].semilogy(values, [r["i_off_A_per_cm"] for r in results], marker="s", label="I_OFF")
    axes[1].set_ylabel("|I_D| (A/cm)")
    axes[1].legend()
    axes[2].plot(values, [r["ss_mV_per_decade"] for r in results], marker="o")
    axes[2].set_ylabel("SS (mV/decade)")
    for ax in axes:
        ax.set_xlabel(param_label)
    fig.suptitle("Sprint 3: {0} sweep".format(sweep_name))
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "{0}_sweep_metrics.png".format(sweep_name), dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 4.5))
    for r in results:
        id_plot = [max(abs(i), 1e-30) for i in r["id_vg_linear_A_per_cm"]]
        ax.semilogy(r["gate_sweep_V"], id_plot, label="{0} = {1:g}".format(param_label, r["param_value"] * display_scale))
    ax.set_xlabel("V_G (V)")
    ax.set_ylabel("|I_D| (A/cm)")
    ax.set_title("Sprint 3: {0} -- I_D-V_G by {1}".format(sweep_name, param_label))
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "{0}_sweep_id_vg.png".format(sweep_name), dpi=150)
    plt.close(fig)
