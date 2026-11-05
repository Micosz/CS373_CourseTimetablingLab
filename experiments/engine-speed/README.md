# ความเร็ว engine C# เทียบ Python

วัดเมื่อ 2026-11-05 บนเครื่องเดียวกัน (Windows, 28 คอร์) ด้วย dataset, พารามิเตอร์ (`experiments/tuning/selected-parameters.json`) และงบ 500 เดียวกับ [การทดลองสุดท้าย](../final/README.md)
ไม่ได้ใช้ผลชุดนี้ตอบคำถามวิจัย ใช้เป็นหลักฐานความเร็วและ parity ของ engine C# (`dotnet/`) เท่านั้น

## 1. การทดลองสุดท้ายทั้งชุด (240 รัน)

| | Python | C# |
|---|---|---|
| ไฟล์ | [`../final/manifest.json`](../final/manifest.json), [`../final/experiment.csv`](../final/experiment.csv) | [`final-csharp/manifest.json`](final-csharp/manifest.json), [`final-csharp/experiment.csv`](final-csharp/experiment.csv) |
| Runtime | CPython 3.13.14 | .NET 8.0.31 |
| จำนวน worker | 18 process | 26 thread |
| เวลาจริงทั้งชุด | **1,811.6 วินาที** (≈ 30 นาที) | **20.5 วินาที** |
| เวลาค้นหารวมทุกรัน (`search_seconds`) | 32,272.2 วินาที | 431.1 วินาที (≈ 75 เท่า) |

ผล 240 รันตรงกันทุกรันในคอลัมน์ `unassigned_weekly_sessions`, `unnecessary_lab_hours`, `room_changes` และ `valid`
เวลาจริงขึ้นกับจำนวน worker ที่ต่างกัน จึงดูเวลาค้นหารวมประกอบ (ตัวเลขนี้ยังรวมผลของการแย่ง CPU ระหว่าง worker ทั้งสองฝั่ง)

## 2. รันทีละรัน (1 worker ทั้งสองฝั่ง)

HC, SA, GA × seed 1001–1003 โหมด weekly = 9 รัน ([`single-worker/python/`](single-worker/python/), [`single-worker/csharp/`](single-worker/csharp/))

| | Python 3.11.15 | C# (.NET 8.0.31) |
|---|---|---|
| เวลาค้นหารวม 9 รัน | 991.7 วินาที | 9.97 วินาที |
| ต่อรัน | 72–146 วินาที | 0.95–1.75 วินาที |

เร็วขึ้นราว **99 เท่า** (ต่อรัน 43–149 เท่า) ผลทั้ง 9 รันตรงกันทุกคอลัมน์ข้างต้น
ช่วงเวลาของ Python กว้างเพราะเครื่องมีงานอื่นทำอยู่ระหว่างวัด ตัวเลขนี้จึงเป็นค่าประมาณ ไม่ใช่ benchmark ที่ควบคุมเต็มที่

## รันซ้ำ

```sh
dotnet run -c Release --project dotnet/src/Timetabling.Cli -- batch run --methods greedy hc sa ga \
  --room-modes weekly fixed --seeds 1001-1030 --budget 500 \
  --parameters experiments/tuning/selected-parameters.json --output results/final-cs
dotnet run -c Release --project dotnet/src/Timetabling.Cli -- batch run --methods hc sa ga --room-modes weekly \
  --seeds 1001-1003 --budget 500 --parameters experiments/tuning/selected-parameters.json --workers 1 --output results/cs-1worker
python engine/batch.py run --methods hc sa ga --room-modes weekly --seeds 1001-1003 --budget 500 --seconds 3600 \
  --parameters experiments/tuning/selected-parameters.json --workers 1 --output results/py-1worker
```

เก็บเฉพาะ `manifest.json` และ `experiment.csv` (ไม่เก็บ `experiment.json.gz` เพราะคำตอบซ้ำกับ `experiments/final/`)
