# Presentation deployment

สไลด์อยู่ใน presentation/ ส่วนเว็บห้องทดลองยังอยู่ที่ root ของ repository

## ย้าย Vercel project เดิม (คงโดเมน cs373presentation.vercel.app)

1. ใน Vercel project cs373presentation เปิด Settings → Git เปลี่ยน Connected Git Repository เป็น Micosz/course-timetabling-lab (อาจต้อง Disconnect ของเดิมก่อนแล้ว Connect repository ใหม่)
2. Settings → Build and Deployment ตั้ง Root Directory เป็น presentation
3. Framework Preset: Other; ไม่ต้องมี Install Command หรือ Build Command; Output Directory ใช้ . (โฟลเดอร์ปัจจุบัน)
4. Deploy commit บน main หลังเปลี่ยนการตั้งค่า ตรวจว่าโดเมนเดิมแสดงสไลด์ และหน้าเว็บห้องทดลองเดิมยังทำงาน
5. หลังตรวจโดเมนเดิมสำเร็จ ลบ repository Micosz/CS373_Presentation ที่ GitHub → Settings → General → Danger Zone → Delete this repository ตามคำขอเจ้าของ

การเพิ่มไฟล์ใน repo ใหม่ไม่ได้เปลี่ยน Git integration ของ Vercel โดยอัตโนมัติ
ยังไม่ได้ลบ repo เดิมหรือเปลี่ยน Vercel integration ผ่านเครื่องมือในรอบย้ายนี้

## เปิดจากเครื่อง

ดาวน์โหลด repository แล้วเปิด presentation/index.html ได้โดยตรง หรือรัน HTTP server ที่ root และเข้า /presentation/
ลูกศรซ้าย/ขวา: ย้อน/เดินหน้าทีละจังหวะ; F: เต็มจอ
บทพูดอยู่ใน speaker-notes.md ไม่มีปุ่มบทพูดบนเว็บ
สไลด์ Final อยู่ที่ presentation/index.html ส่วนสไลด์ความคืบหน้า (4 พ.ย.) อยู่ที่ presentation/progress/ (บน Vercel: /progress/)
