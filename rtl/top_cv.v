// rtl/top_cv.v
`timescale 1ns/1ps
`default_nettype none

module top_cv #(
    parameter integer TB_LEN  = 12,   // decoder traceback depth
    parameter integer PAY_LEN = 10    // payload bits (compared for BER)
)(
    input  wire clk,

    // Encoder side
    input  wire enc_rst_n,      // active-low for encoder
    input  wire enc_in_valid,
    input  wire enc_bit_in,
    output wire enc_out_valid,
    output wire enc_y0,         // treat as v1 in Python test
    output wire enc_y1,         // treat as v0 in Python test

    // Decoder side
    input  wire       dec_rst,        // active-high reset for decoder & BER block
    input  wire       dec_sym_valid,
    input  wire [1:0] dec_rx_sym,     // {v1,v0}
    output wire       dec_bit_valid,
    output wire       dec_bit_out,

    // BER outputs (readable from cocotb)
    output wire        ber_done,
    output wire [31:0] ber_bits,
    output wire [31:0] ber_errs
);

    // --- Encoder DUT ---
    // Adjust port names here ONLY if your convenc.v differs.
    // Expected:
    // module convenc(
    //   input clk, input rst_n, input in_valid, input bit_in,
    //   output out_valid, output y0, output y1);
    convenc u_enc (
        .clk       (clk),
        .rst_n     (enc_rst_n),
        .in_valid  (enc_in_valid),
        .bit_in    (enc_bit_in),
        .out_valid (enc_out_valid),
        .y0        (enc_y0),
        .y1        (enc_y1)
    );

    // --- Decoder DUT ---
    // Expected:
    // module viterbi_decoder_7_5 #(parameter TB_LEN=32)(
    //   input clk, input rst,
    //   input sym_valid, input [1:0] rx_sym,
    //   output bit_valid, output bit_out);
    viterbi_decoder_7_5 #(
        .TB_LEN(TB_LEN)
    ) u_dec (
        .clk       (clk),
        .rst       (dec_rst),
        .sym_valid (dec_sym_valid),
        .rx_sym    (dec_rx_sym),
        .bit_valid (dec_bit_valid),
        .bit_out   (dec_bit_out)
    );

    // ------------------------------
    // Payload tagging for BER compare
    // ------------------------------
    // Count how many ENC payload bits have been presented;
    // we only compare the first PAY_LEN bits against decoder output.
    reg  [31:0] enc_payload_cnt;
    wire        ref_valid = enc_in_valid && (enc_payload_cnt < PAY_LEN);
    wire        ref_bit   = enc_bit_in;

    always @(posedge clk or negedge enc_rst_n) begin
        if (!enc_rst_n) begin
            enc_payload_cnt <= 32'd0;
        end else if (enc_in_valid) begin
            if (enc_payload_cnt < PAY_LEN)
                enc_payload_cnt <= enc_payload_cnt + 32'd1;
        end
    end

    // Narrow PAY_LEN to 16 bits for the tester input
    wire [15:0] PAY_LEN_16 = PAY_LEN[15:0];

    // ------------------------------
    // BER tester instance
    // ------------------------------
    ber_tester #(
        .TB_LEN(TB_LEN)
    ) u_ber (
        .clk           (clk),
        .rst           (dec_rst),         // reset along with decoder
        .ref_valid     (ref_valid),
        .ref_bit       (ref_bit),
        .advance       (dec_sym_valid),   // step once per symbol consumed
        .dec_valid     (dec_bit_valid),
        .dec_bit       (dec_bit_out),
        .total_bits    (PAY_LEN_16),
        .done          (ber_done),
        .bits_compared (ber_bits),
        .bit_errors    (ber_errs)
    );

endmodule

`default_nettype wire
