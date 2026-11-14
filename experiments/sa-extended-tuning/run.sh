#!/usr/bin/env bash
# Post-hoc SA tuning (issue #32): extend the grid below the corner 0.2 / 0.9 found in experiments/tuning.
# Tuning seeds 1-10 only, weekly mode, budget 500, C# engine (bit-identical to Python).
# Run from the repository root:  bash experiments/sa-extended-tuning/run.sh
set -euo pipefail
OUT=experiments/sa-extended-tuning
CLI="dotnet run -c Release --project dotnet/src/Timetabling.Cli --"
for a in 0.001 0.01 0.05 0.1 0.2; do
  for c in 0.7 0.8 0.85 0.9; do
    id="sa-a$a-c$c"
    [ -f "$OUT/configs/$id/experiment.csv" ] && continue
    mkdir -p "$OUT/configs/$id"
    printf '{"sa": {"initial_acceptance": %s, "cooling_rate": %s}}\n' "$a" "$c" > "$OUT/configs/$id/parameters.json"
    $CLI batch run --methods sa --room-modes weekly --seeds 1-10 --budget 500 --slim \
      --parameters "$OUT/configs/$id/parameters.json" --name "$id" --output "$OUT/configs/$id" > /dev/null
  done
done
