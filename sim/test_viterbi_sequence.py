# sim/test_viterbi_sequence.py
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

CLK_NS = 10  # 100 MHz

def enc_7_5(u_bits):
    # s = {s1,s0} = {u[k-2], u[k-1]}, start {0,0}; next = {s0, u}
    s1, s0 = 0, 0
    out = []
    for u in u_bits:
        v1 = u ^ s0 ^ s1  # 111
        v0 = u ^ s1       # 101
        out.append((v1, v0))
        s1, s0 = s0, u
    return out

@cocotb.test()
async def test_viterbi_basic(dut):
    """
    One coded-bit flip on the 4th symbol, with a trellis-consistent tail.
    Original: 11 01 01 00 01
    Flipped : 11 01 01 10 01   (flip v1 in 4th symbol)
    Expect decoded bits: [1, 1, 0, 1, 1]
    """
    cocotb.start_soon(Clock(dut.clk, CLK_NS, units="ns").start())

    # Reset
    dut.rst.value = 1; dut.sym_valid.value = 0; dut.rx_sym.value = 0
    for _ in range(5): await RisingEdge(dut.clk)
    dut.rst.value = 0; await RisingEdge(dut.clk)

    # Payload and a proper tail (these zeros are INPUT bits to the encoder)
    u_payload = [1,1,0,1,1]
    u_tail    = [0,0,0,0,0]          # long-ish tail to flush decisions
    coded     = enc_7_5(u_payload + u_tail)

    # Apply ONE coded-bit flip to symbol index 3 (0-based): (v1,v0) -> (v1^1, v0)
    coded[3] = (coded[3][0] ^ 1, coded[3][1])

    # Drive the DUT
    got = []
    for (v1, v0) in coded:
        dut.rx_sym.value = (v1 << 1) | v0
        dut.sym_valid.value = 1
        await RisingEdge(dut.clk)
        if int(dut.bit_valid.value):
            got.append(int(dut.bit_out.value))
        dut.sym_valid.value = 0

    # Check last 5 decided bits against payload
    assert len(got) >= len(u_payload)
    dec = got[-len(u_payload):]
    dut._log.info(f"Decoded 5-bit stream: {dec}")
    assert dec == u_payload, f"Decoded mismatch: got {dec}, want {u_payload}"
