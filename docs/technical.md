# รายละเอียดเชิงเทคนิค

หน้านี้รวมรายละเอียดเชิงเทคนิค: เว็บดูผล ขอบเขตข้อมูล วิธีแทนคำตอบ ข้อห้ามและเป้าหมาย ความเท่าเทียมในการเทียบ การรันบนเครื่อง และการสร้างชุดข้อมูลซ้ำ ภาพรวมแบบอ่านง่ายอยู่ที่ [README](../README.md)

## เว็บดูผล

เว็บใน `apps/web/` **ไม่รันอัลกอริทึมในเบราว์เซอร์** เป็นที่ดูชุดข้อมูลและไฟล์ผลที่ engine C# สร้างไว้ คนที่เพิ่งเปิดครั้งแรกอ่าน [คู่มือเริ่มใช้ 3 ขั้น](quick-start.md) ก่อน เว็บมีสามหน้า

1. **ข้อมูล** แสดงชุดข้อมูลหลัก Fall CS (174 คลาส, 3,345 คาบรายสัปดาห์) ตารางว่าวิชาไหนต้องใช้ Lab สัปดาห์ไหน และตัวเลือกชุดแปรที่วิชา Lab ใช้ Lab 1 ถึง 15 สัปดาห์ อัปโหลดชุดข้อมูลของตัวเองได้
2. **ผลที่เก็บไว้** เปิดไฟล์ผลที่ commit ไว้ (`experiments/final/`, `experiments/convergence/b50000/` และ `experiments/lab-weeks/wNN/`) หรือนำเข้า `experiment.json` / `experiment.json.gz` ที่รันเองด้วย CLI
3. **ผลเปรียบเทียบ** แสดงตารางสรุปต่อวิธี ผลทุกรัน กราฟ best-so-far และส่วน **ตรวจตารางที่ได้** ของรันที่เลือก (ทั้งโหมด weekly และ fixed):
   - **ตารางรายสัปดาห์**: ทุกคาบของสัปดาห์ที่เลือก และรายการคาบที่ยังจัดไม่ได้
   - **ผังห้องกับเวลา** และ **คาบที่ไม่มีห้อง**
   - **Heatmap การใช้ Lab**: แถวเป็นห้อง Lab คอลัมน์เป็นสัปดาห์ ตัวเลขคือชั่วโมงจำเป็น `+ไม่จำเป็น` ผลรวมชั่วโมงไม่จำเป็นต้องเท่ากับ `unnecessary_lab_hours` ของรันนั้น
   - **ห้องของแต่ละคลาส**: ค้นหาหรือเลือกคลาส เห็นห้องของทั้ง 15 สัปดาห์ต่อคาบประจำ เน้นสัปดาห์ที่เปลี่ยนห้อง สัปดาห์ที่ต้องใช้ Lab และการใช้ Lab โดยไม่จำเป็น ผลรวมการเปลี่ยนห้องของทุกคลาสเท่ากับ `room_changes`
   - นับแบบเดียวกับ `engine/solution_validator.py`: ชั่วโมง Lab ไม่จำเป็น = `duration_minutes` ของคาบที่อยู่ใน Computer Lab ในสัปดาห์ที่ไม่อยู่ใน `lab_weeks`; เปลี่ยนห้อง = ห้องต่างจากสัปดาห์ก่อนหน้าที่จัดได้ของคาบเดียวกัน

ดาวน์โหลด **CSV** สำหรับวิเคราะห์ได้ (ผลแต่ละรัน, ตาราง **ตามห้อง** หรือ **ตามคลาส** ซึ่งรวมสัปดาห์ที่ยังจัดไม่ได้ด้วย ทุกไฟล์เป็น UTF-8 มี BOM จึงเปิดภาษาไทยใน Excel ได้) และ **ชุดผล JSON** สำหรับสำรองหรือส่งให้คนอื่นตรวจ JSON รวมข้อมูลนำเข้า โค้ด engine ที่ใช้จริง พารามิเตอร์ trace คำตอบ และผลตรวจ

