---
title: SimpleVM
slug: simplevm
tagline: A small virtual machine — instruction dispatch, a memory model, and what actually sits between source and silicon.
year: 2025
stack: [C, Python]
repo: https://github.com/pritamkumarravi/simplevm
status: stable
priority: 4
featured: true
---

## overview

SimpleVM is a compact virtual machine: a fixed instruction set, a stack and
registers, a byte-addressable memory, and a fetch–decode–execute loop. It
runs programs compiled from a small assembly dialect. The scale is the point
— the whole machine fits in your head, which is precisely what real
runtimes refuse to do.

## motivation

Every language I use bottoms out in some VM or CPU model I'd never opened.
I wanted to close that gap from the simplest end: build the interpreter,
the memory model, and the instruction cycle myself, and see which
performance intuitions survive contact with the dispatch loop.

## the problem being explored

- What a machine actually is: state plus a transition function, nothing more.
- Why instruction dispatch is *the* hot loop, and what it costs.
- How a memory model — segments, bounds, alignment — shapes what programs can say.
- Where higher-level constructs (calls, closures, exceptions) would have to live.

## approach

The core is a `switch` over opcodes in a tight loop, with memory as a flat
byte array behind bounds-checked accessors. A small assembler (Python) turns
a readable ISA into bytecode, so writing test programs is quick. Each
instruction's semantics are documented next to its implementation — the ISA
reference and the source can't drift apart.

## what i learned

- The fetch–decode–execute loop is the whole story; everything else is ISA design.
- Bounds checks are where safety, simplicity and speed negotiate in the open.
- Writing assembly *for your own machine* reveals how much syntax is kindness.
- This project quietly reorganized how I read performance advice —
  branch prediction, cache lines and dispatch cost stopped being folklore.

## repository

Source and notes live on [GitHub](https://github.com/pritamkumarravi/simplevm).
