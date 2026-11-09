# แผนที่ repository

เริ่มอ่านตามสิ่งที่ต้องการ:

| อยากทำอะไร | เริ่มที่ |
|---|---|
| ใช้เว็บครั้งแรก | [quick-start.md](quick-start.md) |
| ภาพรวมโครงงาน และวิธีรันบนเครื่อง | [../README.md](../README.md) |
| รายละเอียดเชิงเทคนิค (วิธีแทนคำตอบ ข้อห้าม ความเท่าเทียม โค้ด Python) | [technical.md](technical.md) |
| ดูผลทดลองทั้งหมด | [../experiments/INDEX.md](../experiments/INDEX.md) |
| กติกาการทดลอง (seed, งบ, สถิติ) | [protocol.md](protocol.md) |
| ทำไมออกแบบแบบนี้ เทียบกับงานวิจัย | [research-comparison.md](research-comparison.md) |
| ดูสไลด์นำเสนอ | [../apps/slides/](../apps/slides/README.md) |
| ข้อมูลนำเข้าและสมมติฐาน | [../data/START_HERE.txt](../data/START_HERE.txt) |

## โฟลเดอร์

| Path | มีอะไร |
|---|---|
| [`apps/web/`](../apps/web/) | เว็บห้องทดลอง: `index.html` (หน้า UI), `app.mjs` (UI, plots, export, history), `worker.mjs` (Pyodide loader และ Python bridge), `storage.mjs` (IndexedDB), `styles.css` |
| [`apps/slides/`](../apps/slides/README.md) | สไลด์ Final (`index.html`, `deck.js`, `slides.json`, `speaker-notes.md`), `progress/` คือสไลด์ความคืบหน้า 4 พ.ย. และ [DEPLOY.md](../apps/slides/DEPLOY.md) คือวิธีตั้งค่า Vercel |
| [`apps/godot/`](../apps/godot/README.md) | แอปเดสก์ท็อป Godot 4.7 (C#): แผนที่ห้องรายสัปดาห์, รันการค้นหาสด, เทียบ weekly/fixed ใช้ engine C# ตัวเดียวกับ CLI |
| [`engine/`](../engine/) | Python engine ต้นฉบับอ้างอิง ใช้ทั้งเว็บและ CLI (ดูตารางด้านล่าง) |
| [`engine/tests/`](../engine/tests/) | contract/regression tests (`python -m unittest discover -s engine/tests`) |
| [`dotnet/`](../dotnet/README.md) | engine เดียวกันใน C# ให้ผลตรงกับ Python ทุกบิต, CLI `timetabling` (run / batch) และ parity tests |
| [`data/`](../data/) | `fall-cs.json.gz` (ชุดข้อมูลหลัก), `provenance.json` (SHA-256), `assumptions.json`, `conversion_audit.json`, `FORMAT.txt`, `variants/` (ชุดข้อมูลที่มี Lab 3 และ 2 ห้อง) |
| [`dataset_tools/`](../dataset_tools/) | converter และ config ที่ใช้สร้าง `data/` ซ้ำ รวมถึง `make_lab_variants.py` |
| [`experiments/`](../experiments/INDEX.md) | ผลดิบและสรุปของทุกการทดลอง |
| [`docs/`](.) | เอกสารในหน้านี้, `QA.md` (บันทึกการตรวจ), `img/` (ภาพประกอบคู่มือ และ `img/redesign/` ภาพก่อน/หลังปรับหน้าตา) |
| `index.html` (root) | redirect ไป `apps/web/` เพื่อให้ URL ของ GitHub Pages เดิมใช้ได้ |

## ไฟล์ใน `engine/`

| ไฟล์ | หน้าที่ |
|---|---|
| `lab_core.py` | โมเดลปัญหา decoder และ context การค้นหา |
| `algorithms.py` | Greedy, Hill Climbing, Simulated Annealing, Genetic Algorithm |
| `input_validation.py` | ตรวจชุดข้อมูลนำเข้า |
| `solution_validator.py` | ตัวตรวจคำตอบอิสระ (hard constraints และ metrics) |
| `runner.py` | รันหนึ่งครั้งแบบทำซ้ำได้ (ใช้ทั้งในเว็บและ CLI) |
| `cli.py` | command line สำหรับรันบนเครื่อง |
| `batch.py` | รันชุดใหญ่หลาย process แบบทำต่อได้ |
| `tune.py` | จูนพารามิเตอร์ |
| `analyze.py` | สถิติและกราฟของการทดลองสุดท้าย |
| `studies.py` | การศึกษาเรื่องงบ และเรื่อง Lab ขาดแคลน |
| `compare_modes.py` | ตารางเทียบห้องรายสัปดาห์กับห้องคงที่ |

5 ไฟล์แรกในตาราง (`lab_core.py` ถึง `runner.py`) คือ engine ที่ถูกนำไปคิด `engine_sha256` ใน manifest ของผลทดลอง ถ้าแก้ไฟล์เหล่านี้ ผลเดิมจะไม่ถูกนำมาใช้ซ้ำโดยอัตโนมัติ
