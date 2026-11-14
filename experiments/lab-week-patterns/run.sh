#!/usr/bin/env bash
# Lab-week pattern sensitivity (issue #30): same experiment as experiments/final on seeds 1001-1010,
# on datasets whose Lab weeks are consecutive or every other week (dataset_tools/make_pattern_variants.py).
# Run from the repository root:  bash experiments/lab-week-patterns/run.sh
set -euo pipefail
for p in consecutive alternate; do
  dotnet run -c Release --project dotnet/src/Timetabling.Cli -- batch run --dataset data/variants/fall-cs-pattern-$p.json.gz \
    --methods greedy hc sa ga --room-modes weekly fixed --seeds 1001-1010 --budget 500 --workers 4 \
    --parameters experiments/tuning/selected-parameters.json --name "Lab weeks: $p (issue #30)" \
    --output experiments/lab-week-patterns/$p
done
