# ผลการจูน (seed 1–10, weekly, งบ 500)

สร้างโดย `engine/tune.py` ห้ามแก้มือ ตัวเลขเป็นค่าเฉลี่ยบน 10 seed จูน

## ค่าเริ่มต้นเทียบกับค่าที่เลือก

| วิธี | ชุดค่า | พารามิเตอร์ | คาบที่ยังจัดไม่ได้ | Lab ไม่จำเป็น (ชม.) | เปลี่ยนห้อง | จัดครบทุกคาบ |
|---|---|---|---:|---:|---:|---:|
| Hill Climbing | ค่าเริ่มต้น | `{"restart_patience": 20}` | 0.30 | 150.2 | 613.4 | 90% |
| Hill Climbing | **ที่เลือก** | `{"restart_patience": 200}` | 0.00 | 174.6 | 624.9 | 100% |
| Simulated Annealing | ค่าเริ่มต้น | `{"cooling_rate": 0.97, "initial_acceptance": 0.8}` | 0.00 | 123.3 | 618.3 | 100% |
| Simulated Annealing | **ที่เลือก** | `{"cooling_rate": 0.97, "initial_acceptance": 0.8}` | 0.00 | 123.3 | 618.3 | 100% |
| Genetic Algorithm | ค่าเริ่มต้น | `{"crossover_rate": 0.9, "elites": 1, "mutation_rate": 0.3, "population_size": 12, "tournament_size": 3}` | 0.20 | 167.2 | 618.7 | 80% |
| Genetic Algorithm | **ที่เลือก** | `{"crossover_rate": 0.85, "elites": 3, "mutation_rate": 0.86, "population_size": 12, "tournament_size": 4}` | 0.00 | 102.5 | 613.5 | 100% |

## ทุกชุดค่าที่ลอง (เรียงจากดีไปแย่ในแต่ละวิธี)