ผลที่นำเข้าถูกเก็บใน **IndexedDB ของเบราว์เซอร์และ origin ปัจจุบัน** การล้างข้อมูลเว็บ เปลี่ยนเบราว์เซอร์ ใช้โหมดส่วนตัว หรือเปลี่ยนจาก localhost เป็น GitHub Pages จะไม่เห็นรายการชุดเดียวกัน ผลไม่ได้อัปโหลดขึ้นที่ใด

การทำผลใหม่ใช้ CLI ของ engine C# ([dotnet/README.md](../dotnet/README.md)) แล้วเปิด `experiment.json.gz` ในหน้าผลที่เก็บไว้ อย่าสรุปผู้ชนะจากรันเดียว ผลที่รายงานใช้ 30 seeds ตาม [protocol](protocol.md)

## ข้อมูลและขอบเขต

- แหล่งต้นฉบับ: [UniTime university course timetabling datasets](https://www.unitime.org/uct_datasets.php), Purdue Fall 2007 CS (`pu-fal07-cs`)
- ข้อมูลที่ใช้เป็น **adapted synthetic benchmark** ไม่ใช่ข้อมูลจริงของมหาวิทยาลัยไทย และใช้คะแนนคนละแบบกับ benchmark ต้นฉบับ
- 174 คลาส, 223 recurring sessions, 15 สัปดาห์ รวม 3,345 weekly sessions
- ห้องบรรยาย 13 ห้อง + Computer Lab จำลอง 4 ห้อง (61, 36, 30, 26 ที่นั่ง)
- **ความต้องการ Lab สร้างขึ้นเอง (assumption A10)** กำหนดเป็นรายวิชาและตกที่คาบปฏิบัติของวิชาเท่านั้น
  - ต้นฉบับบอกส่วนของวิชา (subpart) แต่ไม่บอกว่าส่วนไหนเป็นงานปฏิบัติ คาบปฏิบัติจึงเป็น **การอนุมานจากรูปแบบเวลาเรียน ไม่ใช่ข้อมูลจากต้นฉบับ**: วิชาที่มีหลายส่วนใช้ส่วนที่คาบยาวที่สุด ถ้าเท่ากันเลือกส่วนที่เรียนน้อยครั้งต่อสัปดาห์ แล้วส่วนที่มีกลุ่มเรียนมากกว่า แล้วรหัส subpart มากกว่า ส่วนวิชาที่มีส่วนเดียวนับเป็นคาบปฏิบัติเฉพาะเมื่อเรียนสัปดาห์ละครั้ง นอกนั้นเป็นวิชาบรรยาย ไม่ใช้ Lab เลย
  - 27 จาก 44 วิชามีคาบปฏิบัติ สับลำดับด้วย seed แล้วหยิบตามลำดับจนชั่วโมง Lab ทั้งเทอมใกล้เป้าใน config (804 ชั่วโมง) ที่สุด ได้ **วิชา Lab 20 วิชา** รวม 106 จาก 223 recurring sessions (อีก 117 ไม่ใช้ Lab เลย)
  - ทุกกลุ่มเรียนในคาบปฏิบัติของวิชาเดียวกันใช้ Lab 4 จาก 15 สัปดาห์ชุดเดียวกัน รวม 424 weekly lab sessions หรือ 800 ชั่วโมงต่อเทอม ความต้องการต่อสัปดาห์อยู่ระหว่าง 9 ถึง 89 ชั่วโมง
  - แต่ละวิชา Lab มีลำดับสุ่มของ 15 สัปดาห์เก็บใน `generator.lab_plan` ชุดหลักใช้ 4 สัปดาห์แรก ชุดแปรระดับ n ใช้ n สัปดาห์แรก
- Seed สร้างข้อมูล `20261119` แยกจาก seed ค้นหาคำตอบ โค้ดอยู่ใน `dataset_tools/build_dataset.py` (ฟังก์ชัน `plan_labs`)
- ผู้สอนที่ไม่มีในต้นฉบับ 143 คลาสใช้ synthetic instructor แยกคลาส เป็นสมมติฐาน ไม่ได้อนุมานว่าผู้สอนจริงไม่ซ้ำกัน
- ล็อก background classes 810 คลาสเพื่อรักษาการใช้ห้อง ผู้สอน และ explicit distribution rules
- กรณีหลักใช้ student non-overlap ระหว่าง target CS classes ส่วนความชนกับนักศึกษาของ background ไม่ถือเป็นข้อห้ามทั่วไป (`external_student_overlap_is_hard=false`); explicit source non-overlap rules ยังคงบังคับ
- ชุดแปรใน `data/variants/`: จำนวนสัปดาห์ Lab 1 ถึง 15 (`fall-cs-labweeks-w01` ถึง `w15`), Lab 3 และ 2 ห้อง (`fall-cs-labs3`, `labs2`) และสัปดาห์ Lab แบบติดกันหรือเว้นสัปดาห์ (`fall-cs-pattern-*`)
- ไม่คิดเวลาเดินระหว่างห้อง ไม่ตีความ source room preferences เป็น hard constraint เพิ่มเอง และไม่ใช้คะแนน preference ดั้งเดิมเป็นคะแนนโครงงาน

รายละเอียดใน [assumptions.json](../data/assumptions.json), [FORMAT.txt](../data/FORMAT.txt), [START_HERE.txt](../data/START_HERE.txt), [conversion_audit.json](../data/conversion_audit.json) และ [provenance.json](../data/provenance.json)

Dataset id `pu-fal07-cs-weekly-lab-v2` (Fall CS Weekly Labs v2), JSON SHA-256: `dcb93db81f2bd60f1ff53bdb8b6c20899c9642489336580a9b209aa74495ee61`

## วิธีแทนคำตอบและวิธีค้นหา

ทั้งสี่วิธีใช้ **indirect encoding และ constructive decoder เดียวกัน**: คำตอบค้นหาเป็นลำดับความสำคัญของคลาสและ preferred source time option ของแต่ละคลาส Decoder ทดลองตัวเลือกวัน/เวลาที่ต้นฉบับอนุญาต เลือก recurring day/time/duration ชุดเดียวตลอดภาค แต่เปลี่ยนห้องได้ตามสัปดาห์ (โหมด `weekly` ค่าเริ่มต้น; โหมด `fixed` ดูหัวข้อถัดไป)

Decoder รักษาข้อห้ามระหว่างจัด หากไม่มีตำแหน่งที่ผ่าน จะเว้น weekly session นั้นและคิดเป็น unassigned คำตอบจึงอาจเป็น **feasible partial timetable**: ไม่มีข้อห้ามที่ละเมิด แต่ยังมีคาบตกค้าง ไม่ควรเรียกว่าจัดได้ครบจนกว่า unassigned=0

- **Greedy:** เริ่มจากคลาสที่มี static placements และ time options น้อยก่อน แล้วใช้ conflict degree เป็นตัวตัดสินร่วม ประเมินครั้งเดียวแล้วจบ เป็น deterministic baseline
- **HC:** สลับลำดับคลาสและเปลี่ยน preferred time option ยอมรับเฉพาะคำตอบที่ดีขึ้น เริ่มใหม่แบบสุ่มเมื่อไม่ดีขึ้นครบ patience คำตอบสุดท้ายเป็น best-so-far
- **SA:** ใช้เพื่อนบ้านแบบเดียวกับ HC แต่ยอมรับคำตอบแย่ลงด้วยความน่าจะเป็นตามอุณหภูมิ ใช้ calibration ไม่เกิน 8 evaluations เพื่อประมาณ initial temperature จาก uphill delta แล้วค่อยลดอุณหภูมิ
- **GA:** ประชากรของ priority/time-preference genomes, tournament selection, ordered crossover ของ permutation, ผสม time preference รายคลาส, mutation แบบเดียวกับ HC และ elitism ใช้ decoder ร่วมซ่อมข้อจำกัดเชิงการจัดห้อง

ค่าเริ่มต้นในโค้ด engine C# (ใช้เมื่อไม่ส่งพารามิเตอร์): HC patience=20; SA initial acceptance=.8, cooling=.97; GA population=12, tournament=3, elites=1, crossover=.9, mutation=.3

ค่าที่จูนแล้ว (`experiments/tuning/selected-parameters.json`): HC patience=200; SA เท่ากับค่าเริ่มต้น (.8 / .97); GA population=12, tournament=4, elites=3, crossover=.85, mutation=.86

นี่คือการเปรียบเทียบวิธีค้นหาบน representation และ decoder นี้ ไม่ใช่การพิสูจน์ว่า implementation นี้แทนทุกวิธีแก้ course timetabling หรือค้นหาตารางทุกแบบได้ Neighborhood เปลี่ยน priority/time preference ไม่ได้ย้ายห้องรายสัปดาห์โดยตรง จึงมีข้อจำกัดของ search space

ที่มาของแต่ละการตัดสินใจเทียบกับงานวิจัยที่อ้างอิง และเหตุผลที่เทียบตัวเลขตรงกับ paper ไม่ได้: [docs/research-comparison.md](research-comparison.md)

## โหมดจัดห้อง: รายสัปดาห์ (weekly) กับ ห้องคงที่ (fixed)

มีโหมดเปรียบเทียบที่ใช้ genome, decoder, ตัวตรวจ และ metric ชุดเดียวกัน ต่างกันเฉพาะกติกาเลือกห้อง ใช้เป็นจุดอ้างอิงว่าโจทย์เดียวกันเป็นอย่างไรเมื่อห้องเปลี่ยนรายสัปดาห์ไม่ได้ ผลที่โหมด fixed ใช้ Lab มากกว่าเป็นไปตามนิยามของโหมด ไม่ใช่ข้อค้นพบเกี่ยวกับมหาวิทยาลัยจริง

- **`weekly` (ค่าเริ่มต้น):** วันเวลาคงที่ทั้งเทอม ห้องเปลี่ยนได้รายสัปดาห์ จึงใช้ Lab เฉพาะสัปดาห์ที่ต้องใช้ได้
- **`fixed`:** แต่ละ recurring session จองห้องเดียวทุกสัปดาห์ที่จัดได้ ถ้ามีสัปดาห์ใดต้องใช้ Lab ห้องนั้นต้องเป็น Computer Lab ทั้งเทอม Decoder เลือกห้องที่จัดได้มากสัปดาห์ที่สุดก่อน ถ้าห้องนั้นไม่ว่างบางสัปดาห์ สัปดาห์นั้นนับเป็น unassigned แทนการย้ายห้อง
- ตัวตรวจอิสระรับโหมดจาก config ของรัน (ไม่เชื่อค่าที่คำตอบประกาศเอง) ในโหมด `fixed` จะเพิ่มข้อห้าม `FIXED_ROOM_CHANGED` (คาบเดียวกันใช้มากกว่าหนึ่งห้อง) และ `FIXED_ROOM_NOT_LAB` (คาบที่มีสัปดาห์ Lab แต่จองห้องที่ไม่ใช่ Lab) และ `ROOM_MODE` เมื่อโหมดที่คำตอบประกาศไม่ตรงกับที่ตรวจ
- รายงาน metric เดียวกันทั้งสองโหมด: คาบที่ยังจัดไม่ได้ / ชั่วโมง Lab ที่ไม่จำเป็น / จำนวนครั้งเปลี่ยนห้อง (โหมด fixed เป็น 0 เสมอ) ทุกรันบันทึก `room_mode`
- เว็บ: ไฟล์ผลที่มีทั้งสองโหมดเปิดในเว็บได้ และแยกแถวสรุปตามโหมด
- CLI: `--room-modes weekly fixed` รันทั้งสองโหมดบน seed ชุดเดียวกันใน batch เดียว ตารางเทียบแบบจับคู่ (fixed − weekly ต่อ seed) อยู่ในรายงานที่ `engine/analyze.py` สร้าง

ผลเทียบสองโหมดอยู่ใน [experiments/final/analysis/report.md](../experiments/final/analysis/report.md)

## ข้อห้ามและเป้าหมายร่วม

ตัวตรวจคำตอบ (`SolutionValidator` ใน C# และ `engine/solution_validator.py` ซึ่งใช้กติกาเดียวกัน) ตรวจจากข้อมูลดิบอิสระจาก bitmask/cache ของตัวค้นหา:

- อ้างอิงคลาส/คาบ/ห้อง/สัปดาห์และ source time option ถูกต้อง ไม่ซ้ำ session-week
- วันเวลาและระยะเวลาของ recurring session คงที่ตาม option ที่เลือก
- ห้องใน domain ที่อนุญาต ความจุพอ ประเภท Lab ถูกต้อง และเปิดให้ใช้เต็มช่วงเวลา
- ห้อง ผู้สอน นักศึกษา และ explicit non-overlap groups ไม่ชนกัน รวม background ตาม policy ของข้อมูล
- SAME_TIME ใช้การครอบช่วงเวลาของคาบสั้นในคาบยาวตามข้อมูล ไม่ได้แปลว่าต้องเริ่มเวลาเดียวกันเสมอ

Source constraint ID บางรายการซ้ำกัน (ID 90 ของ SAME_STUDENTS หลายกลุ่ม) จึงใช้แต่ละ array entry เป็น constraint คนละตัว ไม่รวมเป็นกลุ่มใหญ่ตาม ID

เป้าหมายเทียบแบบ **lexicographic** ตามลำดับ:

1. `unassigned_weekly_sessions` น้อยที่สุด
2. เมื่อข้อแรกเท่ากัน ลด `unnecessary_lab_minutes` (สัปดาห์ที่ไม่ต้องใช้ Lab แต่ไปใช้ห้อง Lab)
3. เมื่อสองข้อแรกเท่ากัน ลด `room_changes` ระหว่างสัปดาห์ที่จัดได้ของ recurring session เดียวกัน (ข้ามสัปดาห์ที่ยังจัดไม่ได้)

SA ใช้ scalar energy ที่รักษาลำดับนี้อย่างเคร่งครัด: `Wc=1`, `Wm=Cmax+1`, `Wu=(Mmax+1)*Wm`; `Cmax` คือเพดาน room changes และ `Mmax` คือเวลารวมทุก weekly session ทั้งคู่คำนวณจาก dataset ปัจจุบัน ไม่ใช่น้ำหนักสุ่มที่ปรับเพื่อให้วิธีใดชนะ

## ความเท่าเทียมและการอ่านผล

- ทุกวิธีได้ initial genome เดียวกัน งบเดียวกัน ข้อมูล/ข้อจำกัด/คะแนน/validator เดียวกัน
- นับหนึ่ง evaluation เมื่อ decode และคิดคะแนน candidate เต็มชุดสำเร็จ รวม initialization, SA calibration และ GA initial population; บันทึก attempted evaluations แยกเมื่อถูกตัดกลางทาง
- Greedy ใช้เพียงหนึ่ง evaluation เพราะไม่มี search loop การรันหลาย seed ให้ผลเดิม ไม่ควรตีความเป็น independent stochastic samples
- หยุดเมื่อครบงบหรือเวลาก่อน คำตอบแรกอนุญาตให้ decode จบเพื่อให้มี baseline แม้เกิน cap เล็กน้อย หลังจากนั้นตรวจ deadline ระหว่างคลาส
- preprocessing แยกจาก search time; final independent validation time บันทึกแยก เวลาขึ้นกับเครื่องและจำนวน process ที่รันพร้อมกัน ไม่ใช้เทียบข้ามเครื่องตรง ๆ
- หาก time limit ตัดก่อนงบเท่ากัน ต้องรายงาน evaluations ที่ใช้จริง ควรเพิ่ม cap เมื่อต้องการเทียบด้วย fixed evaluation budget
- วิธีถูกรันเรียงตาม seed แล้วตามวิธี ไม่สลับลำดับแบบสุ่ม จึงอาจมีผลของ warm-up/สภาวะเครื่องต่อเวลา
- มีสถานะ completed / evaluation_budget / time_limit / invalid_solution / error / worker_timeout / cancelled เก็บแถวที่ล้มเหลวด้วย ไม่แทนผลที่ไม่มีด้วยศูนย์
- เฉพาะคำตอบที่ตรวจผ่านและไม่ error จึงเข้าตารางสรุปแยกตามวิธี Summary เรียง median unassigned → median lab minutes → median room changes เป็น descriptive summary ไม่ใช่ statistical test หรือคำตอบจริงหนึ่งตาราง ค่า Lab แสดง mean ± sample SD
- กราฟแสดง best-so-far ตาม lexicographic comparator; ค่า Lab หรือ room changes อาจเพิ่มเมื่อ unassigned ลดลงได้
- ตารางสรุปในเว็บเป็นค่าพรรณนา ไม่ได้ทำ significance tests สถิติของการทดลองสุดท้ายมาจาก `engine/analyze.py` และ seed จูนกับ seed ทดสอบแยกกันตาม [protocol](protocol.md)

## engine C# และเครื่องมือ Python

- **ตัวแก้ปัญหามีตัวเดียวคือ engine C# ใน `dotnet/`** (decoder, อัลกอริทึมทั้งสี่, ตัวตรวจ และ CLI) ผลทดลองที่ commit ไว้ทั้งหมดมาจาก engine นี้ และแอป Godot ใช้ engine เดียวกัน คำสั่งอยู่ใน [dotnet/README.md](../dotnet/README.md)
- **`engine/` เหลือเครื่องมือ Python** ไม่มีตัวแก้ปัญหา: `analyze.py` (สถิติและรายงาน), `tune.py` (จูน โดยสั่ง CLI ของ C#), `input_validation.py` (ตรวจชุดข้อมูล ใช้โดย `dataset_tools/`) และ `solution_validator.py` (ตัวตรวจคำตอบ ใช้สร้าง fixture ของ tests C#)
- ก่อนลบตัวแก้ปัญหาภาษา Python ออกจาก repo ได้รัน 16 รันของการทดลองสุดท้าย (4 วิธี × 2 โหมดห้อง × seed 1001–1002) ด้วยตัวนั้นบนชุดข้อมูลใหม่ ได้ metric ตารางคำตอบ และ trace ตรงกับผลของ C# ทุกรัน การตรวจนี้ทำซ้ำจากโค้ดปัจจุบันไม่ได้แล้ว ตัวแก้ปัญหาภาษา Python อยู่ใน git history เท่านั้น (มีอยู่ครั้งสุดท้ายที่ commit 6d33611 บน main)
- คอมเมนต์ในซอร์ส C# ที่เขียนว่า port of `engine/...py` เป็นบันทึกที่มาของโค้ด ไฟล์ Python เหล่านั้นไม่อยู่ใน repo แล้ว
- เว็บไม่มีแท็บโค้ด Python และไม่มีวิธี `custom` ให้เขียนอัลกอริทึมเองแล้ว

## รันบนเครื่องและทดสอบ

เว็บไม่มี frontend build และไม่มี backend:

```sh
python -m http.server 8766 --bind 127.0.0.1
```

รันจาก root ของโครงการ แล้วเปิด `http://127.0.0.1:8766/apps/web/` (หน้า root จะ redirect ไปให้เอง) เว็บโหลด `data/` และ `experiments/` ด้วย path สัมพัทธ์ จึงต้องเสิร์ฟจาก root ไม่ใช่จาก `apps/web/` อย่าเปิด `index.html` แบบ file:// เพราะ fetch ต้องใช้ HTTP(S)

รันการทดลองด้วย engine C# (ต้องมี .NET 8 SDK):

```sh
dotnet build -c Release dotnet/src/Timetabling.Cli
dotnet run -c Release --no-build --project dotnet/src/Timetabling.Cli -- batch run --methods greedy hc sa ga \
  --room-modes weekly fixed --seeds 1001-1030 --budget 500 --seconds 3600 \
  --parameters experiments/tuning/selected-parameters.json --output results/final
python engine/analyze.py results/final/experiment.json.gz --output results/final/analysis
```

`batch run` รันหลาย process พร้อมกัน เก็บผลทีละรันใน `<output>/runs/` และถ้าหยุดกลางทาง ให้รันคำสั่งเดิมซ้ำเพื่อทำต่อโดยข้ามรันที่เสร็จแล้ว เมื่อครบจะรวมเป็น `experiment.json.gz` (เปิดในเว็บได้) กับ `experiment.csv` Seed เดียวกันจะทำซ้ำได้เมื่อใช้ dataset, โค้ด engine และพารามิเตอร์เดียวกัน และไม่ถูกตัดด้วยเวลาระหว่างทาง กติกาการทดลองสุดท้าย (seed จูนและทดสอบ งบ และสถิติ) อยู่ใน [docs/protocol.md](protocol.md)

ทดสอบ:

```sh
python -m unittest discover -s engine/tests -v
dotnet test dotnet/Timetabling.sln --filter "Category!=Slow"
```

## สร้าง adapted dataset ซ้ำ

มี converter และ config เดิมใน `dataset_tools/` สร้างลงโฟลเดอร์ใหม่และตรวจ SHA-256 ให้ตรงกับ `data/provenance.json`:

```sh
python dataset_tools/rebuild.py --output results/rebuilt-dataset
```

คำสั่งนี้ดาวน์โหลด source ZIP จาก UniTime ตาม URL ที่ตรึงไว้ หากมี XML อยู่แล้วใช้ `--source-xml /path/to/pu-fal07-cs.xml` ได้ ไม่แก้ XML ต้นฉบับและไม่เขียนทับ output ที่มีอยู่ `data/START_HERE.txt` เป็นบันทึกจากแพ็กเกจ conversion เดิม คำสั่งในเอกสารนั้นอ้างถึงโครงสร้างแพ็กเกจเดิม ให้ใช้คำสั่งข้างบนใน repo นี้

## โครงสร้างและการเผยแพร่

แผนที่ไฟล์ทั้งหมดอยู่ใน [docs/INDEX.md](INDEX.md) และผลทดลองทุกชุดสรุปไว้ใน [experiments/INDEX.md](../experiments/INDEX.md)

```
apps/web/        เว็บดูผล (index.html, app.mjs, storage.mjs, styles.css) ไม่รันอัลกอริทึม
apps/slides/     สไลด์นำเสนอ deck เดียว deploy บน Vercel
apps/godot/      แอปเดสก์ท็อป Godot (C#): แผนที่ห้องรายสัปดาห์, รันสด, เทียบ weekly/fixed
engine/          เครื่องมือ Python: analyze.py, tune.py, input_validation.py, solution_validator.py
engine/tests/    tests ของเครื่องมือวิเคราะห์และชุดข้อมูล (19 รายการ)
dotnet/          C# engine ตัวแก้ปัญหาตัวเดียวของ repo + CLI "timetabling" + tests
data/            ชุดข้อมูลดัดแปลง, assumptions, provenance, variants/
dataset_tools/   converter และ config ที่ใช้สร้าง data/ ซ้ำ
experiments/     ผลดิบที่ commit ไว้เป็นหลักฐาน (JSON.gz + CSV + summary)
docs/            คู่มือ, protocol, research comparison, QA
index.html       redirect ไป apps/web/ เพื่อให้ URL ของ GitHub Pages เดิมใช้ได้
```

- `engine/input_validation.py`, `solution_validator.py`: ตัวตรวจ input และ output ภาษา Python คนละหน้าที่ (ตัวตรวจที่ใช้ตอนรันจริงอยู่ใน C#)
- `engine/analyze.py`, `tune.py`: รายงานสถิติ และการจูนที่สั่ง CLI ของ C#
- `dotnet/`: decoder อัลกอริทึม ตัวตรวจ และ CLI รายละเอียดและคำสั่งอยู่ใน [dotnet/README.md](../dotnet/README.md); แอป Godot อยู่ใน [apps/godot/README.md](../apps/godot/README.md)

`dataset_tools/` อยู่ที่ root ตั้งใจ: `config.json` อ้าง XML ต้นทางแบบ path สัมพัทธ์ และ config นี้ถูกบันทึกลงในชุดข้อมูล การย้ายจะทำให้ SHA-256 ของชุดข้อมูลที่สร้างซ้ำไม่ตรงกับ `data/provenance.json`

Deploy GitHub Pages จาก `main` ที่ `/ (root)` ได้โดยตรง (root `index.html` redirect ไป `apps/web/`) มี `.nojekyll` ไม่ต้องเปิดเผย credentials หรือใช้ server เว็บเป็นที่ดูผลการทดลองเพื่อการศึกษา ไม่ใช่ระบบจัดตารางใช้งานจริงของสถาบัน

ดู [NOTICE](../NOTICE) สำหรับสิทธิ์แยกระหว่างโค้ดกับข้อมูลต้นทาง
