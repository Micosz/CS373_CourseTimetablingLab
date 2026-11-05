# Presentation deployment

สไลด์อยู่ใน apps/slides/ ส่วนเว็บห้องทดลองอยู่ใน apps/web/ (root `index.html` redirect ไปที่นั่น)

## Vercel (โดเมน cs373presentation.vercel.app)

1. ใน Vercel project cs373presentation เปิด Settings → Git ตรวจว่า Connected Git Repository เป็น Micosz/CS373_CourseTimetablingLab
2. Settings → Build and Deployment ตั้ง Root Directory เป็น `apps/slides` แล้วกด Save (เดิมคือ `presentation`; ค่านี้อยู่ใน Vercel จึงต้องแก้แยกจากโค้ด)
3. Framework Preset: Other; ไม่ต้องมี Install Command หรือ Build Command; Output Directory ใช้ . (โฟลเดอร์ปัจจุบัน)
4. หลังเปลี่ยนการตั้งค่า ให้ Redeploy deployment ของ branch `restructure-layout` หรือ push commit ใหม่บน branch นี้เพื่อทดสอบ Preview ของ PR #22 การกด Save อย่างเดียวไม่รัน deployment ที่ล้มไปแล้วซ้ำ
5. ตรวจว่า Vercel Preview สำเร็จและเปิดทั้ง `/` กับ `/progress/` ได้ ก่อนรวม PR เข้า main แล้วตรวจ Production ที่โดเมนเดิมอีกครั้ง

ระหว่างย้ายโครงสร้าง main รุ่นเดิมยังไม่มี `apps/slides/` จึงต้องใช้ commit จาก PR #22 สำหรับ Preview หลังเปลี่ยน Root Directory

การย้ายไฟล์ใน repo ไม่ได้เปลี่ยนการตั้งค่า Vercel โดยอัตโนมัติ

หมายเหตุจากรอบย้าย repo เดิม: หลังตรวจโดเมนเดิมสำเร็จ เจ้าของขอให้ลบ repository Micosz/CS373_Presentation (GitHub → Settings → General → Danger Zone)

## เปิดจากเครื่อง

เปิด apps/slides/index.html ได้โดยตรง หรือรัน HTTP server ที่ root และเข้า /apps/slides/
ลูกศรซ้าย/ขวา: ย้อน/เดินหน้าทีละจังหวะ; F: เต็มจอ
บทพูดอยู่ใน speaker-notes.md ไม่มีปุ่มบทพูดบนเว็บ
สไลด์ Final อยู่ที่ apps/slides/index.html ส่วนสไลด์ความคืบหน้า (4 พ.ย.) อยู่ที่ apps/slides/progress/ (บน Vercel: /progress/)
