// rtl/ber_tester.v
`timescale 1ns/1ps
`default_nettype none

module ber_tester
#(
    parameter integer TB_LEN = 12
)(
    input  wire        clk,
    input  wire        rst,            // active-high

    // Reference stream (payload during ref_valid; zeros otherwise for tail)
    input  wire        ref_valid,
    input  wire        ref_bit,

    // Advance once per received symbol
    input  wire        advance,

    // Decoder output
    input  wire        dec_valid,
    input  wire        dec_bit,

    // How many payload bits to compare
    input  wire [15:0] total_bits,

    // Results
    output reg         done,
    output reg  [31:0] bits_compared,
    output reg  [31:0] bit_errors
);

    // Shift-register pipeline to align the reference bit stream with decoder latency.
    // Newest element enters bit 0; oldest (delayed ~TB_LEN steps) read at [TB_LEN-1].
    reg [TB_LEN-1:0] ref_pipe;
    wire             ref_in = ref_valid ? ref_bit : 1'b0;

    // Bookkeeping for initial pipeline fill (not strictly required for correctness here)
    reg [15:0] pushes;

    always @(posedge clk) begin
        if (rst) begin
            ref_pipe      <= {TB_LEN{1'b0}};
            pushes        <= 16'd0;
            bits_compared <= 32'd0;
            bit_errors    <= 32'd0;
            done          <= 1'b0;
        end else begin
            if (advance) begin
                ref_pipe <= {ref_pipe[TB_LEN-2:0], ref_in};
                if (pushes != 16'hFFFF)
                    pushes <= pushes + 16'd1;
            end

            if (dec_valid && !done) begin
                // Oldest value in the pipe approximates the TB_LEN alignment
                // (while pipe fills, this is zero; comparisons before fill are harmless
                // because ref_valid=0 -> ref_in=0 during tail).
                // If you want to strictly gate until pushes>=TB_LEN, you can add a guard.
                if (ref_pipe[TB_LEN-1] ^ dec_bit)
                    bit_errors <= bit_errors + 32'd1;

                bits_compared <= bits_compared + 32'd1;

                if (bits_compared + 32'd1 == {16'd0, total_bits})
                    done <= 1'b1;
            end
        end
    end

endmodule

`default_nettype wire
