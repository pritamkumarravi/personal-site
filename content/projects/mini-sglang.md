---
title: Mini-SGLang
slug: mini-sglang
tagline: A minimal reimplementation of an LLM serving system's core paths — built to understand what a production inference stack actually does between a request and a token.
year: 2026
stack: [Python, PyTorch, CUDA]
status: active
priority: 2
featured: true
---

## overview

Mini-SGLang is a stripped-down LLM serving system: not a fork, not a wrapper —
a from-scratch walk through the critical path that every inference engine
shares. The point was never to replace the real thing. The point was that
after writing the loop myself, reading production code stops being archaeology.

## motivation

Serving frameworks are easy to *use* and hard to *see into*. Requests go in,
tokens come out, and somewhere in between a scheduler is making decisions that
explain most of your throughput. I didn't want to treat that region as a black
box, so I rebuilt its skeleton: the smallest system that still has to make the
real decisions.

## the problem being explored

What does an inference engine actually spend its time deciding?

- When a request joins the running batch, and when it waits.
- How the KV cache is allocated, paged, and evicted.
- What happens at the boundary of a decode step — where the GPU is
  busy, where it idles, and why.
- How continuous batching turns a queue of requests into a stream of
  nearly-full forward passes.

## approach

The implementation follows one request end to end before generalizing:
tokenize → admit → batch → decode → detokenize → stream. Each stage is a
module with a boundary I can test in isolation, which is exactly what the
big systems make hard. Scheduling and cache policy are separated so one can
be swapped without touching the other.

## what i learned

- The scheduler is the product. Everything else is tensor arithmetic.
- KV-cache management is a systems problem wearing an ML costume —
  it has more in common with an allocator than with a model.
- Batching decisions dominate latency distribution shape; the mean
  hides almost everything interesting.
- Reading the real implementation afterwards felt completely different:
  the unfamiliar parts had shrunk to genuinely novel details.
