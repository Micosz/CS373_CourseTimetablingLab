# Verification record

Checked 2026-10-27. These are implementation checks, not final comparative research results.

- 12 automated Python tests pass on the actual adapted Fall CS input and small code fixtures.
- Four built-in methods pass the independent solution validator; evaluation accounting and lexicographic best-so-far traces checked.
- Repeated native runs with the same seed produce identical solutions/metrics when no time cap intervenes.
- Validator tests cover room, teacher, student conflicts; capacity; room type; availability; duplicate session-week; partial schedules; committed-background overlap; half-open intervals; SAME_TIME; repeated source constraint ID groups.
- Actual Safari browser runs with Pyodide 314.0.7: four methods × seed 42, budget 12. All four returned hard violations = 0 and budget accounting was correct (Greedy used 1; search methods used 12).
- Browser history survives page reload and reopens completed run data.
- Downloaded JSON contains four raw runs, the exact input dataset with matching SHA-256, and the five Python source files actually used by the worker. Downloaded CSV contains four result rows.
- Browser JSON import reopens all four runs and explicitly labels them as imported, without rerunning.
- Browser custom Python template executes with the shared budget (5 evaluations) and passes final audit.
- Dataset converter rebuild matches the exact pinned adapted dataset SHA-256.
- Native CLI smoke: four methods × seed 42, budget 4; JSON and CSV written successfully.

## Fixed-room mode (issue #3), checked 2026-11-04

- 18 automated Python tests pass (adds known-answer fixed vs weekly fixture: 0 vs 180 unnecessary Lab minutes; fixed mode leaves a blocked week unassigned instead of moving room; validator rejects `FIXED_ROOM_CHANGED`, `FIXED_ROOM_NOT_LAB`, `ROOM_MODE` mismatch; all four methods in fixed mode on the real dataset pass audit with 0 room changes; paired summary script).
- Weekly mode is unchanged: Greedy on the real dataset still gives 20 unassigned / 124 Lab hours / 838 room changes.
- Native CLI `--room-modes weekly fixed` runs and writes `room_mode` per run in JSON and CSV.
- Headless Chromium (local HTTP server): the room-mode selector renders on desktop and stacks at 390 px with no horizontal scroll; importing a CLI batch that contains both modes shows separate summary rows, run labels, and chart legend entries per mode with no page errors. Pyodide could not be downloaded in that environment, so a fixed-mode search was not executed inside the browser worker; the worker passes the same `config.room_mode` that the native runner tests cover.

## Schedule viewer (issue #9), checked 2026-11-04

- Chromium via a local HTTP server, no Python search executed: imported all four `experiments/fixed-room` bundles through the real import input (two as `.json.gz`, two as `.json`), 240 runs (120 weekly, 120 fixed).
- For every one of the 240 runs, the rendered heatmap's unnecessary total (sum of the cells' minutes) equals `metrics.unnecessary_lab_minutes`, and minutes/60 equals `unnecessary_lab_hours` (weekly 83–202 h, fixed 1,859–2,028 h). The page shows the ✓ match.
- For every run, rendering each of the 174 classes and counting the highlighted room-change weeks sums to `metrics.room_changes` (weekly 806–906, fixed 0).
- Reopening an imported batch from the history page shows all three views. Both schedule CSVs start with the UTF-8 BOM (EF BB BF) and contain Thai day/status text; by room = 3,325 rows for a run with 20 unassigned, by class = 3,345 rows (all weekly sessions). Not opened in Excel itself.
- Tabs work with arrow keys, Home and End; Tab reaches the class search and the class select. At 1280×720 the 15-week heatmap fits without scrolling. At 390 px wide the page does not scroll sideways (the heatmap scrolls inside its own box, with the room column fixed in place). No console errors.
- `python -m unittest discover -s engine/tests`: 18 tests pass.

Automated CI reruns the Python contract/regression suite. This record does not claim every browser/version or all custom Python programs have been tested. Imported bundles are not re-executed or independently authenticated merely by importing them.
