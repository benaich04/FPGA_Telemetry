# 🚀 FPGA Telemetry Communication System — Convolutional Coding + Viterbi Decoding

## Overview
This project implements and tests a **hardware-based digital telemetry system** using **FPGA-synthesizable Verilog modules** for convolutional encoding and Viterbi decoding.  
The goal is to evaluate **error-correcting performance (BER)** under simulated bit-flip noise and compare hardware-level results against **software and MATLAB reference models**.

The project integrates:
- **Hardware RTL** (encoder, decoder, BER tester)
- **Cocotb/Verilator simulation environment**
- **Python scripts** for theoretical and visualization analysis
- **MATLAB utilities** for analytical BER comparisons

---

## 🧠 Project Idea

In telemetry systems (e.g., satellite downlinks or UAV communication), data must be transmitted reliably despite noise.  
This system simulates such a channel by encoding binary data using a **rate-1/2 convolutional code** (generators (7,5)₈), adding noise, and recovering it with a **hard-decision Viterbi decoder**.

### System Flow


Each stage is fully implemented in Verilog and tested via **Cocotb** at the RTL level.

---

## 📁 Repository Structure


---

## 🧩 File Roles Summary

| Component | File | Description |
|------------|------|-------------|
| Encoder | `convenc.v` | Implements rate-1/2 convolutional code (7,5)₈ with 2 memory registers. |
| Decoder | `viterbi_hard.v` | Viterbi decoder for hard-decision decoding, parameterized traceback depth (`TB_LEN`). |
| BER Tracker | `ber_tester.v` | Counts total bits vs. errors for hardware BER estimation. |
| Top Wrapper | `top_cv.v` | Integrates encoder, decoder, and BER logic for end-to-end tests. |
| Simulator | `sim/test_ber_sweep.py` | Python + Cocotb test that performs multi-trial BER sweeps with bit flips. |
| Makefile | `sim/Makefile` | Handles compilation with Verilator, test execution, and waveform dumping. |
| Visualization | `scripts/generate_readme_artifacts.py` | Generates Python-based theoretical and visualization results for README. |
| Results | `docs/data/*.csv` | Contains output from both simulation and theoretical models. |

---

## 📊 Python Analysis (`generate_readme_artifacts.py`)

This script generates software-level reference data and visual plots for documentation and analysis.

### It Produces:
- **`docs/data/ber_results.csv`** — Theoretical BER values for uncoded and coded BPSK.
- **Figures:**
  - ![BER vs Eb/N0 — Coded vs Uncoded](docs/figures/BER_curves_coded_vs_uncoded.png)
  - ![BPSK Constellation](docs/figures/BPSK_constellation.png)
  - ![BPSK Eye Diagram](docs/figures/BPSK_eye_diagram.png)
  - ![BPSK Matched-Filter Output](docs/figures/BPSK_time_segment.png)

These illustrate both modulation characteristics and coding performance trends.

---

## 🧪 Running Hardware Simulations

### Step-by-Step

1. **Activate your cocotb environment:**
   ```bash
   source ~/venv-cocotb/bin/activate


