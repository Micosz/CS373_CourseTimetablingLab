#!/usr/bin/env bash
# Course-level Lab need, 1 to 15 Lab weeks per Lab course: same experiment as experiments/final on
# seeds 1001-1010, on the datasets from dataset_tools/make_course_lab_variants.py.
# Run from the repository root:  bash experiments/course-level-labs/run.sh
set -euo pipefail
for w in 01 02 04 06 08 10 12 15; do
  dotnet run -c Release --project dotnet/src/Timetabling.Cli -- batch run --dataset data/variants/fall-cs-course-labs-w$w.json.gz \
    --methods greedy hc sa ga --room-modes weekly fixed --seeds 1001-1010 --budget 500 --workers 4 \
    --parameters experiments/tuning/selected-parameters.json --name "Course-level Labs: $w Lab weeks" \
    --output experiments/course-level-labs/w$w
done
