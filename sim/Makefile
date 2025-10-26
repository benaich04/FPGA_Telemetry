# =====================  Cocotb + Verilator Makefile  =====================

TOPLEVEL_LANG ?= verilog
SIM           ?= verilator

# Waves: FST by default (faster than VCD)
WAVE ?= fst
ifeq ($(WAVE),fst)
  EXTRA_ARGS += --trace-fst
else
  EXTRA_ARGS += --trace
endif

# Verilator timing mode (avoid NEEDTIMINGOPT)
TIMING ?= no
ifeq ($(TIMING),no)
  EXTRA_ARGS += --no-timing
else
  EXTRA_ARGS += --timing
endif

EXTRA_ARGS += -Wall

# Suppress specific warnings for Viterbi (filename vs module, BLKSEQ in functions)
VIT_SUPPRESS := -Wno-DECLFILENAME -Wno-BLKSEQ

# ---- Defaults (override on CLI) ----
VERILOG_SOURCES ?= ../rtl/convenc.v
TOPLEVEL        ?= convenc
MODULE          ?= test_convenc_smoke

# Optional: parameters
TB_LEN ?= 32
TB_SEQ ?= 5

# Pull in cocotb rules
include $(shell cocotb-config --makefiles)/Makefile.sim

# ============================  Convenience  ==============================

.PHONY: run waves clean_local clean_all \
        convenc viterbi_hard viterbi_seq chain ber_sweep

# Generic runner (uses current vars)
run:
	$(MAKE) -f $(shell cocotb-config --makefiles)/Makefile.sim \
		SIM=$(SIM) TOPLEVEL_LANG=$(TOPLEVEL_LANG) \
		TOPLEVEL=$(TOPLEVEL) MODULE=$(MODULE) \
		VERILOG_SOURCES="$(VERILOG_SOURCES)" \
		EXTRA_ARGS="$(EXTRA_ARGS)"

# Open latest waveform
waves:
	gtkwave $(firstword $(wildcard sim_build/*.fst sim_build/*.vcd))

# Avoid clashing with cocotb's built-in 'clean'
clean_local:
	rm -rf sim_build __pycache__ .pytest_cache results.xml

clean_all:
	$(MAKE) -f $(shell cocotb-config --makefiles)/Makefile.sim clean
	$(MAKE) clean_local

# ============================  Targets  ==================================

# Encoder smoke test
convenc:
	$(MAKE) run \
		TOPLEVEL=convenc \
		MODULE=test_convenc_smoke \
		VERILOG_SOURCES="../rtl/convenc.v"

# Viterbi: general hard-decision test
viterbi_hard:
	$(MAKE) run \
		TOPLEVEL=viterbi_decoder_7_5 \
		MODULE=test_viterbi_hard \
		VERILOG_SOURCES="../rtl/viterbi_hard.v" \
		EXTRA_ARGS="$(EXTRA_ARGS) $(VIT_SUPPRESS) -GTB_LEN=$(TB_LEN)"

# Viterbi: feeds 1101011001 sequence (short TB)
viterbi_seq:
	$(MAKE) run \
		TOPLEVEL=viterbi_decoder_7_5 \
		MODULE=test_viterbi_sequence \
		VERILOG_SOURCES="../rtl/viterbi_hard.v" \
		EXTRA_ARGS="$(EXTRA_ARGS) $(VIT_SUPPRESS) -GTB_LEN=$(TB_SEQ)"

# Chain: encoder -> decoder (uses your unified top)
chain:
	$(MAKE) run \
		TOPLEVEL=top_cv \
		MODULE=test_chain_conv_viterbi \
		VERILOG_SOURCES="../rtl/convenc.v ../rtl/viterbi_hard.v ../rtl/ber_tester.v ../rtl/top_cv.v" \
		EXTRA_ARGS="$(EXTRA_ARGS) $(VIT_SUPPRESS) -GTB_LEN=$(TB_LEN)" \
		TB_LEN=$(TB_LEN)

# BER sweep: RTL encoder -> Python bit-flip -> RTL decoder
ber_sweep:
	$(MAKE) run \
		TOPLEVEL=top_cv \
		MODULE=test_ber_sweep \
		VERILOG_SOURCES="../rtl/convenc.v ../rtl/viterbi_hard.v ../rtl/ber_tester.v ../rtl/top_cv.v" \
		EXTRA_ARGS="$(EXTRA_ARGS) $(VIT_SUPPRESS) -GTB_LEN=$(TB_LEN)"
