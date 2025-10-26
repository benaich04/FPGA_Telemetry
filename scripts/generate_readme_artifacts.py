# Generates README-ready artifacts for a BPSK + (7,5) conv code + Viterbi link.
# Outputs to: docs/figures/*.png and docs/data/ber_results.csv

import os, math, numpy as np, matplotlib.pyplot as plt, pandas as pd
rng = np.random.default_rng(42)

FIG_DIR = "docs/figures"
DATA_DIR = "docs/data"
os.makedirs(FIG_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# ---- Convolutional (7,5)_oct, K=3 ----
def conv_encode_7_5(bits):
    g1, g2 = 0b111, 0b101
    state = 0
    out = []
    for b in bits:
        state = ((state << 1) | (b & 1)) & 0b111
        v1 = bin(state & g1).count("1") & 1
        v0 = bin(state & g2).count("1") & 1
        out.extend([v1, v0])
    return np.array(out, dtype=int)

def add_tail(bits, K=3):
    return np.concatenate([bits, np.zeros(K-1, dtype=int)])

# ---- Trellis precompute for hard Viterbi ----
K = 3
m = K - 1
NUM_STATES = 1 << m

def _precompute():
    g1, g2 = 0b111, 0b101
    next_state = np.zeros((NUM_STATES, 2), dtype=int)
    out_bits   = np.zeros((NUM_STATES, 2, 2), dtype=int)
    for s in range(NUM_STATES):
        for u in (0,1):
            new_shift = ((s << 1) | u) & ((1 << K) - 1)
            v1 = bin(new_shift & g1).count("1") & 1
            v0 = bin(new_shift & g2).count("1") & 1
            next_state[s,u] = ((s << 1) | u) & ((1 << (K-1)) - 1)
            out_bits[s,u,0], out_bits[s,u,1] = v1, v0
    return next_state, out_bits

NEXT_STATE, OUT_BITS = _precompute()

def viterbi_decode_hard_7_5(rx_pairs):
    T = len(rx_pairs) // 2
    INF = 10**9
    pm = np.full((T+1, NUM_STATES), INF, dtype=int)
    prev = np.full((T+1, NUM_STATES), -1, dtype=int)
    prev_u = np.full((T+1, NUM_STATES), -1, dtype=int)
    pm[0,0] = 0
    for t in range(T):
        r1, r0 = rx_pairs[2*t], rx_pairs[2*t+1]
        for s in range(NUM_STATES):
            if pm[t,s] >= INF: continue
            for u in (0,1):
                ns = NEXT_STATE[s,u]
                v1, v0 = OUT_BITS[s,u]
                bm = (v1 ^ r1) + (v0 ^ r0)
                cand = pm[t,s] + bm
                if cand < pm[t+1,ns]:
                    pm[t+1,ns] = cand
                    prev[t+1,ns] = s
                    prev_u[t+1,ns] = u
    s = int(np.argmin(pm[T]))
    uhat = np.zeros(T, dtype=int)
    for t in range(T,0,-1):
        uhat[t-1] = prev_u[t,s]
        s = prev[t,s] if prev[t,s] >= 0 else 0
    return uhat

# ---- BPSK & simple rectangular pulse shaping ----
def bpsk_map(bits):  # 0->+1, 1->-1
    return 1 - 2*bits

def add_awgn(sig, snr_db):
    snr_lin = 10**(snr_db/10.0)   # Es/N0
    var = 1/(2*snr_lin)           # real AWGN variance per dim
    noise = rng.normal(0, math.sqrt(var), size=sig.shape)
    return sig + noise

def upsample_rect(symbols, sps):
    return np.repeat(symbols, sps)

def matched_filter_rect(rx, sps):
    h = np.ones(sps)
    y = np.convolve(rx, h, mode="same")
    centers = np.arange(sps//2, len(y), sps)
    return y, y[centers], centers

def eye_traces(mf, sps, ntr=100):
    span = 2*sps
    traces = []
    for k in range(ntr):
        st = k*sps
        if st+span <= len(mf):
            traces.append(mf[st:st+span])
        else:
            break
    return np.vstack(traces) if traces else np.empty((0, span))

# ---- BER sweep ----
def simulate_ber(nbits=20000, ebn0_list=(0,1,2,3,4,5,6,7), sps=8):
    rows = []
    for eb in ebn0_list:
        payload = rng.integers(0,2, size=nbits, dtype=int)
        bits_tx = add_tail(payload, K)
        coded   = conv_encode_7_5(bits_tx)
        syms    = bpsk_map(coded)
        tx      = upsample_rect(syms, sps)
        rx      = add_awgn(tx, eb)
        mf, samp, _ = matched_filter_rect(rx, sps)
        hard    = (samp < 0).astype(int)
        dec     = viterbi_decode_hard_7_5(hard)
        dec_payload = dec[:len(payload)]
        ber_coded = np.mean(dec_payload != payload)

        # Uncoded reference
        u_bits = rng.integers(0,2, size=nbits, dtype=int)
        u_syms = bpsk_map(u_bits)
        u_tx   = upsample_rect(u_syms, sps)
        u_rx   = add_awgn(u_tx, eb)
        _, u_samp, _ = matched_filter_rect(u_rx, sps)
        u_hard = (u_samp < 0).astype(int)
        ber_uncoded = np.mean(u_hard != u_bits)

        rows.append({"EbN0_dB": eb, "BER_coded": ber_coded, "BER_uncoded": ber_uncoded})
    return pd.DataFrame(rows)

def make_signal_illustrations(ebn0_db=3.0, sps=8, seg_symbols=40):
    bits = np.array([0,1,1,0, 1,0,0,1, 1,1,0,0, 1,0,1,1], dtype=int)
    bits = add_tail(bits, K)
    coded = conv_encode_7_5(bits)
    syms  = bpsk_map(coded)
    tx    = upsample_rect(syms, sps)
    rx    = add_awgn(tx, ebn0_db)
    mf, samp, centers = matched_filter_rect(rx, sps)

    # 1) Matched-filter time segment
    end = min(len(mf), seg_symbols*sps)
    t = np.arange(end)/sps
    plt.figure(figsize=(9,3.2))
    plt.plot(t, mf[:end])
    c_in = centers[centers < end]
    plt.scatter(c_in/sps, mf[c_in], s=15)
    plt.title("BPSK Matched-Filter Output (Segment)")
    plt.xlabel("Symbols"); plt.ylabel("Amplitude")
    plt.tight_layout()
    plt.savefig(f"{FIG_DIR}/BPSK_time_segment.png", dpi=180); plt.close()

    # 2) “Constellation” snapshot (sampled)
    plt.figure(figsize=(4,4))
    i_vals = samp
    q_vals = np.zeros_like(i_vals) + rng.normal(0, 0.02, size=i_vals.shape)
    plt.scatter(i_vals, q_vals, s=10)
    plt.axvline(0, linestyle="--")
    plt.title(f"BPSK Constellation (Eb/N0={ebn0_db:.1f} dB)")
    plt.xlabel("In-Phase"); plt.ylabel("Quadrature")
    plt.tight_layout()
    plt.savefig(f"{FIG_DIR}/BPSK_constellation.png", dpi=180); plt.close()

    # 3) Eye diagram
    trs = eye_traces(mf, sps, ntr=100)
    plt.figure(figsize=(7,4))
    for tr in trs:
        plt.plot(np.arange(len(tr))/sps, tr, linewidth=0.8)
    plt.title("BPSK Eye Diagram (Rectangular Pulse)")
    plt.xlabel("Symbols"); plt.ylabel("Amplitude")
    plt.tight_layout()
    plt.savefig(f"{FIG_DIR}/BPSK_eye_diagram.png", dpi=180); plt.close()

def main():
    # BER sweep
    df = simulate_ber()
    # Avoid log(0) on plots: clamp zeros to a tiny floor just for visualization
    df_plot = df.copy()
    for col in ("BER_coded","BER_uncoded"):
        df_plot[col] = np.maximum(df_plot[col], 1e-6)
    df.to_csv(f"{DATA_DIR}/ber_results.csv", index=False)

    # Plot BER curves
    plt.figure(figsize=(6.2,4.2))
    plt.semilogy(df_plot["EbN0_dB"], df_plot["BER_uncoded"], marker="o", label="Uncoded BPSK")
    plt.semilogy(df_plot["EbN0_dB"], df_plot["BER_coded"],   marker="s", label="Conv (7,5) + Viterbi")
    plt.grid(True, which="both", linestyle="--", linewidth=0.5)
    plt.xlabel("Eb/N0 (dB)"); plt.ylabel("Bit Error Rate")
    plt.title("BER vs Eb/N0 — Coded vs Uncoded")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"{FIG_DIR}/BER_curves_coded_vs_uncoded.png", dpi=180); plt.close()

    # Signal illustrations
    make_signal_illustrations()

if __name__ == "__main__":
    main()
