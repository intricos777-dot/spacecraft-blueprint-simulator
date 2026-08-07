# Spacecraft Blueprint Simulator

Autonomous, self-looping design space explorer for a **direct-to-space atmospheric-capable spacecraft** targeting **0.5c** with a next-generation **plasma propulsion engine**.

This repo contains:
- `src/` — simulator engine and CLI
- `data/` — curated spacecraft/technology research corpus
- `blueprints/` — generated candidate designs
- `reports/` — convergence summaries
- `sim-runs/` — dated run logs

## Goals

1. Survey every relevant spacecraft from games/fiction/speculative engineering.
2. Build a realistic + theoretical middle-ground architecture.
3. Iterate automatically toward the best feasible blueprint.
4. Keep all designs private by default.

## Run

```bash
python3 src/simulator.py --runs 10 --output blueprints/
```

## Status

Scaffolding. Autonomous loop in progress.
