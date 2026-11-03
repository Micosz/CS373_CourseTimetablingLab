# CS373 Project Progress · 4 November 2026

เว็บสไลด์ภาษาไทย 12 หน้า รวมเอกสารอ้างอิง พร้อมบทพูด

## เปิดใช้งาน

เปิด `index.html` ได้โดยตรง (เนื้อหาและภาพอยู่ใน repo; ฟอนต์ออนไลน์มี fallback)
หรือใช้ `python3 -m http.server 8767` / Windows `py -m http.server 8767` แล้วเปิด http://localhost:8767

- ลูกศรขวา / Space: เปิดรายละเอียดก่อนเปลี่ยนหน้า
- ลูกศรซ้าย: ย้อนตามจังหวะ
- F: เต็มจอ (บทพูดอ่านแยกใน speaker-notes.md)
- สารบัญเลือกหน้า, Home/End: หน้าแรก/สุดท้าย
- ใช้ `speaker-notes.md` ซ้อมประมาณ 10–12 นาที

## Evidence and scope

ภาพเว็บเป็นภาพจริงจาก QA เดิม 4 runs, budget 4 ไม่ใช่ชุด 8 runs ใน verification-summary.json
verification-summary.json บันทึก browser smoke 4 methods × seeds 42,43, budget 12, 8 independent audits passed.
ตัวเลข tests มาจาก QA.md ของ workbench วันที่ 27 Oct 2026 ไม่ได้รันใหม่เพื่อสร้างสไลด์
ยังไม่มี final comparative experiment หรือผลพิสูจน์ว่ารายสัปดาห์ดีกว่าห้องคงที่ใน deck นี้
แผน 30 seeds ยังเป็นข้อเสนอ; fixed-room baseline ยังต้องทำหรือปรับขอบเขตกับอาจารย์

Source workbench: https://github.com/Micosz/course-timetabling-lab
QA: https://github.com/Micosz/course-timetabling-lab/blob/main/QA.md
Dataset: https://www.unitime.org/uct_datasets.php
ต้นทางเนื้อหา: Course Timetabling with Weekly Lab Requirements - Project Proposal Update (Revised), 7 หน้า และข้อสรุปในทีม
ไม่ได้เผยแพร่ไฟล์ proposal หรือ personal skills

## Bibliography corrections

ใช้ Bellio et al. (2016), Computers & Operations Research 65, 83–92, DOI 10.1016/j.cor.2015.07.002 แทนรายการ SA ที่ข้อมูลคลาดเคลื่อนใน proposal
Müller (2009) DOI ที่ถูกต้อง: 10.1007/s10479-009-0644-y
Lemos et al. (2019), Operations Research Perspectives 6, 100092, DOI 10.1016/j.orp.2018.100092
Xiao (2021), The Course Scheduling Problem with Room Considerations, Wright State University, doctoral dissertation
ITC2007: Curriculum-based Course Timetabling: The Problem Model, Queen’s University Belfast
ลิงก์ทั้งหมดอยู่ในหน้าสุดท้ายและ deck.js

## GitHub Pages (optional)

ใน repository ไป Settings → Pages → Deploy from a branch → main → / (root) → Save เพื่อเปิดเว็บสไลด์ออนไลน์ ไฟล์พร้อมใช้ แต่ต้องตรวจการ deploy ก่อนกล่าวว่า URL ออนไลน์พร้อมแล้ว
