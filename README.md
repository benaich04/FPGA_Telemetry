# 🚀 FPGA Telemetry Communication System — Convolutional Coding + Viterbi Decoding

## 📘 Overview
This project implements and validates a **hardware-based digital telemetry system** using **FPGA-synthesizable Verilog modules** for convolutional encoding and Viterbi decoding.  
The objective is to evaluate the **bit error rate (BER)** performance under noisy channel conditions and compare **hardware-level results** against **software and MATLAB analytical models**.

The framework integrates:
- ✅ **Hardware RTL** (Encoder, Decoder, BER Tester)
- 🧪 **Cocotb + Verilator** simulation testbench
- 🐍 **Python** theoretical modeling and visualization scripts
- 📊 **MATLAB** utilities for reference BER comparison

---

## 🧠 System Concept

Telemetry systems — such as satellite downlinks, UAV communication, or remote sensing — rely on **error-correcting codes** to ensure data reliability over noisy channels.  
This project models that chain:

Input Data → Convolutional Encoder → Noisy Channel (Bit-Flips) → Viterbi Decoder → BER Tester


The encoder uses a **rate-1/2 convolutional code** with generators **(7,5)₈**, and the decoder employs a **hard-decision Viterbi algorithm**.  
Each stage is implemented at the RTL level and validated in a **Cocotb/Verilator** simulation environment.

---

## 📁 Repository Structure


---

## 🧩 File Role Summary

| Component | File | Description |
|------------|------|-------------|
| **Encoder** | `convenc.v` | Implements rate-1/2 convolutional encoder with shift-register architecture using generator polynomials (7,5)₈. |
| **Decoder** | `viterbi_hard.v` | Hard-decision Viterbi decoder with traceback mechanism; parameterized traceback length `TB_LEN`. |
| **BER Tracker** | `ber_tester.v` | Counts total transmitted bits and bit errors between reference and decoded sequences. |
| **Top Wrapper** | `top_cv.v` | Integrates encoder, decoder, and BER modules for full-chain simulation. |
| **Simulator** | `sim/test_ber_sweep.py` | Performs Monte Carlo BER sweeps across multiple noise probabilities using Cocotb. |
| **Build System** | `sim/Makefile` | Compiles RTL modules with Verilator and launches Cocotb simulation with configurable parameters. |
| **Visualization** | `scripts/generate_readme_artifacts.py` | Generates theoretical BER data and figures for documentation. |
| **Results** | `docs/data/*.csv` | Stores measured and theoretical BER outputs for analysis. |
| **MATLAB Scripts** | `matlab/*.m` | Provide analytical and comparative validation for FPGA-level results. |

---

## 📊 Python Analysis (`scripts/generate_readme_artifacts.py`)

This script generates **reference data** and **visual plots** to validate the communication chain and visualize the performance of the (7,5) convolutional code.

### Output Artifacts

| Artifact | Description |
|-----------|--------------|
| `docs/data/ber_results.csv` | Theoretical BER results for uncoded and coded BPSK. |
| `docs/figures/BER_curves_coded_vs_uncoded.png` | Compares theoretical BER of uncoded BPSK vs coded convolutional system. |
| `docs/figures/BPSK_constellation.png` | Shows the BPSK constellation with additive noise. |
| `docs/figures/BPSK_eye_diagram.png` | Eye diagram visualizing inter-symbol interference. |
| `docs/figures/BPSK_time_segment.png` | Matched-filter output (time-domain sample sequence). |

#### Example Figures

**BER vs Eb/N₀ (Coded vs Uncoded):**  
<img width="1116" height="756" alt="BER_curves_coded_vs_uncoded" src="https://github.com/user-attachments/assets/dab74201-466d-4302-ae9b-d231c6c9f975" />

**BPSK Constellation:**  
<img width="720" height="720" alt="BPSK_constellation" src="https://github.com/user-attachments/assets/f1fb70f4-f7f8-47b4-99f4-9c19f6802909" />

**Eye Diagram:**  
<img width="1260" height="720" alt="BPSK_eye_diagram" src="https://github.com/user-attachments/assets/8ca400ae-b63f-4d4c-8072-e50532c54701" />

**Matched-Filter Output:** 
<img width="1620" height="576" alt="BPSK_time_segment" src="https://github.com/user-attachments/assets/4c7bedf8-96e8-4eff-9a80-ec43a56aeed7" />


## 🧪 Running Hardware Simulations

### Step 1 — Activate Environment
```bash
source ~/venv-cocotb/bin/activate

```


### 📁 Step 2 — Navigate to Simulation Directory

```bash
cd sim
```

### 🚀 Step 3 — Run BER Sweep Test

```bash
make ber_sweep
```

This executes **`test_ber_sweep.py`**, which performs the following:

* Generates random input payloads
* Encodes bits using **`convenc.v`**
* Simulates a noisy **bit-flip channel**
* Decodes using **`viterbi_hard.v`**
* Computes and logs BER results into **`docs/data/ber_hw_bitflip.csv`**

#### 🖥️ View Simulation Waveforms

You can inspect internal RTL signals using **GTKWave**:

```bash
gtkwave sim_build/trace.fst
```

---

## 📈 MATLAB Reference (Optional)

1. Open **`matlab/ber_theory_conv.m`** to compute analytical BER curves.
2. Use **`compare_fpga_vs_matlab.m`** to visualize FPGA vs MATLAB results.
3. Validate that **hardware** and **theory** exhibit similar BER trends across varying SNR.

---

## 🧭 Next Steps

| Goal                     | Description                                                                                 |
| ------------------------ | ------------------------------------------------------------------------------------------- |
| ✅ AWGN Channel           | Replace the random bit-flip model with a Gaussian noise channel for more realistic results. |
| ⚙️ Soft-Decision Decoder | Integrate a soft-decision Viterbi decoder for an expected ~2 dB coding gain.                |
| 🧩 FPGA Deployment       | Synthesize the RTL on an FPGA board (e.g., Artix-7 or Zynq) and measure real-time BER.      |
| 🧠 Extended Model        | Add BPSK/QPSK modulation, telemetry packet framing, and downlink synchronization.           |

---

## ⚠️ Known Issues

* Hardware BER results remained near **0.5** — caused by decoder-symbol alignment mismatch.
* Bitstream synchronization and traceback window calibration require further adjustment.
* Possible timing misalignment between encoder and decoder handoff inside **`top_cv.v`**.

---

## 🧰 For Future Reference

If you need to **rerun the full flow**:

```bash
# From project root
cd sim
make clean_local
make ber_sweep
```

If you want to **regenerate README figures**:

```bash
cd scripts
python3 generate_readme_artifacts.py
```

---

## 👨‍💻 Author

**Mohamed Benaich**
Electrical Engineering @ NYU Abu Dhabi
GitHub: [benaich04](https://github.com/benaich04)
Email: [mb9194@nyu.edu](mailto:mb9194@nyu.edu)

```
```
