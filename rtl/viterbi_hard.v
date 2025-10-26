// -----------------------------------------------------------------------------
// Viterbi Decoder (Verilog-2001, Verilator-friendly)
// Rate 1/2, K=3, generators (7,5)_oct -> g1=111b, g2=101b
// Hard-decision input: 2 bits per symbol (rx_sym[1:0])
// Streaming output with latency TB_LEN: decoded_bit valid after TB_LEN steps
// -----------------------------------------------------------------------------
// NOTE: File is viterbi_hard.v but module is viterbi_decoder_7_5.
//       We silence Verilator's DECLFILENAME warning below.
// -----------------------------------------------------------------------------

`timescale 1ns/1ps
// verilator lint_off DECLFILENAME 

module viterbi_decoder_7_5
#(
    parameter TB_LEN = 32  // Traceback/register-exchange length (>=2 recommended)
)
(
    input              clk,
    input              rst,          // synchronous reset (active high)

    // One symbol (2 bits) per valid cycle:
    input              sym_valid,    // assert 1 when rx_sym is valid this cycle
    input      [1:0]   rx_sym,       // {v1,v0} hard bits

    // Decoded bit stream (delayed by TB_LEN symbols)
    output reg         bit_valid,    // goes high after TB_LEN accepted symbols
    output reg         bit_out       // estimated original data bit
);

    // -----------------------------
    // Trellis for K=3 -> 2^(K-1)=4 states
    // State encoding: s = {s1,s0} = {u[k-2], u[k-1]}
    // Next state q = {q1,q0} = {u[k], s0}
    // For a given next_state q, predecessors are:
    //   p0 = {0, q0}, with input u = q1
    //   p1 = {1, q0}, with input u = q1
    // -----------------------------
    integer i;

    // Path metrics (16-bit, saturating)
    reg [15:0] pm_cur   [0:3];

    // Survivor paths via register-exchange:
    // Each state keeps a shift register of the last TB_LEN decoded bits
    reg [TB_LEN-1:0] path_reg_cur [0:3];

    // Local "next" values computed each valid symbol (combinational for this cycle)
    reg [15:0]       pm_calc   [0:3];
    reg [TB_LEN-1:0] path_calc [0:3];

    // Count how many symbols we've accepted (for bit_valid gating)
    reg [31:0] sym_count;

    // -----------------------------
    // Hamming distance for 2-bit symbols
    // -----------------------------
    // verilator lint_off BLKSEQ 
    function [1:0] hamming2;
        input [1:0] a;
        input [1:0] b;
        reg   [1:0] x;
        begin
            x = a ^ b;
            hamming2 = x[0] + x[1];
        end
    endfunction

    // -----------------------------
    // Encoder output for (7,5)_oct given predecessor state s={s1,s0} and input u
    // v1 = u ^ s0 ^ s1   (g1 = 111b)
    // v0 = u ^ s1        (g2 = 101b)
    // Return as {v1,v0}
    // -----------------------------
    function [1:0] enc_out_7_5;
        input [1:0] s;  // {s1,s0}
        input       u;
        reg   v1, v0, s1, s0;
        begin
            s1 = s[1];
            s0 = s[0];
            v1 = u ^ s0 ^ s1;
            v0 = u ^ s1;
            enc_out_7_5 = {v1, v0};
        end
    endfunction

    // -----------------------------
    // Saturating add (16-bit)
    // -----------------------------
    function [15:0] sat_add16;
        input [15:0] a;
        input [15:0] b;
        reg   [16:0] sum;
        begin
            sum = a + b;
            if (sum[16] == 1'b1) sat_add16 = 16'hFFFF;
            else                 sat_add16 = sum[15:0];
        end
    endfunction

    // -----------------------------
    // Find best (minimum) metric state index among 4 states
    // -----------------------------
    function [1:0] argmin4;
        input [15:0] m0, m1, m2, m3;
        reg   [15:0] best;
        reg   [1:0]  idx;
        begin
            best = m0; idx = 2'd0;
            if (m1 < best) begin best = m1; idx = 2'd1; end
            if (m2 < best) begin best = m2; idx = 2'd2; end
            if (m3 < best) begin best = m3; idx = 2'd3; end
            argmin4 = idx;
        end
    endfunction
    // verilator lint_on BLKSEQ 

    // -----------------------------
    // Reset / Initialize
    // Start in state 00 with metric 0; others large.
    // Path registers cleared.
    // -----------------------------
    always @(posedge clk) begin
        if (rst) begin
            pm_cur[0] <= 16'd0;
            pm_cur[1] <= 16'h3FFF;
            pm_cur[2] <= 16'h3FFF;
            pm_cur[3] <= 16'h3FFF;

            for (i=0;i<4;i=i+1) begin
                path_reg_cur[i] <= {TB_LEN{1'b0}};
                pm_calc[i]      = 16'd0;
                path_calc[i]    = {TB_LEN{1'b0}};
            end

            sym_count <= 32'd0;
            bit_valid <= 1'b0;
            bit_out   <= 1'b0;

        end else begin
            // Default hold
            for (i=0;i<4;i=i+1) begin
                pm_cur[i]        <= pm_cur[i];
                path_reg_cur[i]  <= path_reg_cur[i];
            end
            bit_valid <= (sym_count >= TB_LEN) ? 1'b1 : 1'b0;
            bit_out   <= bit_out;

            if (sym_valid) begin
                // Compute pm_calc/path_calc for each next_state q using BLOCKING '='
                // q = {q1,q0}, predecessors p0={0,q0}, p1={1,q0}, input u=q1

                // q = 2'b00
                begin : NEXT_00
                    reg [1:0] q, p0, p1;
                    reg       u;
                    reg [1:0] e0, e1;
                    reg [1:0] d0, d1;
                    reg [15:0] m0, m1;
                    q  = 2'b00; u  = q[0];
                    p0 = {1'b0, q[1]}; p1 = {1'b1, q[1]};
                    e0 = enc_out_7_5(p0, u); e1 = enc_out_7_5(p1, u);
                    d0 = hamming2(rx_sym, e0); d1 = hamming2(rx_sym, e1);
                    m0 = sat_add16(pm_cur[p0], {14'd0, d0});
                    m1 = sat_add16(pm_cur[p1], {14'd0, d1});
                    if (m0 <= m1) begin
                        pm_calc[q]   = m0;
                        path_calc[q] = {path_reg_cur[p0][TB_LEN-2:0], u};
                    end else begin
                        pm_calc[q]   = m1;
                        path_calc[q] = {path_reg_cur[p1][TB_LEN-2:0], u};
                    end
                end

                // q = 2'b01
                begin : NEXT_01
                    reg [1:0] q, p0, p1;
                    reg       u;
                    reg [1:0] e0, e1;
                    reg [1:0] d0, d1;
                    reg [15:0] m0, m1;
                    q  = 2'b01; u  = q[0];
                    p0 = {1'b0, q[1]}; p1 = {1'b1, q[1]};
                    e0 = enc_out_7_5(p0, u); e1 = enc_out_7_5(p1, u);
                    d0 = hamming2(rx_sym, e0); d1 = hamming2(rx_sym, e1);
                    m0 = sat_add16(pm_cur[p0], {14'd0, d0});
                    m1 = sat_add16(pm_cur[p1], {14'd0, d1});
                    if (m0 <= m1) begin
                        pm_calc[q]   = m0;
                        path_calc[q] = {path_reg_cur[p0][TB_LEN-2:0], u};
                    end else begin
                        pm_calc[q]   = m1;
                        path_calc[q] = {path_reg_cur[p1][TB_LEN-2:0], u};
                    end
                end

                // q = 2'b10
                begin : NEXT_10
                    reg [1:0] q, p0, p1;
                    reg       u;
                    reg [1:0] e0, e1;
                    reg [1:0] d0, d1;
                    reg [15:0] m0, m1;
                    q  = 2'b10; u  = q[0];
                    p0 = {1'b0, q[1]}; p1 = {1'b1, q[1]};
                    e0 = enc_out_7_5(p0, u); e1 = enc_out_7_5(p1, u);
                    d0 = hamming2(rx_sym, e0); d1 = hamming2(rx_sym, e1);
                    m0 = sat_add16(pm_cur[p0], {14'd0, d0});
                    m1 = sat_add16(pm_cur[p1], {14'd0, d1});
                    if (m0 <= m1) begin
                        pm_calc[q]   = m0;
                        path_calc[q] = {path_reg_cur[p0][TB_LEN-2:0], u};
                    end else begin
                        pm_calc[q]   = m1;
                        path_calc[q] = {path_reg_cur[p1][TB_LEN-2:0], u};
                    end
                end

                // q = 2'b11
                begin : NEXT_11
                    reg [1:0] q, p0, p1;
                    reg       u;
                    reg [1:0] e0, e1;
                    reg [1:0] d0, d1;
                    reg [15:0] m0, m1;
                    q  = 2'b11; u  = q[0];
                    p0 = {1'b0, q[1]}; p1 = {1'b1, q[1]};
                    e0 = enc_out_7_5(p0, u); e1 = enc_out_7_5(p1, u);
                    d0 = hamming2(rx_sym, e0); d1 = hamming2(rx_sym, e1);
                    m0 = sat_add16(pm_cur[p0], {14'd0, d0});
                    m1 = sat_add16(pm_cur[p1], {14'd0, d1});
                    if (m0 <= m1) begin
                        pm_calc[q]   = m0;
                        path_calc[q] = {path_reg_cur[p0][TB_LEN-2:0], u};
                    end else begin
                        pm_calc[q]   = m1;
                        path_calc[q] = {path_reg_cur[p1][TB_LEN-2:0], u};
                    end
                end

                // Commit "next" to registered state (NON-BLOCKING)
                for (i=0;i<4;i=i+1) begin
                    pm_cur[i]       <= pm_calc[i];
                    path_reg_cur[i] <= path_calc[i];
                end

                // Advance counter and produce output from CURRENT-CYCLE results
                sym_count <= sym_count + 32'd1;
                begin : OUTPUT_STAGE
                    reg [1:0] best_idx;
                    best_idx = argmin4(pm_calc[0], pm_calc[1], pm_calc[2], pm_calc[3]);
                    bit_valid <= (sym_count + 32'd1 >= TB_LEN) ? 1'b1 : 1'b0;
                    bit_out   <= path_calc[best_idx][TB_LEN-1];  // oldest bit (MSB)
                end
            end
        end
    end

endmodule
