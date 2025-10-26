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
    Push one input bit to the encoder and return raw pins (y0, y1).
    We'll decide later which is v1/v0 via calibration.
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
            y0 = int(dut.enc_y0.value)
            y1 = int(dut.enc_y1.value)
            return (y0, y1)
        await RisingEdge(dut.clk)

    raise AssertionError("Timeout waiting for enc_out_valid")

async def _one_pass_errors(dut, mapping, payload, TB_LEN, ENC_LATENCY):
    """
    Feed one payload+tail through encoder->(optional flips 0.0)->decoder,
    using 'mapping' to pack rx_sym. Return (#errors, recovered_len).
    mapping: 'y0_is_v1'  or  'y1_is_v1'
    """
    await reset_chain(dut)
    in_stream = payload + [0] * TB_LEN

    # Encode
    coded = []
    for u in in_stream:
        y0, y1 = await enc_push_bit_and_get_symbol(dut, u, enc_latency_cycles=ENC_LATENCY)
        # Interpret pins into (v1, v0) per mapping
        if mapping == 'y0_is_v1':
            v1, v0 = y0, y1
        else:
            v1, v0 = y1, y0
        coded.append((v1, v0))

    # No noise for calibration
    noisy = coded

    # Decode
    decided = []
    for (v1, v0) in noisy:
        dut.dec_rx_sym.value    = (v1 << 1) | v0  # pack {v1,v0}
        dut.dec_sym_valid.value = 1
        await RisingEdge(dut.clk)
        dut.dec_sym_valid.value = 0

        if int(dut.dec_bit_valid.value):
            decided.append(int(dut.dec_bit_out.value))

    # Flush traceback
    for _ in range(2 * TB_LEN):
        await RisingEdge(dut.clk)
        if int(dut.dec_bit_valid.value):
            decided.append(int(dut.dec_bit_out.value))

    recovered = decided[-len(payload):]
    if len(recovered) != len(payload):
        return (len(payload), len(recovered))  # treat as all wrong if short
    errs = sum(a != b for a, b in zip(recovered, payload))
    return (errs, len(recovered))

async def calibrate_mapping(dut, TB_LEN, ENC_LATENCY, rng):
    """
    Try both mappings quickly with p=0. Choose the one with fewer errors.
    """
    test_len = 64
    payload  = [rng.randint(0, 1) for _ in range(test_len)]

    errs_a, got_a = await _one_pass_errors(dut, 'y0_is_v1', payload, TB_LEN, ENC_LATENCY)
    errs_b, got_b = await _one_pass_errors(dut, 'y1_is_v1', payload, TB_LEN, ENC_LATENCY)

    dut._log.info(f"[CAL] y0_is_v1: errs={errs_a}/{test_len}, got={got_a}")
    dut._log.info(f"[CAL] y1_is_v1: errs={errs_b}/{test_len}, got={got_b}")

    if errs_a <= errs_b:
        dut._log.info("[CAL] Selected mapping: y0_is_v1 (enc_y0=v1, enc_y1=v0)")
        return 'y0_is_v1'
    else:
        dut._log.info("[CAL] Selected mapping: y1_is_v1 (enc_y1=v1, enc_y0=v0)")
        return 'y1_is_v1'

@cocotb.test()
async def test_ber_sweep(dut):
    """
    BER sweep: RTL encoder -> bit-flip channel -> RTL Viterbi.
    Produces CSV at docs/data/ber_hw_bitflip.csv (relative to CWD).
    """
    cocotb.start_soon(Clock(dut.clk, CLK_NS, units="ns").start())

    # ---------- Knobs ----------
    TB_LEN       = 12                 # must match RTL -GTB_LEN
    PAYLOAD_LEN  = 200                # bits per trial
    TRIALS       = 20                 # trials per p_flip
    P_FLIPS      = [0.00, 0.02, 0.05, 0.10]
    ENC_LATENCY  = 0                  # set >0 if your encoder is pipelined
    rng_seed     = 42
    rng          = random.Random(rng_seed)

    # CSV path
    out_csv = os.environ.get("BER_CSV", "docs/data/ber_hw_bitflip.csv")
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)

    # ---------- Calibrate mapping at p=0 ----------
    mapping = await calibrate_mapping(dut, TB_LEN, ENC_LATENCY, rng)

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

            # 2) Encode and capture (v1, v0) using calibrated mapping
            coded = []
            for u in in_stream:
                y0, y1 = await enc_push_bit_and_get_symbol(dut, u, enc_latency_cycles=ENC_LATENCY)
                if mapping == 'y0_is_v1':
                    v1, v0 = y0, y1
                else:
                    v1, v0 = y1, y0
                coded.append((v1, v0))

            # 3) Apply independent coded-bit flips
            noisy = [(flip_bit(v1, p, rng), flip_bit(v0, p, rng)) for (v1, v0) in coded]

            # 4) Feed decoder
            decided = []
            for (v1, v0) in noisy:
                dut.dec_rx_sym.value    = (v1 << 1) | v0  # {v1,v0}
                dut.dec_sym_valid.value = 1
                await RisingEdge(dut.clk)
                dut.dec_sym_valid.value = 0

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
            "mapping": mapping,
        })

    # ---------- Write CSV ----------
    with open(out_csv, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["p_flip", "BER_hw", "errors", "total_bits", "trials",
                        "payload_len", "tb_len", "clk_ns", "seed", "mapping"]
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    dut._log.info(f"=== BER SUMMARY CSV written to: {out_csv} ===")
