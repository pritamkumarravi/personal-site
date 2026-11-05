---
title: SimpleGrad
slug: simplegrad
tagline: Reverse-mode automatic differentiation from scratch — a tiny autograd engine, because backpropagation shouldn't be a library you import.
year: 2025
stack: [Python]
status: stable
priority: 3
featured: true
---

## overview

SimpleGrad is a small automatic differentiation engine with just enough
surface to train real neural networks: a scalar/node graph, a topological
backward pass, and a handful of operations. Small enough to read in one
sitting, complete enough that gradients come out correct against a
framework's.

## motivation

I used autograd for a long time before I understood it, and the gap bothered
me. Backpropagation is presented as either calculus homework or framework
incantation. The honest middle — a working engine in a few hundred lines —
is where the actual idea lives, so I built it.

## the problem being explored

What is the minimum machinery such that `loss.backward()` is not magic?

- A graph of operations that remembers how each value was produced.
- The chain rule, applied in reverse topological order.
- Accumulation at fan-out nodes — where most intuition quietly breaks.
- Enough ergonomics (an NN layer, an optimizer, a training loop) to prove
  the engine is real.

## approach

Every value is a node with parents and a local gradient rule. The forward
pass builds the graph; `backward()` seeds the output with 1.0 and walks the
topology in reverse, letting each node pull gradients from its consumers.
No global state, no hidden passes — the algorithm is the file.

## what i learned

- The chain rule is trivial; the *bookkeeping* is the engineering.
- Fan-out is where understanding is won or lost — accumulate, don't assign.
- Writing a fresh SGD loop on your own engine teaches more about optimizers
  than reading ten blog posts.
- Correctness is cheap to check: finite differences on random graphs catch
  almost every gradient bug.
- After this, reading a framework's autograd code became structural reading —
  I could see which parts were the idea and which were performance.
