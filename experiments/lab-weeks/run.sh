#!/usr/bin/env bash
# Lab weeks per Lab course, 1 to 15: same experiment as experiments/final on seeds 1001-1010,
# on the datasets from dataset_tools/make_lab_week_variants.py (level 04 has the Lab weeks of the main dataset).
# Run from the repository root:  bash experiments/lab-weeks/run.sh
set -euo pipefail
for w in 01 02 04 06 08 10 12 15; do
  dotnet run -c Release --no-build --project dotnet/src/Timetabling.Cli -- batch run --dataset data/variants/fall-cs-labweeks-w$w.json.gz \
    --methods greedy hc sa ga --room-modes weekly fixed --seeds 1001-1010 --budget 500 --workers 20 \
    --parameters experiments/tuning/selected-parameters.json --name "Lab weeks per Lab course: $w" \
    --output experiments/lab-weeks/w$w
done
