# ผลการจูน (seed 1–10, weekly, งบ 500)

สร้างโดย `engine/tune.py` ห้ามแก้มือ ตัวเลขเป็นค่าเฉลี่ยบน 10 seed จูน

## ค่าเริ่มต้นเทียบกับค่าที่เลือก

| วิธี | ชุดค่า | พารามิเตอร์ | คาบที่ยังจัดไม่ได้ | Lab ไม่จำเป็น (ชม.) | เปลี่ยนห้อง | จัดครบทุกคาบ |
|---|---|---|---:|---:|---:|---:|
| Hill Climbing | ค่าเริ่มต้น | `{"restart_patience": 20}` | 0.00 | 72.7 | 830.1 | 100% |
| Hill Climbing | **ที่เลือก** | `{"restart_patience": 50}` | 0.00 | 71.1 | 831.7 | 100% |
| Simulated Annealing | ค่าเริ่มต้น | `{"cooling_rate": 0.97, "initial_acceptance": 0.8}` | 0.00 | 68.9 | 831.9 | 100% |
| Simulated Annealing | **ที่เลือก** | `{"cooling_rate": 0.9, "initial_acceptance": 0.2}` | 0.00 | 58.4 | 837.4 | 100% |
| Genetic Algorithm | ค่าเริ่มต้น | `{"crossover_rate": 0.9, "elites": 1, "mutation_rate": 0.3, "population_size": 12, "tournament_size": 3}` | 0.00 | 76.2 | 839.4 | 100% |
| Genetic Algorithm | **ที่เลือก** | `{"crossover_rate": 0.64, "elites": 3, "mutation_rate": 0.66, "population_size": 35, "tournament_size": 5}` | 0.00 | 55.1 | 824.6 | 100% |

## ทุกชุดค่าที่ลอง (เรียงจากดีไปแย่ในแต่ละวิธี)

