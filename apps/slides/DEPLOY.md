# Presentation deployment

สไลด์อยู่ใน apps/slides/ ส่วนเว็บห้องทดลองอยู่ใน apps/web/ (root `index.html` redirect ไปที่นั่น)

## Vercel (โดเมน cs373presentation.vercel.app)

1. ใน Vercel project cs373presentation เปิด Settings → Git ตรวจว่า Connected Git Repository เป็น Micosz/course-timetabling-lab
2. Settings → Build and Deployment ตั้ง Root Directory เป็น `apps/slides` (เดิมคือ `presentation`; ต้องเปลี่ยนเองหลัง merge การจัดโครงสร้างใหม่ ไม่อย่างนั้น deploy จะหาโฟลเดอร์ไม่เจอ)
3. Framework Preset: Other; ไม่ต้องมี Install Command หรือ Build Command; Output Directory ใช้ . (โฟลเดอร์ปัจจุบัน)
4. Deploy commit บน main หลังเปลี่ยนการตั้งค่า ตรวจว่าโดเมนเดิมแสดงสไลด์ และ /progress/ ยังเปิดได้

การย้ายไฟล์ใน repo ไม่ได้เปลี่ยนการตั้งค่า Vercel โดยอัตโนมัติ

หมายเหตุจากรอบย้าย repo เดิม: หลังตรวจโดเมนเดิมสำเร็จ เจ้าของขอให้ลบ repository Micosz/CS373_Presentation (GitHub → Settings → General → Danger Zone)

## เปิดจากเครื่อง

เปิด apps/slides/index.html ได้โดยตรง หรือรัน HTTP server ที่ root และเข้า /apps/slides/
ลูกศรซ้าย/ขวา: ย้อน/เดินหน้าทีละจังหวะ; F: เต็มจอ
บทพูดอยู่ใน speaker-notes.md ไม่มีปุ่มบทพูดบนเว็บ
สไลด์ Final อยู่ที่ apps/slides/index.html ส่วนสไลด์ความคืบหน้า (4 พ.ย.) อยู่ที่ apps/slides/progress/ (บน Vercel: /progress/)
