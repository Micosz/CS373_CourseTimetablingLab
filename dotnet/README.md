# C# engine (.NET 8)

Engine ตัวเดียวกับ `engine/` (Python) เขียนใหม่ใน C# **ผลออกมาเหมือนกันทุกบิต**: seed เดียวกันได้คำตอบ, trace และ metrics เดียวกับ Python ผลทดลองที่ commit ไว้ทั้งหมดจึงใช้ engine นี้ทำซ้ำได้ แต่เร็วกว่ามาก

| | Python (`engine/batch.py`) | C# (`timetabling batch run`) |
|---|---|---|
| การทดลองสุดท้าย 240 รัน | 1,812 วินาที (18 process) | 76 วินาที (28 thread) |
| ผลลัพธ์ | ต้นฉบับ | ตรงกันทุกรัน (ทดสอบใน `FullParityTests`) |

Python ยังเป็น **ต้นฉบับอ้างอิง** และเป็น runtime ของเว็บ (Pyodide รองรับโหมดเขียนอัลกอริทึมเอง) ส่วน C# ใช้กับงานรันชุดใหญ่และแอป Godot (`apps/godot/`)

## โครงสร้าง

```
Timetabling.sln
src/Timetabling.Engine/   library: PyRandom, Dataset, Problem (decoder), SearchContext, Algorithms,
                          SolutionValidator, InputValidator, Runner
src/Timetabling.Cli/      command line "timetabling" (run, batch run, batch merge)
tests/Timetabling.Engine.Tests/
                          parity tests กับ CPython และผลใน experiments/ (Fixtures/*.py สร้างค่าอ้างอิงจาก Python)
```

ทำไมได้ผลตรงกับ Python:
- `PyRandom` เป็น MT19937 แบบเดียวกับ `random.Random` ของ CPython รวม `shuffle`, `randrange`, `choice`, `sample` ที่ใช้ขั้นตอนเดียวกัน
- Decoder ใช้ลำดับการวนและ tie-break เดียวกับ `lab_core.py` (เทียบ id ห้องแบบ ordinal เหมือน str ของ Python) และใช้ bitset แทน int ขนาดใหญ่ของ Python
- `SolutionValidator` ตรวจคำตอบซ้ำจากข้อมูลดิบแบบอิสระเหมือน `solution_validator.py` ถ้าคะแนนจากการค้นหาไม่ตรงกับตัวตรวจ รันนั้นถูกทำเครื่องหมาย error

## ใช้งาน

ต้องมี [.NET 8 SDK](https://dotnet.microsoft.com/download) รันจาก root ของ repo:

```sh
dotnet test dotnet/Timetabling.sln --filter "Category!=Slow"   # ทดสอบเร็ว ราว 1 นาที
dotnet test dotnet/Timetabling.sln --filter "Category=Slow"    # replay ครบ 240 รันของ experiments/final
```

```sh
dotnet run -c Release --project dotnet/src/Timetabling.Cli -- run --budget 50 --seed 42 --repeats 3 --output results
```

```sh
dotnet run -c Release --project dotnet/src/Timetabling.Cli -- batch run --methods greedy hc sa ga \
  --room-modes weekly fixed --seeds 1001-1030 --budget 500 \
  --parameters experiments/tuning/selected-parameters.json --output results/final-cs
```

ไฟล์ที่ได้ (`runs/`, `manifest.json`, `experiment.json.gz`, `experiment.csv`) อยู่ในรูปแบบเดียวกับ `engine/batch.py` จึงใช้กับ `engine/analyze.py` และนำเข้าเว็บได้ทันที รันซ้ำคำสั่งเดิมเพื่อทำต่อจากที่หยุดไว้ได้ Manifest บันทึก `"engine": "dotnet"` และ `engine_sha256` ของซอร์ส C# (hash ใช้บรรทัดแบบ LF จึงไม่ขึ้นกับการตั้งค่า line ending ของ git)

## ข้อต่างจาก Python ที่ตั้งใจ

- ไม่มีวิธี `custom` (โค้ด Python ที่ผู้ใช้เขียนเอง) ใช้ได้เฉพาะบนเว็บ
- ช่องในชุดข้อมูลที่ชนิดผิด (เช่น capacity เป็นข้อความ) จะล้มตอนอ่าน JSON แทนที่จะเป็นข้อความตรวจของ Python
- Audit ของ solution ที่ไม่ใช่ object เขียน `violations_truncated: false` เสมอ (Python ไม่มี key นี้ในกรณีนั้น)
