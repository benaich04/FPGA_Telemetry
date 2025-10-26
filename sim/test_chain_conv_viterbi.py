# sim/test_ber_sweep.py
import os
import csv
import random
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

CLK_NS = 10  # 100 MHz

def flip_bit(b: int, p: float, rng: random.Random) -> int:
    return b ^ 1 if rng.random() < p else b

async def reset_chain(dut):
    # Active-low reset for encoder, active-high for decoder (per your DUT)
    dut.enc_rst_n.value = 0
    dut.dec_rst.value   = 1

    # Deassert inputs
    dut.enc_in_valid.value  = 0
    dut.enc_bit_in.value    = 0
    dut.dec_sym_valid.value = 0
    dut.dec_rx_sym.value    = 0

    # Let resets propagate
    for _ in range(5):
        await RisingEdge(dut.clk)

    # Release resets
    dut.enc_rst_n.value = 1
    dut.dec_rst.value   = 0
    await RisingEdge(dut.clk)

async def enc_push_bit_and_get_symbol(dut, u: int, enc_latency_cycles: int = 0, timeout_cycles: int = 16):
    """
    Push one input bit to the encoder and return (v1, v0).
    - enc_latency_cycles: set to 0 if your encoder outputs valid in the same cycle.
                          increase if your encoder has pipeline latency.
    """
    # Drive input for one cycle
    dut.enc_in_valid.value = 1
    dut.enc_bit_in.value   = u
    await RisingEdge(dut.clk)
    dut.enc_in_valid.value = 0

    # Wait for encoder latency (if any)
    for _ in range(enc_latency_cycles):
        await RisingEdge(dut.clk)

    # Wait until enc_out_valid is asserted (robustness)
    for _ in range(timeout_cycles):
        if int(dut.enc_out_valid.value):
            v1 = int(dut.enc_y0.value)  # your naming: y0 = v1, y1 = v0 in the original comment
            v0 = int(dut.enc_y1.value)
            return (v1, v0)
        await RisingEdge(dut.clk)

    raise AssertionError("Timeout waiting for enc_out_valid")

@cocotb.test()
async def test_ber_sweep(dut):
    """
    BER sweep: RTL encoder -> bit-flip channel -> RTL Viterbi.
    Produces CSV at docs/data/ber_hw_bitflip.csv with columns:
    p_flip, BER_hw, errors, total_bits, trials, payload_len, tb_len, clk_ns, seed
    """
    cocotb.start_soon(Clock(dut.clk, CLK_NS, units="ns").start())

    # ---------- Knobs ----------
    TB_LEN       = 12                 # must match your RTL traceback/tail length
    PAYLOAD_LEN  = 200                # bits per trial
    TRIALS       = 20                 # trials per p_flip
    P_FLIPS      = [0.00, 0.02, 0.05, 0.10]
    ENC_LATENCY  = 0                  # set >0 if your encoder has pipeline latency
    rng_seed     = 42
    rng          = random.Random(rng_seed)

    # CSV path (allow override via env if desired)
    out_csv = os.environ.get("BER_CSV", "docs/data/ber_hw_bitflip.csv")
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)

    # ---------- Sweep ----------
    rows = []
    for p in P_FLIPS:
        bit_errors = 0
        bit_total  = 0

        for _ in range(TRIALS):
            await reset_chain(dut)

            # 1) Generate payload + tail to terminate trellis
            payload   = [rng.randint(0, 1) for _ in range(PAYLOAD_LEN)]
            in_stream = payload + [0] * TB_LEN

            # 2) Encode and capture (v1, v0) symbols
            coded = []
            for u in in_stream:
                v1, v0 = await enc_push_bit_and_get_symbol(dut, u, enc_latency_cycles=ENC_LATENCY)
                coded.append((v1, v0))

            # 3) Apply independent coded-bit flips
            noisy = [(flip_bit(v1, p, rng), flip_bit(v0, p, rng)) for (v1, v0) in coded]

            # 4) Feed decoder
            decided = []
            for (v1, v0) in noisy:
                dut.dec_rx_sym.value    = (v1 << 1) | v0  # pack {v1,v0} -> [1:0]
                dut.dec_sym_valid.value = 1
                await RisingEdge(dut.clk)
                dut.dec_sym_valid.value = 0

                # Collect decided bits whenever valid
                if int(dut.dec_bit_valid.value):
                    decided.append(int(dut.dec_bit_out.value))

            # Drain a few extra cycles to flush the traceback output
            for _ in range(2 * TB_LEN):
                await RisingEdge(dut.clk)
                if int(dut.dec_bit_valid.value):
                    decided.append(int(dut.dec_bit_out.value))

            # 5) Compare last PAYLOAD_LEN bits (discard tail decisions)
            recovered = decided[-PAYLOAD_LEN:]
            if len(recovered) != PAYLOAD_LEN:
                raise AssertionError(f"Not enough decided bits: got {len(recovered)} needed {PAYLOAD_LEN}")

            errs = sum(a != b for a, b in zip(recovered, payload))
            bit_errors += errs
            bit_total  += PAYLOAD_LEN

        ber = (bit_errors / bit_total) if bit_total else 0.0
        dut._log.info(f"[BER] p_flip={p:.3f}  errors={bit_errors}/{bit_total}  BER={ber:.6f}")
        rows.append({
            "p_flip": p,
            "BER_hw": ber,
            "errors": bit_errors,
            "total_bits": bit_total,
            "trials": TRIALS,
            "payload_len": PAYLOAD_LEN,
            "tb_len": TB_LEN,
            "clk_ns": CLK_NS,
            "seed": rng_seed,
        })

    # ---------- Write CSV ----------
    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["p_flip", "BER_hw", "errors", "total_bits", "trials",
                        "payload_len", "tb_len", "clk_ns", "seed"]
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    dut._log.info(f"=== BER SUMMARY CSV written to: {out_csv} ===")
