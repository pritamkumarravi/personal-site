---
title: Anatomy of a decode step
date: 2026-10-21
category: gpu
tags: [gpu, inference, performance]
summary: One token out, an entire system in. Tracing a single autoregressive decode step from the scheduler's queue to a sampled logit — and finding out where the time actually goes.
---

From the outside, inference looks like a sentence appearing on a screen. From
the inside, each token is a full trip through a scheduler, a batched kernel
launch sequence, a memory hierarchy, and a sampling procedure — in a few
milliseconds, over and over. This note traces one decode step end to end,
because you can't reason about performance until you know what a single
step contains.

## the shape of the loop

```
        ┌─────────────────────────────────────────────┐
        │  scheduler: pick the batch for this step    │
        └──────────────────────┬──────────────────────┘
                               ▼
        ┌─────────────────────────────────────────────┐
        │  gather last-token embeddings + KV pages    │
        └──────────────────────┬──────────────────────┘
                               ▼
        ┌─────────────────────────────────────────────┐
        │  transformer layers: attention + MLP        │
        │    (weights streamed from HBM each step)    │
        └──────────────────────┬──────────────────────┘
                               ▼
        ┌─────────────────────────────────────────────┐
        │  append new K/V → sample → detokenize       │
        └─────────────────────────────────────────────┘
```

The defining constraint: **one token per sequence per step**. Every request
in the batch advances together, so the step's cost is shared — which is why
batching is the first, biggest throughput lever.

## where the time goes

For small batch sizes, decode is memory-bound. The arithmetic per weight is
tiny — one activation row per matrix — but *every weight must be read from
HBM every step*. Roughly:

```python
# decode is memory-bound: every weight is streamed once per step
step_time = weight_bytes / memory_bandwidth
```

That ratio is why a model that "fits" in memory can still crawl, and why
quantization helps latency at low batch even when nobody is compute-starved.
It also explains continuous batching: if the step is bounded by streaming
weights anyway, adding sequences to the batch reads the same weights once
and amortizes them across more requests — nearly free tokens.

## the pieces that decide latency

- **Scheduling**: which requests ride in this step. Admitting a long-prompt
  request mid-stream forces a prefill that stalls everyone's next token.
- **KV gather**: assembling scattered cache pages into kernel-friendly
  layout. The allocator's page table shows up here as real clock time.
- **Kernel launches**: dozens of small launches per step; overhead that is
  invisible in prefill and brutal in a 5 ms step. CUDA graphs exist because
  of this loop.
- **Sampling and detokenization**: trivial FLOPs, but a synchronization
  point — the GPU waits for the CPU to decide what the next input token is.

## what to do with this

Once the step is visible, optimization questions become concrete. Is this
kernel bandwidth-bound or launch-bound? Is the batch read-bound on weights
or on cache? Is the scheduler admitting prefills at moments that wreck the
step time? None of these are answerable from the outside — which is the
running argument of this site: build the small version, then read the big one.

The natural continuation is the [KV cache note](/writing/the-kv-cache-is-an-allocator/)
and the [Mini-SGLang notes](/projects/mini-sglang/), where the loop above
exists in runnable miniature.
