# แผนที่ repository

เริ่มอ่านตามสิ่งที่ต้องการ:

| อยากทำอะไร | เริ่มที่ |
|---|---|
| เปิดเว็บดูชุดข้อมูลและผลที่เก็บไว้ | [quick-start.md](quick-start.md) |
| ภาพรวมโครงงาน และวิธีรันการทดลองบนเครื่อง | [../README.md](../README.md) |
| รายละเอียดเชิงเทคนิค (วิธีแทนคำตอบ ข้อห้าม ความเท่าเทียม การสร้างชุดข้อมูลซ้ำ) | [technical.md](technical.md) |
| ดูผลทดลองทั้งหมด | [../experiments/INDEX.md](../experiments/INDEX.md) |
| กติกาการทดลอง (seed, งบ, สถิติ) | [protocol.md](protocol.md) |
| ทำไมออกแบบแบบนี้ เทียบกับงานวิจัย | [research-comparison.md](research-comparison.md) |
| ดูสไลด์นำเสนอ | [../apps/slides/](../apps/slides/README.md) |
| อ่านเล่มรายงาน | [report/](report/README.md) |
| ข้อมูลนำเข้าและสมมติฐาน | [../data/START_HERE.txt](../data/START_HERE.txt) |

## โฟลเดอร์

| Path | มีอะไร |
|---|---|
| [`apps/web/`](../apps/web/) | เว็บดูผล ไม่รันอัลกอริทึมในเบราว์เซอร์: หน้าข้อมูล (ชุดหลักและชุดแปรจำนวนสัปดาห์ Lab), หน้าผลที่เก็บไว้ (เปิดไฟล์ผลจาก engine C# ใน `experiments/` เช่น final, งบ 50,000 และ lab-weeks หรือนำเข้า `experiment.json.gz`) และหน้าผลเปรียบเทียบ (ตาราง กราฟ และตารางเรียนที่ได้) ไฟล์: `index.html`, `app.mjs` (UI, plots, export), `storage.mjs` (IndexedDB), `styles.css` |
| [`apps/slides/`](../apps/slides/README.md) | สไลด์นำเสนอ มี deck เดียว เปิดที่ `/` รายละเอียดไฟล์อยู่ใน README ของโฟลเดอร์ และ [DEPLOY.md](../apps/slides/DEPLOY.md) คือวิธีตั้งค่า Vercel |
| [`apps/godot/`](../apps/godot/README.md) | แอปเดสก์ท็อป Godot 4.7 (C#): แผนที่ห้องรายสัปดาห์, รันการค้นหาสด, เทียบ weekly/fixed ใช้ engine C# ตัวเดียวกับ CLI (ภาพหน้าจอในโฟลเดอร์ถ่ายกับชุดข้อมูลก่อนหน้า) |
| [`engine/`](../engine/) | เครื่องมือ Python เท่านั้น ไม่มีตัวแก้ปัญหา: วิเคราะห์ผล จูน และตัวตรวจ (ดูตารางด้านล่าง) |
| [`engine/tests/`](../engine/tests/) | tests ของเครื่องมือวิเคราะห์และชุดข้อมูล 19 รายการ (`python -m unittest discover -s engine/tests`) |
| [`dotnet/`](../dotnet/README.md) | engine C# ตัวแก้ปัญหาตัวเดียวของ repo ใช้ผลิตผลทดลองทั้งหมด, CLI `timetabling` (run / batch) และ tests ที่ตรวจว่าผลที่ commit ทำซ้ำได้ |
| [`data/`](../data/) | `fall-cs.json.gz` (ชุดข้อมูลหลัก), `provenance.json` (SHA-256), `assumptions.json`, `conversion_audit.json`, `FORMAT.txt`, `variants/` (ชุดข้อมูลที่มี Lab 3 และ 2 ห้อง, สัปดาห์ Lab แบบติดกันหรือเว้นสัปดาห์ และวิชา Lab ใช้ Lab 1 ถึง 15 สัปดาห์) |
| [`dataset_tools/`](../dataset_tools/) | converter และ config ที่ใช้สร้าง `data/` ซ้ำ รวมถึง `make_lab_variants.py` (Lab ขาดแคลน) `make_pattern_variants.py` (รูปแบบสัปดาห์ Lab) และ `make_lab_week_variants.py` (วิชา Lab ใช้ Lab 1 ถึง 15 สัปดาห์) |
| [`experiments/`](../experiments/INDEX.md) | ผลดิบและสรุปของทุกการทดลอง: `final/` (ผลหลัก), `tuning/`, `convergence/`, `lab-weeks/`, `lab-scarcity/`, `lab-week-patterns/`, `lab-hours-breakdown/` |
| [`docs/`](.) | เอกสารในหน้านี้, `QA.md` (บันทึกการตรวจ), `img/` (ภาพประกอบคู่มือ และ `img/redesign/` ภาพก่อน/หลังปรับหน้าตา) |
| `index.html` (root) | redirect ไป `apps/web/` เพื่อให้ URL ของ GitHub Pages เดิมใช้ได้ |

## ไฟล์ใน `engine/`

| ไฟล์ | หน้าที่ |
|---|---|
| `analyze.py` | สถิติ ตาราง และกราฟของการทดลอง จากไฟล์ผล `experiment.json.gz` |
| `tune.py` | จูนพารามิเตอร์ตาม protocol ข้อ 5 โดยสั่ง CLI ของ C# (ต้อง build ก่อน) |
| `input_validation.py` | ตรวจชุดข้อมูลนำเข้า ใช้โดย `dataset_tools/` และตัวสร้าง fixture ของ tests C# |
| `solution_validator.py` | ตัวตรวจคำตอบ (hard constraints และ metrics) ใช้โดยตัวสร้าง fixture `make_validator_cases.py` ของ tests C# |
| `tests/test_analyze.py`, `tests/test_variants.py` | tests ของ `analyze.py` และของชุดข้อมูลกับชุดแปร |

ค่า `engine_sha256` ใน manifest ของผลทดลองคือ SHA-256 ของซอร์ส C# ทุกไฟล์ `*.cs` ในโฟลเดอร์ `dotnet/src/Timetabling.Engine/` (ฝังไว้ใน assembly ตอน build และเก็บสำเนาไว้ใน `code_snapshot` ของไฟล์ผล) ถ้าแก้ไฟล์เหล่านี้ ตัวรันจะไม่ยอมรวมผลเก่ากับผลใหม่
