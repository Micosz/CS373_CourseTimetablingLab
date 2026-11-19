# การทดลองสุดท้าย: 4 วิธี × 30 seeds × 2 โหมดห้อง (issue #6)

รันเมื่อ 2026-11-19 บนชุดข้อมูลหลักชุดปัจจุบัน (Fall CS Weekly Labs v2) ตาม [docs/protocol.md](../../docs/protocol.md) ด้วยพารามิเตอร์ที่จูนแล้วจาก [`experiments/tuning/`](../tuning/)

| | |
|---|---|
| วิธี | Greedy, HC, SA, GA |
| Seeds | 1001–1030 (seed ทดสอบ ไม่ถูกใช้ตอนจูน) ทั้งโหมด weekly และ fixed โดยใช้ seed และ initial genome เดียวกันต่อคู่ |
| งบ | 500 evaluations ต่อรัน (Greedy = 1 ตามนิยาม), time cap 3,600 วินาที |
| พารามิเตอร์ | `experiments/tuning/selected-parameters.json`: HC patience 200, SA acceptance 0.8 และ cooling 0.97, GA ประชากร 12, mutation 0.86, crossover 0.85, tournament 4, elites 3 |
| ผลตรวจ | **240 / 240 รันผ่านตัวตรวจอิสระ** (hard violations = 0) HC, SA และ GA ครบงบทุกรัน ไม่มีรันโดน time cap (นานสุดราว 2.5 วินาที) |
| ที่รัน | engine C# (.NET 8.0.31), Windows, 20 process พร้อมกัน, เวลาจริง **19.5 วินาที** |
| Dataset SHA-256 | `dcb93db81f2bd60f1ff53bdb8b6c20899c9642489336580a9b209aa74495ee61` |
| Engine SHA-256 | `e9222d735e2332c6220122760a91fc730e5aa89874a246a4b24ebaa5194c7db1` (เดียวกับตอนจูน) |

## รันซ้ำ

```sh
dotnet build -c Release dotnet/src/Timetabling.Cli
dotnet run -c Release --no-build --project dotnet/src/Timetabling.Cli -- batch run \
  --methods greedy hc sa ga --room-modes weekly fixed --seeds 1001-1030 --budget 500 --seconds 3600 \
  --parameters experiments/tuning/selected-parameters.json --workers 20 \
  --name "Final experiment (docs/protocol.md)" --output experiments/final
python engine/analyze.py experiments/final/experiment.json.gz --output experiments/final/analysis
```

ผลจะตรงกันเมื่อใช้ dataset, โค้ด engine และพารามิเตอร์เดียวกัน ก่อนลบตัวแก้ปัญหาภาษา Python ออกจาก repo ได้รัน 16 รันของการทดลองสุดท้าย (4 วิธี × 2 โหมดห้อง × seed 1001–1002) ด้วยตัวนั้นบนชุดข้อมูลใหม่ ได้ metric ตารางคำตอบ และ trace ตรงกับผลของ C# ทุกรัน การตรวจนี้ทำซ้ำจากโค้ดปัจจุบันไม่ได้แล้ว ตัวแก้ปัญหาภาษา Python อยู่ใน git history เท่านั้น (มีอยู่ครั้งสุดท้ายที่ commit 6d33611 บน main)

## ไฟล์

| ไฟล์ | เนื้อหา |
|---|---|
| `experiment.json.gz` | ผลดิบทั้ง 240 รัน: ข้อมูลนำเข้า โค้ด engine พารามิเตอร์ trace best-so-far ตารางเต็ม และผลตรวจของทุกรัน นำเข้าเว็บได้โดยตรง |
| `experiment.csv` | metric ต่อรัน |
| `manifest.json` | dataset, engine, เวอร์ชัน .NET, จำนวน process, เวลาจริง |
| `analysis/report.md` | **ตาราง สถิติ และสรุปทั้งหมด** (สร้างโดย `analyze.py` ห้ามแก้มือ) |
| `analysis/summary.csv`, `summary.json`, `stats.json`, `runs.csv` | ตัวเลขเดียวกันในรูปที่สไลด์และรายงานดึงไปใช้ได้ |
| `analysis/*.svg` | convergence, box plot ชั่วโมง Lab ไม่จำเป็น, weekly เทียบ fixed, การเปลี่ยนห้องเทียบ lower bound |

## ผลหลัก (ตัวเลขจาก `analysis/report.md`)

โหมด weekly เฉลี่ย 30 seed

| วิธี | คาบที่ยังจัดไม่ได้ | รันที่จัดครบ | Lab ไม่จำเป็น (ชม.) | เปลี่ยนห้อง |
|---|---:|---:|---:|---:|
| Greedy | 14.0 | 0/30 | 242.0 | 654.0 |
| HC | 0.2 | 26/30 | 169.4 | 624.4 |
| SA | 0.03 | 29/30 | 145.8 | 619.7 |
| GA | 0.07 | 28/30 | 146.9 | 617.8 |

- **วิธีค้นหาทั้งสามดีกว่า Greedy ทุก seed** (30/30, p ปรับแล้ว < 0.001) Friedman χ² = 56.44, p < 0.001 อันดับเฉลี่ย Greedy 4.00, HC 2.30, SA 1.83, GA 1.87
- **HC, SA และ GA ยังแยกกันไม่ได้ที่งบ 500** HC กับ SA p = 0.102, HC กับ GA p = 0.102, SA กับ GA p = 0.666 (Wilcoxon จับคู่ ปรับ Holm) จึงไม่มีผู้ชนะในสามวิธีนี้
- **ที่งบ 500 ยังจัดไม่ครบทุกรัน** HC ขาดคาบใน 4 seed, GA 2 seed, SA 1 seed (ขาดไม่เกิน 2 คาบจาก 3,345) ทุกรันจัดครบตั้งแต่งบ 1,000 ([convergence](../convergence/README.md))
- **โหมด fixed จัดไม่ครบสักรัน** ขาดเฉลี่ย 179 ถึง 199 คาบ (Greedy 285) และมี Lab ไม่จำเป็นราว 2,020 ถึง 2,050 ชม. เทียบกับ weekly ต่างกันเฉลี่ย +1,791 ถึง +1,900 ชม. และ +179 ถึง +271 คาบ (p < 0.001 ทุกวิธี) ผลข้อนี้เป็นไปตามที่ตั้งโจทย์ไว้ เพราะในโหมด fixed คาบที่มีสัปดาห์ Lab ต้องอยู่ Lab ทั้งเทอม
- **การเปลี่ยนห้องราว 621 ครั้งต่อเทอมอยู่ที่ 1.04 ถึง 1.05 เท่าของ lower bound (596 ครั้ง)** ส่วนใหญ่จึงหลีกเลี่ยงไม่ได้ถ้าจะจัดครบและไม่ใช้ Lab เกินจำเป็น (#10)

ข้อควรระวัง: ทั้งหมดนี้เป็นผลบนชุดข้อมูลดัดแปลงชุดเดียวที่ความต้องการ Lab สร้างขึ้นเอง (assumption A10 สุ่มเลือกวิชา Lab ครั้งเดียว) และงบ 500 ครั้ง ซึ่งเล็ก ข้อสรุปเรื่องการจัดครบและลำดับวิธีเปลี่ยนตามงบ ดู [`experiments/convergence/`](../convergence/README.md)
