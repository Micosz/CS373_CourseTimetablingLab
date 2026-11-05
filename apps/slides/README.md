# CS373 Final Presentation · ผลงานขั้นสุดท้าย

เว็บสไลด์ภาษาไทย 17 หน้า ประมาณ 12–15 นาที พร้อมบทพูดทุกหน้า ไม่มี dependency หรือขั้นตอน build

หน้าตาออกแบบใน Claude Design ก่อน (ร่าง: https://claude.ai/artifact/BJz1B7PSfyayMF1YzGFWRE) แล้วนำ HTML ของแต่ละหน้ามาใช้ตรง ๆ แต่ละหน้าเป็นผืน 1920×1080 ที่จัดวางด้วย inline style และย่อขยายให้พอดีหน้าต่าง
ภาษาภาพ: พื้นขาว ตัวอักษร `#171717` น้ำเงิน `#0a72ef` และแดง `#d92d20`/`#ff5b4f` (ใช้สีทึบ แยกกันด้วยความสว่างและป้ายกำกับ ไม่ใช้สีอ่อน) ฟอนต์ Geist, Geist Mono และ IBM Plex Sans Thai จาก Google Fonts
กราฟทุกอันวาดใหม่จากไฟล์ผลจริง ไม่มีภาพหน้าจอแอป

| หน้า | เนื้อหา | ที่มาของตัวเลข |
|---|---|---|
| 1 | ปก | – |
| 2 | ห้องคงที่ทำให้ Lab ถูกจองทั้งเทอม (ตัวอย่างสมมติ) | – |
| 3 | สิ่งที่ทำเพิ่มจากข้อเสนอแนะ: 4 วิธี, 240 รัน, C# ~75 เท่า | `experiments/final/`, `experiments/engine-speed/` |
| 4 | ข้อมูล: 174 คลาส, 3,345 คาบรายสัปดาห์, Lab จำลอง 4 ห้อง | `README.md` ของ repository |
| 5 | ตัวแทนคำตอบร่วม + 4 อัลกอริทึม | `README.md` ของ repository |
| 6 | กติกาการทดลอง: seed จูน/ทดสอบ, งบ 500, สถิติ, 240/240 | `docs/protocol.md`, `experiments/final/README.md` |
| 7 | ผลการจูน | `experiments/tuning/README.md`, `summary.md` |
| 8 | ผลหลัก (dot plot 30 seed): GA 57.7 · HC 64.9 · SA 76.2 · Greedy 124.0 ชม. | `experiments/final/experiment.csv`, `analysis/report.md` |
| 9 | สถิติ: Friedman χ² = 63.12, GA ดีกว่า SA 26/30, GA กับ HC p = 0.188 | `experiments/final/analysis/report.md` |
| 10 | ตัวอย่าง A, B, C: ห้องคงที่ล็อก Lab ทั้งเทอม | ตัวอย่างสมมติ (บทพูดอ้าง 804 / 2,211 ชม. จาก `data/fall-cs.json.gz` และ 11 วิชาที่ไม่ได้ห้องจาก GA seed 1001 ใน `experiments/final/experiment.json.gz`) |
| 11 | เปลี่ยนห้อง: LB 783 ครั้ง, GA/HC 831, SA 835 | `experiments/final/analysis/report.md` |
| 12 | Lab ขาดแคลน 4/3/2 ห้อง: คาบที่ไม่มีห้อง 0/0/17.7 เทียบ 159/482/896 | `experiments/lab-scarcity/scarcity-summary.csv` |
| 13 | งบ 50/200/500/1000 | `experiments/budget/budget-summary.csv` |
| 14 | Engine C#: 30 นาที → 20 วินาที, ผลตรงกัน 240/240 | `experiments/final/manifest.json`, `experiments/engine-speed/` |
| 15 | ข้อจำกัด | README ของ tuning, budget, lab-scarcity |
| 16 | สรุป | ตัวเลขจากหน้า 8–14 |
| 17 | เอกสารอ้างอิง | – |

## ไฟล์

- `slides.json`: เนื้อหาทุกหน้า (`id`, `title`, `style` ของผืนสไลด์, `html`, `note` = บทพูด)
- `deck.js`: บรรทัดแรกคือ array `slides` ชุดเดียวกับ `slides.json` (หน้าเว็บอ่านจากตัวนี้ จึงเปิดไฟล์ตรง ๆ ได้โดยไม่ต้องมี server) ที่เหลือคือตัวควบคุมสไลด์
- `speaker-notes.md`: บทพูดชุดเดียวกับฟิลด์ `note`
- `style.css`: ค่าเริ่มต้นของผืนสไลด์ (div = flex column, ระยะขอบข้อความ 0) และแถบควบคุม
- `progress/`: สไลด์ความคืบหน้า 4 พ.ย. เก็บไว้เป็นประวัติ ไม่แก้

- `port_design.py`: สร้าง 3 ไฟล์ข้างบนจากร่างใน Claude Design (ไฟล์ `project/deck.json` และ `project/slides/*.html` ที่ดาวน์โหลดมา) พร้อมแปะ class สำหรับอนิเมชัน: `python apps/slides/port_design.py <โฟลเดอร์ project ของร่าง> apps/slides`

ทั้ง 3 ที่ (`slides.json`, บรรทัดแรกของ `deck.js`, `speaker-notes.md`) ต้องตรงกัน ทางที่ปลอดภัยคือแก้ในร่าง Claude Design แล้วรัน `port_design.py` ใหม่

## อนิเมชัน

- เปลี่ยนหน้า: หน้าเดิมจางออก หน้าใหม่เลื่อนขึ้นเล็กน้อย (ย้อนกลับเลื่อนลง)
- หน้า 11 → 12: ซูมเข้าจุดเล็ก ๆ ที่ป้าย "LB" ซึ่งกลายเป็นหน้า 12 (ตั้งค่าใน `ZOOMS` ของ `deck.js`)
- กราฟ: แท่งพุ่งขึ้น (หน้า 11, 12) แท่งยืดออก (หน้า 9, 14) จุดเด้งขึ้นทีละจุด (หน้า 8) กราฟเส้นวาดจากซ้ายไปขวา (หน้า 13) ช่องตารางสัปดาห์ทยอยขึ้น (หน้า 2, 10) เล่นใหม่ทุกครั้งที่เข้าหน้า
- เครื่องที่ตั้ง "ลดการเคลื่อนไหว" (prefers-reduced-motion) จะไม่มีอนิเมชันเลย

## เปิดใช้งาน

เปิด `index.html` ได้โดยตรง หรือรัน server ที่ root ของ repo: `python -m http.server 8766` แล้วเปิด http://localhost:8766/apps/slides/

- ลูกศรขวา / Space: หน้าถัดไป · ลูกศรซ้าย: ย้อน · Home/End: หน้าแรก/สุดท้าย
- F: เต็มจอ · สารบัญเลือกหน้า · ลิงก์ `#N` เปิดหน้าที่ N
- ฟอนต์โหลดจาก Google Fonts ถ้าออฟไลน์จะใช้ฟอนต์สำรองของเครื่อง (Tahoma/Arial)

### สไลด์ความคืบหน้า (4 พ.ย. 2026)

อยู่ที่ `progress/` เปิด `progress/index.html` หรือ http://localhost:8766/apps/slides/progress/ บน Vercel คือ `/progress/`

## Evidence and scope

- ตัวเลขผลทดลองทุกตัวคัดจากไฟล์ใน repository:
  - [`experiments/final/`](../../experiments/final/README.md) และ [`analysis/report.md`](../../experiments/final/analysis/report.md)
  - [`experiments/tuning/`](../../experiments/tuning/README.md), [`experiments/budget/`](../../experiments/budget/README.md), [`experiments/lab-scarcity/`](../../experiments/lab-scarcity/README.md)
  - [`experiments/engine-speed/`](../../experiments/engine-speed/README.md): เวลา C# เทียบ Python
  - กติกาการทดลอง: [`docs/protocol.md`](../../docs/protocol.md)
- ขอบเขต: ผลทั้งหมดมาจากชุดข้อมูลดัดแปลงชุดเดียว (Fall CS · Weekly Labs v1) และงบ 500 ที่ยังไม่อิ่มตัว

## ตรวจสอบ (5 พ.ย. 2026)

- เปิดผ่าน `python -m http.server 8766` ที่ viewport 1600×960 เดินครบ 17 หน้า ไม่มี console error ทุกหน้าแสดงตรงกับร่างใน Claude Design
- ยังไม่ได้ตรวจบน Vercel จริง

## เอกสารอ้างอิง

- Lemos, A., Melo, F. S., Monteiro, P. T., & Lynce, I. (2019). Room usage optimization in timetabling: A case study at Universidade de Lisboa. *Operations Research Perspectives, 6*, 100092. https://doi.org/10.1016/j.orp.2018.100092
- Bellio, R., Ceschia, S., Di Gaspero, L., Schaerf, A., & Urli, T. (2016). Feature-based tuning of simulated annealing applied to the curriculum-based course timetabling problem. *Computers & Operations Research, 65*, 83–92. https://doi.org/10.1016/j.cor.2015.07.002
- Müller, T. (2009). ITC2007 solver description: A hybrid approach. *Annals of Operations Research, 172*(1), 429–446. https://doi.org/10.1007/s10479-009-0644-y
- Xiao, L. (2021). *The Course Scheduling Problem with Room Considerations* [Doctoral dissertation, Wright State University]. https://corescholar.libraries.wright.edu/etd_all/2474/
- ITC2007. Curriculum-based Course Timetabling: The Problem Model. Queen’s University Belfast. https://www.eeecs.qub.ac.uk/itc2007/curriculmcourse/course_curriculm_index.htm
- UniTime. University course timetabling datasets, Purdue Fall 2007 CS (`pu-fal07-cs`). https://www.unitime.org/uct_datasets.php

## Deploy

ดู `DEPLOY.md` (Vercel Root Directory = `apps/slides`, ไม่มี build command)
