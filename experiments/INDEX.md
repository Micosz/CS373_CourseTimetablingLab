# ผลทดลองทั้งหมด

ทุกชุดใช้ชุดข้อมูล Fall CS · Weekly Labs v1 (`data/fall-cs.json.gz`) กติกาอยู่ใน [docs/protocol.md](../docs/protocol.md) ตัวเลขในตารางคัดมาจาก README ของแต่ละชุด

| ชุด | คำถาม | Seeds · งบ | ข้อสรุปหลัก | ไฟล์ |
|---|---|---|---|---|
| [fixed-room](fixed-room/README.md) (#3) | ห้องรายสัปดาห์เทียบกับห้องคงที่ (ผลเบื้องต้น ยังไม่จูน) | 1001–1030 · 50 | ห้องคงที่ทำให้ Lab ถูกครองโดยไม่ได้ใช้เพิ่มราว 1,800 ชม. ต่อเทอม | `weekly-seeds-*.json.gz/.csv`, `fixed-seeds-*.json.gz/.csv`, `summary.md` |
| [tuning](tuning/README.md) (#5) | พารามิเตอร์ที่ดีที่สุดของ HC, SA และ GA | 1–10 · 500 | ลองทั้งหมด 47 ชุดค่า และได้ค่าที่ล็อกไว้ใน `selected-parameters.json` | `experiment.json.gz/.csv`, `tuning-summary.csv`, `summary.md`, `selected-parameters.json` |
| [final](final/README.md) (#6) | เทียบ 4 วิธี × 2 โหมดห้อง | 1001–1030 · 500 | GA ≈ HC ดีกว่า SA และ Greedy ส่วนห้องคงที่จัดครบ 0% ในทุกวิธี | `experiment.json.gz/.csv`, [`analysis/report.md`](final/analysis/report.md) และกราฟ |
| [budget](budget/README.md) (#8) | ค้นหานานขึ้นได้อะไรเพิ่ม | 1001–1010 · 50/200/500/1000 | จัดครบทุกคาบตั้งแต่งบ 200 และยังดีขึ้นจนถึงงบ 1000 โดยลำดับวิธีไม่เปลี่ยน | `experiment.json.gz/.csv`, `budget-summary.csv`, `budget.svg`, `summary.md` |
| [lab-scarcity](lab-scarcity/README.md) (#13) | ถ้า Lab เหลือ 3 หรือ 2 ห้อง (GA) | 1001–1010 · 500 | ห้องรายสัปดาห์ยังจัดครบเมื่อเหลือ Lab 3 ห้อง ส่วนห้องคงที่จัดไม่ครบตั้งแต่ 4 ห้อง | `labs3/`, `labs2/`, `scarcity-summary.csv`, `scarcity.svg`, `summary.md` |
| [engine-speed](engine-speed/README.md) | engine C# เร็วกว่า Python เท่าไร และผลตรงกันไหม | 1001–1030 · 500 และ 1001–1003 · 500 | 240 รัน: 1,812 → 20.5 วินาที, เวลาค้นหารวมลด ≈ 75 เท่า · รันทีละรันเร็วขึ้น ≈ 99 เท่า · ผลตรงกันทุกรัน | `final-csharp/`, `single-worker/` (`manifest.json`, `experiment.csv`) |

นำไฟล์ `.json.gz` ทุกไฟล์เข้าเว็บได้โดยตรง (หรือ gunzip ก่อน) และ `manifest.json` ของแต่ละชุดบันทึก SHA-256 ของ dataset และ engine ที่ใช้
