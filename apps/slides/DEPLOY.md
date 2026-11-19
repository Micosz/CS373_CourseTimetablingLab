# Presentation deployment

สไลด์อยู่ใน apps/slides/ มี deck เดียว เปิดที่ `/` ส่วนเว็บห้องทดลองอยู่ใน apps/web/ (root `index.html` redirect ไปที่นั่น)

## Vercel (โดเมน cs373presentation.vercel.app)

1. ใน Vercel project cs373presentation เปิด Settings → Git ตรวจว่า Connected Git Repository เป็น Micosz/CS373_CourseTimetablingLab
2. Settings → Build and Deployment ตั้ง Root Directory เป็น `apps/slides` แล้วกด Save (ค่านี้อยู่ใน Vercel จึงต้องแก้แยกจากโค้ด)
3. Framework Preset: Other, ไม่ต้องมี Install Command หรือ Build Command, Output Directory ใช้โฟลเดอร์ปัจจุบัน (ตรงกับ `vercel.json`)
4. ไฟล์ที่ `simple/build.py` สร้าง (`simple/deck.js`, `simple/slides.json`, `simple/speaker-notes.md`) ต้อง commit มาด้วย เพราะ Vercel ไม่รัน build
5. ตรวจว่า Vercel Preview เปิด `/` ได้ก่อนรวม PR เข้า main แล้วตรวจ Production ที่โดเมนเดิมอีกครั้ง

ลิงก์เก่า `/simple/` ยังใช้ได้ หน้านั้นส่งต่อมาที่ `/` โดยคงเลขหน้าไว้

## เปิดจากเครื่อง

เปิด apps/slides/index.html ได้โดยตรง หรือรัน `python -m http.server 8766 --directory apps/slides` แล้วเปิด http://localhost:8766/
ลูกศรซ้ายและขวา: ย้อนและเดินหน้าทีละหน้า, F: เต็มจอ
บทพูดอยู่ใน simple/speaker-notes.md ไม่มีปุ่มบทพูดบนเว็บ
