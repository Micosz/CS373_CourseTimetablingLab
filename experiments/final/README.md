# การทดลองสุดท้าย: 4 วิธี × 30 seeds × 2 โหมดห้อง (issue #6)

รันเมื่อ 2026-11-05 ตาม [docs/protocol.md](../../docs/protocol.md) ด้วยพารามิเตอร์ที่จูนแล้วจาก [`experiments/tuning/`](../tuning/)

| | |
|---|---|
| วิธี | Greedy, HC, SA, GA |
| Seeds | 1001–1030 (seed ทดสอบ ไม่ถูกใช้ตอนจูน) ทั้งโหมด weekly และ fixed · seed และ initial genome เดียวกันต่อคู่ |
| งบ | 500 evaluations ต่อรัน (Greedy = 1 ตามนิยาม) · time cap 3,600 วินาที |
| พารามิเตอร์ | `experiments/tuning/selected-parameters.json`: HC patience 50 · SA acceptance 0.2, cooling 0.9 · GA ประชากร 35, mutation 0.66, crossover 0.64, tournament 5, elites 3 |
| ผลตรวจ | **240 / 240 รันผ่านตัวตรวจอิสระ** (hard violations = 0) · HC/SA/GA ครบงบทุกรัน · ไม่มีรันโดน time cap (นานสุด 252 วินาที) |
| ที่รัน | native CPython 3.13.14, Windows, 18 process พร้อมกัน · เวลาจริง **30 นาที** (1,812 วินาที) |
| Dataset SHA-256 | `c92918faeb82b4d5c9f702e0629fe5e8d48bcc1a1286c0b21d514a9021973968` |
| Engine SHA-256 | `222ae5d0adbbaf4cc0229a880ef57c50ae2c0df4959f96087b82d76e37c61134` (โค้ด engine เดียวกับตอนจูนและ `experiments/fixed-room/`) |

## รันซ้ำ

```sh
python3 engine/batch.py run --methods greedy hc sa ga --room-modes weekly fixed --seeds 1001-1030 \
  --budget 500 --seconds 3600 --parameters experiments/tuning/selected-parameters.json \
  --output experiments/final --workers 18 --name "Final experiment (docs/protocol.md)"
python3 engine/analyze.py experiments/final/experiment.json.gz --output experiments/final/analysis
```

ถ้าหยุดกลางทาง รันคำสั่งแรกซ้ำจะทำต่อโดยข้ามรันที่เสร็จแล้ว ผลจะตรงกันเมื่อใช้ dataset, โค้ด engine, พารามิเตอร์ และเวอร์ชัน Python เดียวกัน บนเครื่องที่มี core น้อยกว่าให้ลด `--workers` (รันเดี่ยวราว 75 วินาทีต่อรันของ HC/SA/GA; 180 รันที่ไม่ใช่ Greedy ≈ 3–4 ชม. บน core เดียว)

## ไฟล์

| ไฟล์ | เนื้อหา |
|---|---|
| `experiment.json.gz` | ผลดิบทั้ง 240 รัน: ข้อมูลนำเข้า โค้ด engine พารามิเตอร์ trace best-so-far ตารางเต็ม และผลตรวจของทุกรัน นำเข้าเว็บได้โดยตรง |
| `experiment.csv` | metric ต่อรัน |
| `manifest.json` | dataset, engine, Python, จำนวน process, เวลาจริง |
| `analysis/report.md` | **ตาราง สถิติ และสรุปทั้งหมด** (สร้างโดย `analyze.py` ห้ามแก้มือ) |
| `analysis/summary.csv`, `summary.json`, `stats.json`, `runs.csv` | ตัวเลขเดียวกันในรูปที่สไลด์/รายงานดึงไปใช้ได้ |
| `analysis/*.svg` | convergence, box plot ชั่วโมง Lab ไม่จำเป็น, weekly เทียบ fixed, การเปลี่ยนห้องเทียบ lower bound |

## ผลหลัก (ตัวเลขจาก `analysis/report.md`)

- **HC, SA และ GA จัดครบทุกคาบใน 30/30 seed** ส่วน Greedy ขาด 20 คาบทุก seed
- **GA ดีที่สุดในภาพรวม** (อันดับเฉลี่ย Friedman 1.53, χ² = 63.1, p < 0.001) Lab ไม่จำเป็นเฉลี่ย 57.7 ชม. เทียบกับ HC 64.9 และ SA 76.2 ชม. GA ดีกว่า SA อย่างมีนัยสำคัญ (26/30 seed) แต่ **GA กับ HC ยังแยกกันไม่ได้** (GA ชนะ 18/30, p ปรับแล้ว = 0.19) และ HC กับ SA ก็แยกไม่ได้ (p = 0.18)
- **ห้องคงที่ (fixed) แย่กว่าทุกวิธีทุก seed**: Lab ถูกครองโดยไม่ได้ใช้เพิ่มเฉลี่ย 1,801–1,949 ชม. ต่อเทอม และยังจัดไม่ได้ 150–390 คาบ เพราะ Lab 4 ห้องไม่พอให้จองทั้งเทอม
- **การเปลี่ยนห้องราว 831 ครั้งต่อเทอมอยู่ที่ 1.06 เท่าของ lower bound (783 ครั้ง)** ส่วนใหญ่จึงหลีกเลี่ยงไม่ได้ถ้าจะไม่ใช้ Lab เกินจำเป็น (#10)

ข้อควรระวัง: ทั้งหมดนี้เป็นผลบนชุดข้อมูลดัดแปลงชุดเดียว (Fall CS · Weekly Labs v1) และงบ 500 ครั้ง ผลของงบอื่นอยู่ใน [`experiments/budget/`](../budget/)
