import cocotb
from cocotb.triggers import RisingEdge
from cocotb.clock import Clock

# tiny reference encoder for (7,5), K=3
def conv_ref(bits):
    d1 = d0 = 0
    out = []
    for u in bits:
        y0 = (u ^ d1 ^ d0) & 1
        y1 = (u ^ d0) & 1
        out.append((y0, y1))
        d0, d1 = d1, u
    return out

@cocotb.test()
async def test_convenc_smoke(dut):
    # clock & reset
    cocotb.start_soon(Clock(dut.clk, 10, units="ns").start())
    dut.rst_n.value = 0 # assert reset (active-low)
    dut.in_valid.value = 0 # no input yet
    dut.bit_in.value = 0 # default input bit
    for _ in range(5): # hold reset for 5 clock cycles
        await RisingEdge(dut.clk)
    dut.rst_n.value = 1 # deassert reset (release)

    await RisingEdge(dut.clk)  # give DUT one cycle to come out of reset

    # a tiny known pattern, easy to eyeball
    src = [1,0,1,1,0,0,1]  # 7 bits
    ref = conv_ref(src) #refernece output computed using conv_ref

    got = []
    for b in src: #go through element in the input bits 
        dut.in_valid.value = 1      #set the in_valid to 1
        dut.bit_in.value = b        #set the input bit to the b-th element in the src input
        await RisingEdge(dut.clk)   #wait for a clk cycle
        dut.in_valid.value = 0      #set the in_valid to 0

        if int(dut.out_valid.value): #if the out_valid is 1
            y0 = int(dut.y0.value)   #take the y0 from the module and assign it to z0 
            y1 = int(dut.y1.value)
            got.append((y0,y1))

    # drain a few cycles (not strictly needed here)
    for _ in range(4):      #wait for 4 clk cycles
        await RisingEdge(dut.clk)
        if int(dut.out_valid.value): #if out_valid is 1
            got.append((int(dut.y0.value), int(dut.y1.value)))

    assert got[:len(ref)] == ref, f"Mismatch!\n got={got}\n ref={ref}" #important part to compute the expected outputs and compare against the DUT