| ชุดค่า | พารามิเตอร์ | รันที่ใช้ได้ | คาบที่ยังจัดไม่ได้ | Lab ไม่จำเป็น (ชม.) | เปลี่ยนห้อง | จัดครบ | วินาที/รัน |
|---|---|---:|---:|---:|---:|---:|---:|
| hc-p200 | `{"restart_patience": 200}` | 10/10 | 0.00 | 174.6 | 624.9 | 100% | 1.4 |
| hc-p500 | `{"restart_patience": 500}` | 10/10 | 0.00 | 174.6 | 624.9 | 100% | 1.4 |
| hc-p50 | `{"restart_patience": 50}` | 10/10 | 0.10 | 151.6 | 613.3 | 90% | 1.1 |
| hc-p10 | `{"restart_patience": 10}` | 10/10 | 0.10 | 187.8 | 627.0 | 90% | 1.1 |
| hc-p100 | `{"restart_patience": 100}` | 10/10 | 0.20 | 165.5 | 623.8 | 90% | 1.0 |
| hc-p5 | `{"restart_patience": 5}` | 10/10 | 0.20 | 171.1 | 623.5 | 80% | 1.1 |
| hc-p20 (ค่าเริ่มต้น) | `{"restart_patience": 20}` | 10/10 | 0.30 | 150.2 | 613.4 | 90% | 1.2 |
| sa-a0.8-c0.97 (ค่าเริ่มต้น) | `{"cooling_rate": 0.97, "initial_acceptance": 0.8}` | 10/10 | 0.00 | 123.3 | 618.3 | 100% | 1.6 |
| sa-a0.05-c0.97 | `{"cooling_rate": 0.97, "initial_acceptance": 0.05}` | 10/10 | 0.00 | 128.8 | 618.3 | 100% | 1.6 |
| sa-a0.5-c0.97 | `{"cooling_rate": 0.97, "initial_acceptance": 0.5}` | 10/10 | 0.00 | 130.1 | 618.8 | 100% | 1.6 |
| sa-a0.95-c0.8 | `{"cooling_rate": 0.8, "initial_acceptance": 0.95}` | 10/10 | 0.00 | 130.6 | 617.3 | 100% | 1.4 |
| sa-a0.95-c0.97 | `{"cooling_rate": 0.97, "initial_acceptance": 0.95}` | 10/10 | 0.00 | 138.0 | 618.9 | 100% | 1.6 |
| sa-a0.8-c0.9 | `{"cooling_rate": 0.9, "initial_acceptance": 0.8}` | 10/10 | 0.00 | 138.8 | 622.0 | 100% | 1.5 |
| sa-a0.95-c0.9 | `{"cooling_rate": 0.9, "initial_acceptance": 0.95}` | 10/10 | 0.00 | 140.1 | 617.5 | 100% | 1.5 |
| sa-a0.01-c0.97 | `{"cooling_rate": 0.97, "initial_acceptance": 0.01}` | 10/10 | 0.00 | 140.9 | 618.8 | 100% | 1.5 |
| sa-a0.95-c0.99 | `{"cooling_rate": 0.99, "initial_acceptance": 0.95}` | 10/10 | 0.00 | 145.2 | 621.0 | 100% | 1.5 |
| sa-a0.8-c0.8 | `{"cooling_rate": 0.8, "initial_acceptance": 0.8}` | 10/10 | 0.00 | 149.6 | 614.8 | 100% | 1.6 |
| sa-a0.01-c0.8 | `{"cooling_rate": 0.8, "initial_acceptance": 0.01}` | 10/10 | 0.00 | 149.7 | 616.3 | 100% | 1.5 |
| sa-a0.5-c0.9 | `{"cooling_rate": 0.9, "initial_acceptance": 0.5}` | 10/10 | 0.00 | 151.6 | 619.3 | 100% | 1.8 |
| sa-a0.2-c0.8 | `{"cooling_rate": 0.8, "initial_acceptance": 0.2}` | 10/10 | 0.00 | 152.7 | 616.2 | 100% | 1.9 |
| sa-a0.2-c0.99 | `{"cooling_rate": 0.99, "initial_acceptance": 0.2}` | 10/10 | 0.00 | 153.0 | 624.9 | 100% | 1.5 |
| sa-a0.2-c0.9 | `{"cooling_rate": 0.9, "initial_acceptance": 0.2}` | 10/10 | 0.00 | 154.7 | 619.4 | 100% | 1.6 |
| sa-a0.01-c0.9 | `{"cooling_rate": 0.9, "initial_acceptance": 0.01}` | 10/10 | 0.00 | 156.3 | 624.7 | 100% | 1.5 |
| sa-a0.8-c0.99 | `{"cooling_rate": 0.99, "initial_acceptance": 0.8}` | 10/10 | 0.00 | 157.0 | 623.1 | 100% | 1.5 |
| sa-a0.05-c0.9 | `{"cooling_rate": 0.9, "initial_acceptance": 0.05}` | 10/10 | 0.00 | 157.9 | 621.5 | 100% | 1.6 |
| sa-a0.01-c0.99 | `{"cooling_rate": 0.99, "initial_acceptance": 0.01}` | 10/10 | 0.00 | 158.1 | 624.5 | 100% | 1.6 |
| sa-a0.5-c0.8 | `{"cooling_rate": 0.8, "initial_acceptance": 0.5}` | 10/10 | 0.00 | 159.4 | 616.6 | 100% | 1.6 |
| sa-a0.05-c0.8 | `{"cooling_rate": 0.8, "initial_acceptance": 0.05}` | 10/10 | 0.00 | 161.0 | 617.6 | 100% | 1.7 |
| sa-a0.5-c0.99 | `{"cooling_rate": 0.99, "initial_acceptance": 0.5}` | 10/10 | 0.00 | 163.9 | 622.3 | 100% | 1.5 |
| sa-a0.05-c0.99 | `{"cooling_rate": 0.99, "initial_acceptance": 0.05}` | 10/10 | 0.00 | 165.2 | 625.7 | 100% | 1.7 |
| sa-a0.2-c0.97 | `{"cooling_rate": 0.97, "initial_acceptance": 0.2}` | 10/10 | 0.10 | 139.5 | 620.7 | 90% | 1.6 |
| ga-15 | `{"crossover_rate": 0.85, "elites": 3, "mutation_rate": 0.86, "population_size": 12, "tournament_size": 4}` | 10/10 | 0.00 | 102.5 | 613.5 | 100% | 1.6 |
| ga-14 | `{"crossover_rate": 0.66, "elites": 2, "mutation_rate": 0.77, "population_size": 33, "tournament_size": 3}` | 10/10 | 0.00 | 117.4 | 619.3 | 100% | 1.7 |
| ga-13 | `{"crossover_rate": 0.72, "elites": 2, "mutation_rate": 0.67, "population_size": 18, "tournament_size": 3}` | 10/10 | 0.00 | 131.5 | 612.1 | 100% | 1.8 |
| ga-16 | `{"crossover_rate": 0.97, "elites": 2, "mutation_rate": 0.21, "population_size": 21, "tournament_size": 4}` | 10/10 | 0.00 | 133.9 | 613.9 | 100% | 1.6 |
| ga-04 | `{"crossover_rate": 0.96, "elites": 2, "mutation_rate": 0.29, "population_size": 22, "tournament_size": 4}` | 10/10 | 0.00 | 134.2 | 618.0 | 100% | 1.7 |
| ga-11 | `{"crossover_rate": 0.64, "elites": 3, "mutation_rate": 0.66, "population_size": 35, "tournament_size": 5}` | 10/10 | 0.00 | 136.2 | 615.6 | 100% | 1.7 |
| ga-09 | `{"crossover_rate": 0.72, "elites": 1, "mutation_rate": 0.64, "population_size": 33, "tournament_size": 3}` | 10/10 | 0.00 | 140.8 | 620.9 | 100% | 1.7 |
| ga-03 | `{"crossover_rate": 0.68, "elites": 1, "mutation_rate": 0.57, "population_size": 20, "tournament_size": 3}` | 10/10 | 0.00 | 141.7 | 613.4 | 100% | 1.5 |
| ga-08 | `{"crossover_rate": 0.94, "elites": 2, "mutation_rate": 0.62, "population_size": 24, "tournament_size": 3}` | 10/10 | 0.00 | 143.2 | 621.1 | 100% | 1.7 |
| ga-07 | `{"crossover_rate": 0.97, "elites": 1, "mutation_rate": 0.35, "population_size": 36, "tournament_size": 4}` | 10/10 | 0.00 | 145.7 | 621.9 | 100% | 1.8 |
| ga-06 | `{"crossover_rate": 0.75, "elites": 1, "mutation_rate": 0.7, "population_size": 27, "tournament_size": 3}` | 10/10 | 0.00 | 148.2 | 625.8 | 100% | 1.8 |
| ga-05 | `{"crossover_rate": 0.64, "elites": 1, "mutation_rate": 0.25, "population_size": 18, "tournament_size": 4}` | 10/10 | 0.00 | 158.2 | 617.1 | 100% | 1.7 |
| ga-12 | `{"crossover_rate": 0.84, "elites": 2, "mutation_rate": 0.23, "population_size": 27, "tournament_size": 2}` | 10/10 | 0.00 | 160.1 | 617.9 | 100% | 1.7 |
| ga-19 | `{"crossover_rate": 0.93, "elites": 2, "mutation_rate": 0.88, "population_size": 32, "tournament_size": 2}` | 10/10 | 0.00 | 177.4 | 619.8 | 100% | 1.6 |
| ga-10 | `{"crossover_rate": 0.9, "elites": 1, "mutation_rate": 0.33, "population_size": 25, "tournament_size": 2}` | 10/10 | 0.00 | 183.1 | 632.9 | 100% | 1.7 |
| ga-01 | `{"crossover_rate": 0.86, "elites": 1, "mutation_rate": 0.37, "population_size": 21, "tournament_size": 5}` | 10/10 | 0.10 | 143.0 | 615.0 | 90% | 1.6 |
| ga-18 | `{"crossover_rate": 0.64, "elites": 3, "mutation_rate": 0.12, "population_size": 26, "tournament_size": 3}` | 10/10 | 0.10 | 182.4 | 624.8 | 90% | 1.6 |
| ga-00 (ค่าเริ่มต้น) | `{"crossover_rate": 0.9, "elites": 1, "mutation_rate": 0.3, "population_size": 12, "tournament_size": 3}` | 10/10 | 0.20 | 167.2 | 618.7 | 80% | 1.7 |
| ga-02 | `{"crossover_rate": 0.7, "elites": 1, "mutation_rate": 0.16, "population_size": 11, "tournament_size": 4}` | 10/10 | 0.80 | 212.6 | 630.0 | 70% | 1.6 |
| ga-17 | `{"crossover_rate": 0.85, "elites": 3, "mutation_rate": 0.14, "population_size": 7, "tournament_size": 4}` | 10/10 | 2.20 | 216.6 | 640.7 | 50% | 1.5 |
