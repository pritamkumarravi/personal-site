---
title: WAN2.1 Bench
slug: wan21-bench
tagline: Benchmark tooling for video generation models — where GPU performance engineering meets creative output, and every measurement is a multi-second render.
year: 2026
stack: [Python, PyTorch, CUDA]
repo: https://github.com/pritamkumarravi/wan2.1-bench
status: active
priority: 1
featured: true
---

## overview

WAN2.1 Bench is a harness for measuring video generation performance
consistently: fixed prompts and seeds, controlled resolution and step counts,
repeat runs, and clean reporting of the numbers that actually move —
latency per step, end-to-end time, and memory ceiling.

## motivation

Video generation is the most demanding inference workload I know: long
sequences, heavy attention, transformer weights, and outputs you can't
unit-test. Most numbers quoted about these models come from different
settings and aren't comparable. I wanted a harness that makes my own
comparisons honest before I start optimizing anything.

## the problem being explored

- What "performance" even means for a diffusion transformer — steps,
  resolution, batching and CFG all move the target.
- Where time actually goes: attention versus MLPs versus
  the machinery around the model.
- How memory pressure behaves as resolution and sequence length grow,
  and what that does to feasibility on consumer hardware.

## approach

The harness fixes everything that isn't the variable under test: pinned
prompts, fixed seeds, warmup passes excluded, medians over repeats. Results
are written alongside their exact configuration so a number is never
separated from its provenance. It's benchmark tooling in the plain sense —
boring by design, so the interesting numbers are trustworthy.

## what i learned

- Measurement discipline matters more here than anywhere else —
  video workloads are slow enough that sloppy methodology costs hours.
- Diffusion "steps" hide a rich inner structure; the step loop is a
  systems problem of its own.
- Memory, not FLOPs, is usually the wall on consumer GPUs.
- Creative quality and systems performance are the same project:
  the fastest pipeline is useless if the output isn't worth watching.
