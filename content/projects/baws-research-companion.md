---
title: BAWS Research Companion
slug: baws-research-companion
tagline: A tool built out of real workflow friction — keeping reading, notes and experiments in one place while doing research.
year: 2025
stack: [Python]
status: wip
priority: 5
featured: true
---

## overview

BAWS Research Companion is a working tool for managing a research workflow:
collecting sources, keeping notes connected to what produced them, and
tracking the small experiments that research actually consists of.

## motivation

This one started from annoyance, not curiosity. Research material fragments
across PDFs, browser tabs, notebooks and half-remembered terminal sessions —
and the connections *are* the research. I wanted a tool shaped around how I
actually work rather than how a product assumes I do, which meant building it.

## the problem being explored

- What the minimum structure of research state is — enough to be useful,
  not so much that maintaining it becomes a second job.
- How to keep provenance intact: which run, which source, which version.
- Where automation helps a workflow and where it silently adds friction.

## approach

Plain files over databases, so everything stays greppable, portable and
version-controlled. Small commands over a monolithic app, so the tool fits
into a terminal workflow instead of replacing it. It is deliberately
unfinished in places — it grows when the workflow does.

## what i learned

- Tool-building is systems design under the constraint "one user, me" —
  every abstraction must pay rent immediately.
- The best data model is the one you'll actually maintain at 1 a.m.
- Building for yourself first surfaces requirements no specification
  would have mentioned.
