# CS373 Final Presentation · ผลงานขั้นสุดท้าย

เว็บสไลด์ภาษาไทย 16 หน้า (ปก + 14 หน้าเนื้อหา + เอกสารอ้างอิง) ประมาณ 12–15 นาที พร้อมบทพูดทุกหน้า
ใช้ engine และสไตล์เดียวกับสไลด์ความคืบหน้า ไม่มี dependency หรือขั้นตอน build

| หน้า | เนื้อหา | ที่มาของตัวเลข |
|---|---|---|
| 1 | ปก | – |
| 2 | ปัญหาการจอง Lab ทั้งภาค และคำถามของโครงงาน (ตัวอย่างสมมติ) | – |
| 3 | ข้อมูล: 174 คลาส, 3,345 คาบรายสัปดาห์, Lab จำลอง 4 ห้อง, 804 ชม. Lab ที่จำเป็น | `README.md` ของ repository หัวข้อข้อมูลและขอบเขต |
| 4 | genome + decoder ร่วม, ตัวตรวจอิสระ, 4 อัลกอริทึม | `README.md` ของ repository |
| 5 | กติกา: seed จูน 1–10 / ทดสอบ 1001–1030, งบ 500, Friedman + Wilcoxon-Holm, 240/240 รันผ่านตัวตรวจ | `docs/protocol.md`, `experiments/final/README.md` |
| 6 | ผลจูน: 47 ชุดค่า × 10 seeds, ค่าที่เลือก, SA อยู่ขอบช่วง | `experiments/tuning/README.md`, `summary.md` |
| 7 | ผลหลัก: HC/SA/GA จัดครบ 30/30, Lab ไม่จำเป็น GA 57.7 · HC 64.9 · SA 76.2 · Greedy 124.0 ชม. | `experiments/final/analysis/report.md` + `lab-hours-boxplot.svg` |
| 8 | สถิติ: Friedman χ² = 63.12, GA ดีกว่า SA (26/30), GA กับ HC แยกไม่ได้ (p = 0.188) | `report.md` + `convergence.svg` |
| 9 | weekly เทียบ fixed: fixed จัดครบ 0%, Lab ไม่จำเป็นเพิ่ม 1,801–1,949 ชม. | `report.md` + `weekly-vs-fixed.svg` |
| 10 | เปลี่ยนห้อง ราว 831 ครั้ง = 1.06× lower bound 783 | `report.md` + `room-changes.svg` |
| 11 | Lab ขาดแคลน: weekly จัดครบที่ 3 ห้อง, fixed ขาด 159 คาบตั้งแต่ 4 ห้อง | `experiments/lab-scarcity/README.md`, `summary.md` + `scarcity.svg` |
| 12 | งบ 50/200/500/1000: ยังดีขึ้นถึง 1000, 500 พอสำหรับเทียบวิธี | `experiments/budget/README.md`, `summary.md` + `budget.svg` |
| 13 | เครื่องมือบนเว็บ: ชุดค่าสำเร็จรูป, heatmap/ห้องของแต่ละคลาส, CSV/JSON | `docs/quick-start.md` และภาพ `docs/img/quick-start-2.jpg` (commit 7b560a4, #12), commit 55caeba (#9) |
| 14 | ข้อจำกัด | README ของ tuning, budget, lab-scarcity |
| 15 | สรุป | ตัวเลขจากหน้า 7–12 |
| 16 | เอกสารอ้างอิง | – |

## เปิดใช้งาน

เปิด `index.html` ได้โดยตรง หรือรัน server ในโฟลเดอร์นี้:
`python -m http.server 8811` (Windows `py -m http.server 8811`) แล้วเปิด http://localhost:8811/

- ลูกศรขวา / Space: เปิดรายละเอียดก่อนเปลี่ยนหน้า · ลูกศรซ้าย: ย้อนตามจังหวะ
- F: เต็มจอ · สารบัญเลือกหน้า · Home/End: หน้าแรก/สุดท้าย
- บทพูดอยู่ใน `speaker-notes.md` (เนื้อหาเดียวกับ `note` ของแต่ละสไลด์ใน `deck.js` / `slides.json`)

### สไลด์ความคืบหน้า (4 พ.ย. 2026)

ย้ายไปอยู่ที่ `progress/` โดยไม่แก้เนื้อหา เปิด `progress/index.html` หรือ http://localhost:8811/progress/
บน Vercel คือ `/progress/` (`vercel.json` ตั้ง `trailingSlash: true` เพื่อให้ `/progress` redirect ไป `/progress/` และ path สัมพัทธ์ของ CSS/JS ถูกต้อง)
บันทึก QA เดิมอยู่ใน `progress/QA.md`

## Evidence and scope

- ตัวเลขผลทดลองทุกตัวคัดจากไฟล์ใน repository ไม่ได้รันการทดลองใหม่เพื่อทำสไลด์:
  - [`experiments/final/`](../experiments/final/README.md) และ [`analysis/report.md`](../experiments/final/analysis/report.md): 4 วิธี × seed 1001–1030 × weekly/fixed, งบ 500, พารามิเตอร์ที่จูนแล้ว
  - [`experiments/tuning/`](../experiments/tuning/README.md): 47 ชุดค่า × seed 1–10, `selected-parameters.json`
  - [`experiments/budget/`](../experiments/budget/README.md): งบ 50/200/500/1000 บน seed 1001–1010
  - [`experiments/lab-scarcity/`](../experiments/lab-scarcity/README.md): Lab 4/3/2 ห้อง (GA, seed 1001–1010)
  - กติกาการทดลอง: [`docs/protocol.md`](../docs/protocol.md)
- กราฟใน `assets/final/*.svg` คัดลอกจากโฟลเดอร์ผลข้างต้นแบบไม่แก้ไข (byte-identical) กราฟมีสีพื้นของตัวเอง และ `style.css` ตั้ง `color-scheme: light` ให้กราฟแสดงแบบสว่างแม้เครื่องใช้ dark mode
- `assets/final/web-presets.jpg` คือ `docs/img/quick-start-2.jpg` จาก commit 7b560a4 (branch issue-12-presets) ฟีเจอร์ชุดค่าสำเร็จรูป (#12) และ heatmap/ห้องของแต่ละคลาส/CSV (#9) อยู่ในงานของ issue นั้น ๆ
- ขอบเขต: ผลทั้งหมดมาจากชุดข้อมูลดัดแปลงชุดเดียว (Fall CS · Weekly Labs v1, adapted synthetic benchmark) และงบ 500 ที่ยังไม่อิ่มตัว ผลจากเว็บ (Pyodide) เป็นการสาธิต หลักฐานหลักมาจาก native CPython ตาม protocol

## ตรวจสอบ (5 พ.ย. 2026)

- เปิดผ่าน `python -m http.server 8811` ที่ viewport 1280×720 เดินหน้า 43 จังหวะจนถึงหน้าสุดท้าย และย้อนกลับครบ ไม่มี console error
- ทุกหน้าไม่มีเนื้อหาทับ footer หรือล้นขอบขวา รูปทั้ง 7 โหลดได้ ตรวจกราฟซ้ำในโหมด dark ของเบราว์เซอร์แล้วกราฟยังเป็นพื้นสว่าง
- `progress/` เปิดได้ CSS และ `assets/preliminary-comparison.csv` โหลดได้ เดินครบ 13 หน้า ไม่มี console error
- ยังไม่ได้ตรวจบน Vercel จริง และใช้ฟอนต์ Google Fonts ตามที่โหลดได้ในเครื่องที่ตรวจ

## เอกสารอ้างอิง

- Lemos, A., Melo, F. S., Monteiro, P. T., & Lynce, I. (2019). Room usage optimization in timetabling: A case study at Universidade de Lisboa. *Operations Research Perspectives, 6*, 100092. https://doi.org/10.1016/j.orp.2018.100092
- Bellio, R., Ceschia, S., Di Gaspero, L., Schaerf, A., & Urli, T. (2016). Feature-based tuning of simulated annealing applied to the curriculum-based course timetabling problem. *Computers & Operations Research, 65*, 83–92. https://doi.org/10.1016/j.cor.2015.07.002
- Müller, T. (2009). ITC2007 solver description: A hybrid approach. *Annals of Operations Research, 172*(1), 429–446. https://doi.org/10.1007/s10479-009-0644-y
- Xiao, L. (2021). *The Course Scheduling Problem with Room Considerations* [Doctoral dissertation, Wright State University]. https://corescholar.libraries.wright.edu/etd_all/2474/
- ITC2007. Curriculum-based Course Timetabling: The Problem Model. Queen’s University Belfast. https://www.eeecs.qub.ac.uk/itc2007/curriculmcourse/course_curriculm_index.htm
- UniTime. University course timetabling datasets, Purdue Fall 2007 CS (`pu-fal07-cs`). https://www.unitime.org/uct_datasets.php

## Deploy

ดู `DEPLOY.md` (Vercel Root Directory = `presentation`, ไม่มี build command)
Source workbench: https://github.com/Micosz/course-timetabling-lab
