---
title: The KV cache is an allocator wearing an ML costume
date: 2026-09-14
category: systems
tags: [inference, kv-cache, memory]
summary: Autoregressive inference spends most of its intelligence not on matrix multiplication but on remembering. A first-principles look at why the KV cache behaves like a memory allocator — and why that framing explains almost everything about serving performance.
---

Every conversation with a language model is a memory problem in disguise.
During autoregressive decoding, the model must attend to every token that
came before — and attention needs each earlier token's keys and values,
stored and ready. That store is the KV cache, and once you look at it as
*an allocator with unusual customers*, most of LLM serving design stops
being mysterious.

## what the cache actually holds

For every generated sequence, per layer, per attention head, the cache
stores two tensors: the keys and the values computed for every token so far.
The arithmetic is unforgiving:

```python
bytes_per_token = (
    2                    # K and V
    * n_layers
    * n_kv_heads         # fewer than attention heads under GQA
    * head_dim
    * bytes_per_element
)
cache_bytes = bytes_per_token * sequence_length
```

Multiply it out for a long-context model and the cache dwarfs the weights.
This is the first reframing: the "model" is a fixed cost, but the KV cache
grows *with every request and every token* — it behaves like heap memory
under load.

## decoding is a bandwidth problem

A prefill pass (ingesting the prompt) is compute-bound: it processes
thousands of tokens in parallel and keeps the tensor cores busy. Decode is
the opposite. Each step generates **one** token, which means one row of
arithmetic per weight matrix — and a full read of every cached key and value.

The GPU spends that step mostly waiting on memory. Throughput is bounded
not by FLOPs but by how fast you can stream the cache from HBM. Which
raises the question every serving system must answer:

> with the GPU bottlenecked on reads, how do I avoid reading the same
> bytes once per request?

## the allocator's problems

Framed as an allocator, the KV cache has to solve the classics:

| Allocator problem | Serving equivalent |
|---|---|
| Variable allocation sizes | Sequences of unknown final length |
| Fragmentation | Pre-reserved contiguous buffers per sequence |
| Compaction cost | Moving a live cache mid-generation |
| Sharing | Prefixes, few-shot prompts, system prompts |
| Reclamation | Finished (or aborted) requests |

Pre-allocating `max_seq_len` per request is the naive policy — and it
fragments exactly like early malloc implementations did. The insight behind
paged KV caches is to do what operating systems did decades ago: split the
cache into fixed-size blocks, keep a per-sequence page table, and accept a
small indirection cost in exchange for near-zero external fragmentation.

## sharing is the multiplier

The second big lever falls out of the same framing. If many requests begin
with the same prefix — a system prompt, a few-shot block — their first *n*
pages are byte-identical. Copy-on-write semantics let them share physical
pages until one request generates a token that diverges.

This is why prefix caching can change serving economics entirely: the
shared portion is computed once, read once per decode step by every
subscriber, and stored once. The allocator grew reference counting.

## what I took away

- Memory policy is the serving system. Scheduling decides *who* runs; the
  cache decides *whether anyone else can*.
- Every classic allocator idea — paging, coalescing, reference counting,
  copy-on-write — has already been re-invented inside inference engines.
  Reading OS literature is directly transferable.
- The path to understanding this was rebuilding a minimal version — the
  [project page](/projects/mini-sglang/) has the notes. The mechanism is
  small; the design space around it is not.

The abstractions hold until you multiply out the cache size for a real
model at a real context length. Then they don't, and the systems work begins.
