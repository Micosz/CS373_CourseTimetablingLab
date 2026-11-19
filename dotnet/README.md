# C# engine (.NET 8)

ตัวแก้ปัญหาตัวเดียวของ repo: decoder, อัลกอริทึมทั้งสี่ (Greedy, HC, SA, GA), ตัวตรวจคำตอบอิสระ และ CLI **ผลทดลองที่ commit ไว้ใน `experiments/` ทั้งหมดผลิตด้วย engine นี้** (รันเมื่อ 2026-11-19 บน Windows, .NET 8) โค้ดนี้เริ่มจากการ port ตัวแก้ปัญหาภาษา Python ซึ่งถูกลบออกจาก repo แล้ว คอมเมนต์ port of `engine/...py` ในซอร์สจึงเป็นบันทึกที่มา

| | |
|---|---|
| การทดลองสุดท้าย 240 รัน | เวลาจริง 19.5 วินาที (20 process, `experiments/final/manifest.json`) |
| งบ 50,000 จำนวน 30 รัน | เวลาจริง 8.3 นาที (24 process, `experiments/convergence/b50000/manifest.json`) |
| ตรวจข้ามกับ Python (ก่อนลบ) | ก่อนลบตัวแก้ปัญหาภาษา Python ออกจาก repo ได้รัน 16 รันของการทดลองสุดท้าย (4 วิธี × 2 โหมดห้อง × seed 1001–1002) ด้วยตัวนั้นบนชุดข้อมูลใหม่ ได้ metric ตารางคำตอบ และ trace ตรงกับผลของ C# ทุกรัน การตรวจนี้ทำซ้ำจากโค้ดปัจจุบันไม่ได้แล้ว ตัวแก้ปัญหาภาษา Python อยู่ใน git history เท่านั้น (มีอยู่ครั้งสุดท้ายที่ commit 6d33611 บน main) |
| ทำซ้ำได้ | `FullParityTests` รันซ้ำครบ 240 รันของ `experiments/final` แล้วต้องได้ผลเดิมทุกรัน |

ไม่มีการวัดเวลาเทียบกับตัวแก้ปัญหาภาษา Python จึงไม่มีตัวเลขว่าเร็วกว่ากี่เท่า

โฟลเดอร์ `engine/` เหลือเครื่องมือ Python ที่ทำงานกับไฟล์ผลของ engine นี้: `analyze.py` (สถิติและรายงาน) และ `tune.py` (จูน โดยสั่ง CLI นี้) กับตัวตรวจ `input_validation.py` และ `solution_validator.py` ที่ใช้สร้าง fixture ของ tests เว็บ (`apps/web/`) ไม่รันอัลกอริทึม ใช้เปิดดูไฟล์ผลที่ engine นี้สร้าง และแอป Godot (`apps/godot/`) ใช้ engine นี้โดยตรง

## โครงสร้าง

```
Timetabling.sln
src/Timetabling.Engine/   library: PyRandom, Dataset, Problem (decoder), SearchContext, Algorithms,
                          SolutionValidator, InputValidator, Runner
src/Timetabling.Cli/      command line "timetabling" (run, batch run, batch merge)
tests/Timetabling.Engine.Tests/
                          tests เทียบ RNG กับ CPython และตัวตรวจกับ engine/*.py (Fixtures/*.py สร้างค่าอ้างอิง) และรันซ้ำผลใน experiments/
```

สิ่งที่ยังผูกกับ Python (เพื่อให้ผลตรงกับตัวแก้ปัญหาเดิมและกับตัวตรวจใน `engine/`):
- `PyRandom` เป็น MT19937 แบบเดียวกับ `random.Random` ของ CPython รวม `shuffle`, `randrange`, `choice`, `sample` ที่ใช้ขั้นตอนเดียวกัน
- Decoder ใช้ลำดับการวนและ tie-break เดียวกับ decoder ภาษา Python เดิม (เทียบ id ห้องแบบ ordinal เหมือน str ของ Python) และใช้ bitset แทน int ขนาดใหญ่ของ Python
- `SolutionValidator` ตรวจคำตอบซ้ำจากข้อมูลดิบแบบอิสระเหมือน `engine/solution_validator.py` ถ้าคะแนนจากการค้นหาไม่ตรงกับตัวตรวจ รันนั้นถูกทำเครื่องหมาย error

## ใช้งาน

ต้องมี [.NET 8 SDK](https://dotnet.microsoft.com/download) รันจาก root ของ repo:

```sh
dotnet test dotnet/Timetabling.sln --filter "Category!=Slow"   # ทดสอบเร็ว ราว 1 นาที
dotnet test dotnet/Timetabling.sln --filter "Category=Slow"    # รันซ้ำครบ 240 รันของ experiments/final ต้องได้ผลเดิม
```

```sh
dotnet run -c Release --project dotnet/src/Timetabling.Cli -- run --budget 50 --seed 42 --repeats 3 --output results
```

```sh
dotnet run -c Release --project dotnet/src/Timetabling.Cli -- batch run --methods greedy hc sa ga \
  --room-modes weekly fixed --seeds 1001-1030 --budget 500 \
  --parameters experiments/tuning/selected-parameters.json --output results/final-cs
```

ไฟล์ที่ได้ (`runs/`, `manifest.json`, `experiment.json.gz`, `experiment.csv`) อยู่ในรูปแบบไฟล์ผลการทดลองที่ `engine/analyze.py` และเว็บอ่าน จึงวิเคราะห์และเปิดในเว็บได้ทันทีที่หน้า **ผลที่เก็บไว้** รันซ้ำคำสั่งเดิมเพื่อทำต่อจากที่หยุดไว้ได้ Manifest บันทึก `"engine": "dotnet"` และ `engine_sha256` ของซอร์ส C# ทุกไฟล์ใน `src/Timetabling.Engine/` (hash ใช้บรรทัดแบบ LF จึงไม่ขึ้นกับการตั้งค่า line ending ของ git)

## ข้อต่างจากตัวแก้ปัญหา Python เดิมและตัวตรวจ Python

- ไม่มีวิธี `custom` (โค้ด Python ที่ผู้ใช้เขียนเอง) ซึ่งเคยมีในตัวแก้ปัญหา Python ที่ลบไปแล้ว
- ช่องในชุดข้อมูลที่ชนิดผิด (เช่น capacity เป็นข้อความ) จะล้มตอนอ่าน JSON แทนที่จะเป็นข้อความตรวจของ Python
- Audit ของ solution ที่ไม่ใช่ object เขียน `violations_truncated: false` เสมอ (Python ไม่มี key นี้ในกรณีนั้น)
