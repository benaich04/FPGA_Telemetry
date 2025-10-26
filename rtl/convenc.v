`timescale 1ns/1ps
`default_nettype none

// Rate-1/2 convolutional encoder, K=3 (constraint length)
// Generators default to (7,5) in octal -> 3'b111 and 3'b101 in binary.
module convenc #(
  parameter [2:0] G0 = 3'b111, // (7)_oct
  parameter [2:0] G1 = 3'b101  // (5)_oct
)(
  input  wire clk,
  input  wire rst_n,
  input  wire in_valid,
  input  wire bit_in,        // serial input bit
  output reg  out_valid,
  output reg  y0,            // coded bit 0
  output reg  y1             // coded bit 1
);
  // 2 memory bits for K=3 (m = K-1 = 2)
  reg d1, d0;

  wire [2:0] regvec = {bit_in, d1, d0}; //registor vector that has the bits to encode
  wire y0_next = ^(regvec & G0); // encode : take regvec, mask taps with G0 using AND, then XOR all remaining 1-bits to get the encoded bit. 
  wire y1_next = ^(regvec & G1);

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin //reset when rst_n is 0
      d1 <= 1'b0;
      d0 <= 1'b0;
      y0 <= 1'b0;
      y1 <= 1'b0;
      out_valid <= 1'b0;
    end else begin //if not reset mode
      out_valid <= in_valid;   // pass-through: mark outputs (y0,y1) valid on the same cycle as input bit
      if (in_valid) begin
        y0 <= y0_next;
        y1 <= y1_next;
        // shift register update
        d0 <= d1;
        d1 <= bit_in;
      end
    end
  end
endmodule
