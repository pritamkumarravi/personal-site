---
title: About
template: about.html
url: /about/
description: About Pritam Ravi — technical interests, current focus, and a first-principles approach to learning and building.
---

hey, I'm pritam.

I care about the machinery underneath modern ML — the serving stacks, schedulers,
kernels and memory systems between a model and a request. Frameworks are easy to
use and hard to see into; most of what I do is an attempt to see into them.

## technical interests

- **Inference engineering** — serving systems, scheduling, KV-cache management,
  continuous batching.
- **ML systems** — how models, runtimes and hardware interact, and why the fast
  path is fast.
- **GPU performance** — memory hierarchies, kernel behaviour, and the arithmetic
  of making hardware do what the roofline says it can.
- **Post-training for creative domains** — teaching models to be interesting,
  not just correct.

## current focus

Right now I'm working through LLM inference and serving systems: reading
implementations, running my own, and rebuilding simplified versions to test
whether I actually understand a component or just recognize it. The experiments
are collected on the [projects page](/projects/).

## how i think

First principles over familiarity: break a system into its fundamental
components and reason up from there, rather than memorizing how a tool wants
to be used. When something feels like a black box, I build a small version —
an autograd engine, a minimal serving loop, a tiny VM — until the design
choices become obvious. Then I experiment until behaviour is explained,
not just observed.