| ชุดค่า | พารามิเตอร์ | รันที่ใช้ได้ | คาบที่ยังจัดไม่ได้ | Lab ไม่จำเป็น (ชม.) | เปลี่ยนห้อง | จัดครบ | วินาที/รัน |
|---|---|---:|---:|---:|---:|---:|---:|
| hc-p50 | `{"restart_patience": 50}` | 10/10 | 0.00 | 71.1 | 831.7 | 100% | 218.7 |
| hc-p20 (ค่าเริ่มต้น) | `{"restart_patience": 20}` | 10/10 | 0.00 | 72.7 | 830.1 | 100% | 198.2 |
| hc-p100 | `{"restart_patience": 100}` | 10/10 | 0.00 | 78.8 | 830.7 | 100% | 252.3 |
| hc-p10 | `{"restart_patience": 10}` | 10/10 | 0.00 | 79.2 | 828.1 | 100% | 222.4 |
| hc-p200 | `{"restart_patience": 200}` | 10/10 | 0.00 | 83.2 | 834.5 | 100% | 275.0 |
| hc-p500 | `{"restart_patience": 500}` | 10/10 | 0.00 | 83.7 | 837.6 | 100% | 286.5 |
| hc-p5 | `{"restart_patience": 5}` | 10/10 | 0.00 | 100.3 | 844.0 | 100% | 228.3 |
| sa-a0.2-c0.9 | `{"cooling_rate": 0.9, "initial_acceptance": 0.2}` | 10/10 | 0.00 | 58.4 | 837.4 | 100% | 256.3 |
| sa-a0.2-c0.97 | `{"cooling_rate": 0.97, "initial_acceptance": 0.2}` | 10/10 | 0.00 | 64.3 | 838.8 | 100% | 251.1 |
| sa-a0.8-c0.9 | `{"cooling_rate": 0.9, "initial_acceptance": 0.8}` | 10/10 | 0.00 | 65.1 | 829.0 | 100% | 237.9 |
| sa-a0.95-c0.97 | `{"cooling_rate": 0.97, "initial_acceptance": 0.95}` | 10/10 | 0.00 | 65.7 | 834.4 | 100% | 232.1 |
| sa-a0.8-c0.97 (ค่าเริ่มต้น) | `{"cooling_rate": 0.97, "initial_acceptance": 0.8}` | 10/10 | 0.00 | 68.9 | 831.9 | 100% | 235.0 |
| sa-a0.5-c0.99 | `{"cooling_rate": 0.99, "initial_acceptance": 0.5}` | 10/10 | 0.00 | 75.7 | 840.3 | 100% | 224.7 |
| sa-a0.95-c0.9 | `{"cooling_rate": 0.9, "initial_acceptance": 0.95}` | 10/10 | 0.00 | 75.8 | 838.4 | 100% | 209.7 |
| sa-a0.5-c0.97 | `{"cooling_rate": 0.97, "initial_acceptance": 0.5}` | 10/10 | 0.00 | 80.4 | 850.5 | 100% | 234.5 |
| sa-a0.5-c0.9 | `{"cooling_rate": 0.9, "initial_acceptance": 0.5}` | 10/10 | 0.00 | 84.1 | 832.6 | 100% | 231.7 |
| sa-a0.8-c0.999 | `{"cooling_rate": 0.999, "initial_acceptance": 0.8}` | 10/10 | 0.00 | 85.2 | 834.2 | 100% | 220.2 |
| sa-a0.8-c0.99 | `{"cooling_rate": 0.99, "initial_acceptance": 0.8}` | 10/10 | 0.00 | 87.3 | 835.1 | 100% | 237.1 |
| sa-a0.95-c0.99 | `{"cooling_rate": 0.99, "initial_acceptance": 0.95}` | 10/10 | 0.00 | 87.5 | 840.4 | 100% | 245.0 |
| sa-a0.2-c0.99 | `{"cooling_rate": 0.99, "initial_acceptance": 0.2}` | 10/10 | 0.00 | 89.1 | 842.5 | 100% | 256.7 |
| sa-a0.2-c0.999 | `{"cooling_rate": 0.999, "initial_acceptance": 0.2}` | 10/10 | 0.00 | 89.5 | 846.7 | 100% | 226.3 |
| sa-a0.95-c0.995 | `{"cooling_rate": 0.995, "initial_acceptance": 0.95}` | 10/10 | 0.00 | 97.8 | 841.0 | 100% | 255.1 |
| sa-a0.5-c0.995 | `{"cooling_rate": 0.995, "initial_acceptance": 0.5}` | 10/10 | 0.00 | 99.7 | 842.4 | 100% | 222.8 |
| sa-a0.2-c0.995 | `{"cooling_rate": 0.995, "initial_acceptance": 0.2}` | 10/10 | 0.00 | 99.8 | 850.4 | 100% | 250.8 |
| sa-a0.5-c0.999 | `{"cooling_rate": 0.999, "initial_acceptance": 0.5}` | 10/10 | 0.00 | 103.0 | 838.1 | 100% | 234.2 |
| sa-a0.8-c0.995 | `{"cooling_rate": 0.995, "initial_acceptance": 0.8}` | 10/10 | 0.00 | 107.5 | 844.4 | 100% | 232.1 |
| sa-a0.95-c0.999 | `{"cooling_rate": 0.999, "initial_acceptance": 0.95}` | 10/10 | 0.10 | 116.7 | 835.9 | 90% | 254.1 |
| ga-11 | `{"crossover_rate": 0.64, "elites": 3, "mutation_rate": 0.66, "population_size": 35, "tournament_size": 5}` | 10/10 | 0.00 | 55.1 | 824.6 | 100% | 236.0 |
| ga-08 | `{"crossover_rate": 0.94, "elites": 2, "mutation_rate": 0.62, "population_size": 24, "tournament_size": 3}` | 10/10 | 0.00 | 55.2 | 839.8 | 100% | 184.7 |
| ga-07 | `{"crossover_rate": 0.97, "elites": 1, "mutation_rate": 0.35, "population_size": 36, "tournament_size": 4}` | 10/10 | 0.00 | 57.7 | 839.5 | 100% | 180.4 |
| ga-14 | `{"crossover_rate": 0.66, "elites": 2, "mutation_rate": 0.77, "population_size": 33, "tournament_size": 3}` | 10/10 | 0.00 | 58.4 | 828.9 | 100% | 220.0 |
| ga-09 | `{"crossover_rate": 0.72, "elites": 1, "mutation_rate": 0.64, "population_size": 33, "tournament_size": 3}` | 10/10 | 0.00 | 59.8 | 827.3 | 100% | 204.3 |
| ga-06 | `{"crossover_rate": 0.75, "elites": 1, "mutation_rate": 0.7, "population_size": 27, "tournament_size": 3}` | 10/10 | 0.00 | 60.1 | 829.7 | 100% | 178.0 |
| ga-15 | `{"crossover_rate": 0.85, "elites": 3, "mutation_rate": 0.86, "population_size": 12, "tournament_size": 4}` | 10/10 | 0.00 | 60.9 | 820.5 | 100% | 194.8 |
| ga-01 | `{"crossover_rate": 0.86, "elites": 1, "mutation_rate": 0.37, "population_size": 21, "tournament_size": 5}` | 10/10 | 0.00 | 61.1 | 825.3 | 100% | 242.6 |
| ga-04 | `{"crossover_rate": 0.96, "elites": 2, "mutation_rate": 0.29, "population_size": 22, "tournament_size": 4}` | 10/10 | 0.00 | 64.1 | 829.1 | 100% | 190.3 |
| ga-13 | `{"crossover_rate": 0.72, "elites": 2, "mutation_rate": 0.67, "population_size": 18, "tournament_size": 3}` | 10/10 | 0.00 | 65.4 | 838.8 | 100% | 242.3 |
| ga-03 | `{"crossover_rate": 0.68, "elites": 1, "mutation_rate": 0.57, "population_size": 20, "tournament_size": 3}` | 10/10 | 0.00 | 67.2 | 831.9 | 100% | 221.9 |
| ga-16 | `{"crossover_rate": 0.97, "elites": 2, "mutation_rate": 0.21, "population_size": 21, "tournament_size": 4}` | 10/10 | 0.00 | 67.8 | 832.8 | 100% | 182.9 |
| ga-18 | `{"crossover_rate": 0.64, "elites": 3, "mutation_rate": 0.12, "population_size": 26, "tournament_size": 3}` | 10/10 | 0.00 | 69.2 | 832.4 | 100% | 185.4 |
| ga-10 | `{"crossover_rate": 0.9, "elites": 1, "mutation_rate": 0.33, "population_size": 25, "tournament_size": 2}` | 10/10 | 0.00 | 70.6 | 837.8 | 100% | 224.5 |
| ga-12 | `{"crossover_rate": 0.84, "elites": 2, "mutation_rate": 0.23, "population_size": 27, "tournament_size": 2}` | 10/10 | 0.00 | 74.4 | 842.3 | 100% | 237.7 |
| ga-00 (ค่าเริ่มต้น) | `{"crossover_rate": 0.9, "elites": 1, "mutation_rate": 0.3, "population_size": 12, "tournament_size": 3}` | 10/10 | 0.00 | 76.2 | 839.4 | 100% | 237.8 |
| ga-19 | `{"crossover_rate": 0.93, "elites": 2, "mutation_rate": 0.88, "population_size": 32, "tournament_size": 2}` | 10/10 | 0.00 | 77.2 | 833.2 | 100% | 164.9 |
| ga-05 | `{"crossover_rate": 0.64, "elites": 1, "mutation_rate": 0.25, "population_size": 18, "tournament_size": 4}` | 10/10 | 0.00 | 83.7 | 838.2 | 100% | 178.3 |
| ga-17 | `{"crossover_rate": 0.85, "elites": 3, "mutation_rate": 0.14, "population_size": 7, "tournament_size": 4}` | 10/10 | 0.00 | 88.7 | 839.6 | 100% | 186.6 |
| ga-02 | `{"crossover_rate": 0.7, "elites": 1, "mutation_rate": 0.16, "population_size": 11, "tournament_size": 4}` | 10/10 | 0.00 | 94.0 | 835.6 | 100% | 239.1 |
