# Module 4: Programming — Command Your CubeSat
## Lesson Content Reference สำหรับ LAIKA (AI Mentor)

**เป้าหมายของโมดูล:** ผู้เรียนออกจากโมดูลนี้แล้วต้อง (1) เข้าใจว่าดาวเทียมไม่มี "ความคิดเป็นของตัวเอง" ทุกการตัดสินใจต้องมีมนุษย์เขียนโปรแกรมสั่งไว้ล่วงหน้า (2) รู้จักและใช้ concept การเขียนโปรแกรมพื้นฐาน (data type, if/else ซ้อนได้, loop แบบ tick, การตั้งค่าล่วงหน้า/threshold, event-driven) ผ่านบล็อก เพื่อคุม **EPS (พลังงาน) + Thermal (ความร้อน) + OBC (การตัดสินใจ)** ให้ดาวเทียมอยู่รอดจนจบ window (3) เห็นผลลัพธ์ของโค้ดตัวเองเป็นตัวเลขจริง (battery, temperature) และผล grading ไม่ใช่แค่ "ถูก/ผิด"

**หลักการสำคัญที่ยึดต่อจากโมดูล 1-3:** ศัพท์เทคนิคทุกตัวต้องมีคำอธิบายกำกับทันทีที่โผล่ครั้งแรก และเนื้อหาต้องแม่นยำเชิงเทคนิค — โมดูลนี้ใช้ block-based programming (การเขียนโปรแกรมแบบต่อบล็อก) ใน Arena โดยโครงสร้างภารกิจเป็น **Setup → Main Loop → Check** (คล้าย `void setup()` + main loop ของ embedded) และ **ตรรกะเบื้องหลังบล็อกต้องสะท้อนหลักการ flight software จริง** ไม่ใช่ logic ที่แต่งขึ้นเองแบบไม่มีมูล (ดูหัวข้อ 4.6 สำหรับรายละเอียดที่ควรอิงอ้างถูกต้อง)

**โครงสร้างภารกิจที่ implement แล้ว (Mission 01 — `leo-orbital-launch`):**
```
[SETUP]  — ตั้งค่า threshold / heater / payload ก่อนเริ่มจำลอง
   ↓
[MAIN LOOP] — โค้ดบล็อกที่รันซ้ำทุก tick จนครบ 10 tick
   ↓
[CHECK]  — ระบบเทียบ battery + temperature ตอนจบ ให้ผล Perfect / Risky / Fail
           แล้วคำนวณผล Comms และ Longevity ให้อัตโนมัติ
```

---

## 4.1 ทำไมดาวเทียมต้องมีโปรแกรมสั่งงาน

**Hook เปิดเรื่อง:** เปิดด้วยภาพ CubeSat "ลอยนิ่งเฉยๆ" ไม่ทำอะไรเลย
> "ตอนนี้ดาวเทียมดวงนี้เป็นแค่กล่องโลหะราคาแพงที่ลอยอยู่เฉยๆ — มันมี OBC (สมองกลาง) มี EPS มี COMM มี Payload ครบตามที่เรียนในโมดูลที่แล้ว แต่ไม่มีอะไรทำงานเลยสักอย่าง เพราะอะไร?"
> คำตอบ: เพราะ "สมอง" ของมันว่างเปล่า ไม่มีใครบอกมันว่าเจอสถานการณ์แบบไหนต้องทำอะไร ถ้าไม่มีโปรแกรมสั่ง มันจะกลายเป็นแค่ขยะอวกาศ (space debris) ที่ลอยเปะปะไปเรื่อยๆ

**เชื่อมกับโมดูล 2:** ทวนความจำว่า OBC (สมองกลาง) ทำหน้าที่แค่ "รับข้อมูล → ตัดสินใจ → สั่งงาน" — แต่กฎการตัดสินใจทั้งหมดนั้น**มนุษย์ต้องเป็นคนเขียนไว้ล่วงหน้า** OBC ไม่ได้ฉลาดขึ้นมาเอง มันแค่ทำตามเงื่อนไขที่ถูกเขียนสั่งไว้เป๊ะๆ

**เชื่อมกับ Arena:** ใน Mission 01 ผู้เรียนไม่ได้เขียนโค้ดคุม COMM หรือ Longevity โดยตรง — ระบบคำนวณผลสองอย่างนี้จากว่า **แบตเตอรี่และอุณหภูมิ ณ tick สุดท้าย** อยู่ในเกณฑ์ดีแค่ไหน นี่คือแนวคิด "แกนหลักคือ EPS + Thermal + OBC ส่วน Comms คือผลลัพธ์ที่รอ"

---

## 4.2 พื้นฐานที่ต้องรู้ก่อนต่อบล็อก (Foundational Concepts)

ก่อนให้ผู้เรียนลงมือต่อบล็อก ต้องปูพื้น 5 concept นี้ก่อน เพราะ Mission 01 ไล่ความซับซ้อนผ่าน 3 เฟสภายใน window เดียว (10 tick) และต้องใช้ concept เหล่านี้จริง ไม่ใช่แค่ if/else เดี่ยวๆ — ให้สอนแต่ละอันด้วย analogy สั้นๆ ที่ผูกกับดาวเทียมทันที

### 4.2.1 Data Type (ชนิดข้อมูล)
ค่าที่ sensor แต่ละตัวอ่านมา "ไม่เหมือนกัน" — ต้องรู้จักก่อนว่าค่าที่ได้เป็นชนิดไหน ถึงจะเอาไปเทียบเงื่อนไขถูก
| ชนิดข้อมูล | หน้าตา | ตัวอย่างจากบล็อกใน Mission 01 |
|---|---|---|
| **Number (ตัวเลข)** | ค่าตัวเลขที่เอาไปเทียบมากกว่า-น้อยกว่าได้ | `battery level = 55`, `temperature = 50`, `tick number = 8` |
| **Boolean (ค่าจริง-เท็จ)** | มีแค่ 2 สถานะ: `true` หรือ `false` | `is daylight? = true` (tick 1-2 เป็น day), `is daylight? = false` (tick 3 เป็น night) |

**จุดที่ต้องเน้น:** เอา Boolean ไปเทียบแบบ `< 20%` ไม่ได้ และเอา Number ไปเช็คแบบ `if battery level` เฉยๆ ก็ผิด (ต้องใช้บล็อกเปรียบเทียบ `<`, `<=`, `>`, `>=`, `=` กับค่าที่ตั้งไว้) — ความผิดพลาดแบบนี้เกิดขึ้นบ่อยกับมือใหม่ ควรมี checkpoint เล็กๆ ให้จับผิดคู่ที่ผิดชนิดข้อมูล

### 4.2.2 If / Else แบบซ้อนได้ (Nested Condition)
**if/else ซ้อนกันได้หลายชั้น** ไม่ใช่มีแค่ 2 ทางเลือกเสมอไป เช่น ถ้า `is daylight?` เป็น true ให้เปิด payload ถ้าไม่ใช่ค่อยปิด — หรือซ้อนอีกชั้นว่าถ้า `temperature` ต่ำเกิน threshold ให้เปิด heater สื่อสารด้วย diagram แบบ flowchart แตกกิ่งหลายชั้นในบล็อกเอดิเตอร์

### 4.2.3 Loop แบบ Tick (การวนซ้ำตามรอบจำลอง)
**Analogy:** OBC ของจริงไม่ได้เช็คค่าแค่ครั้งเดียวจบแล้วหยุด — มันวนเช็ค sensor ซ้ำๆ ตลอดเวลาที่ดาวเทียมยังทำงานอยู่ เหมือนยามเฝ้าประตูที่คอยมองซ้ายขวาซ้ำๆ ไม่ใช่มองแค่ครั้งเดียวแล้วเลิก

ใน Mission 01 ใช้ **tick** แทนเวลาจริง (ไม่ใช่วินาที) เพื่อให้ผลลัพธ์ deterministic และเทสต์ซ้ำได้:
- บล็อก `repeat until end of window` — วนหนึ่งรอบต่อ 1 tick จนครบ 10 tick (ไม่ใช่ spin ใน tick เดียว)
- บล็อก `wait 1 tick` — จบ tick ปัจจุบันทันที แล้วขยับไป tick ถัดไปโดยไม่ทำอะไรเพิ่ม

**จุดที่ต้องเน้น:** 1 tick = 1 รอบจำลอง ไม่ใช่เวลาจริง — ความยากของภารกิจคุมด้วยจำนวน tick (Mission 01 ใช้ 10 tick) ไม่ใช่ wall-clock

### 4.2.4 การตั้งค่าล่วงหน้า (Setup / Threshold)
แทนที่จะใช้ตัวแปรเปลี่ยนค่าระหว่างรัน ใน Mission 01 ผู้เรียน **กำหนด threshold ก่อนเริ่มจำลอง** ในส่วน Setup (คล้าย `void setup()` ของ Arduino):
- `set battery threshold low = [__]%` — กำหนดค่าที่ถือว่า "แบตต่ำ"
- `set battery threshold high = [__]%` — กำหนดค่าที่ถือว่า "แบตเต็ม/ปลอดภัย"
- `set temp threshold min/max = [__]°C` — กำหนดช่วงอุณหภูมิที่ยอมรับได้
- `set heater power = [__]%` — กำหนดกำลังไฟที่ฮีตเตอร์ใช้ต่อ tick
- `enable payload: [camera / science_sensor / off]` — เลือกเปิด payload หรือไม่

**จุดที่ต้องเน้น:** threshold เหล่านี้ถูกใช้โดยบล็อก `when [event] do` (เช่น `battery_low`, `too_cold`) และระบบ grading ตอนจบ — การวางแผน Setup ดีๆ คือการ "ออกแบบ flight software ก่อนขึ้นบิน" ไม่ใช่แก้ตัวเลขกลางอากาศ

### 4.2.5 Event-driven (เมื่อเกิดเหตุการณ์แล้วทำ)
**Analogy:** แทนที่จะเช็คทุกอย่างด้วย if/else ตลอดเวลา บางครั้งเราอยากให้โปรแกรม "รอฟัง" เหตุการณ์แล้วตอบสนองทันที — เหมือน OBC ที่มี interrupt handler สำหรับเหตุฉุกเฉิน

- บล็อก `when [event] do ...` — ทำงานเมื่อเหตุการณ์เกิดขึ้นใน tick นั้น
- เหตุการณ์ที่มีใน Mission 01: `battery_low`, `battery_high`, `too_cold`, `too_hot`, `glitch_tick`
- **จุดสำคัญ:** `glitch_tick` (radiation glitch) เกิดขึ้น**ตายตัวที่ tick 8** — ลดแบต 25% ทันที ผู้เรียนต้องเตรียม `when glitch_tick do enter safe mode` (หรือ logic อื่น) ไว้ล่วงหน้า

**จุดที่ต้องเน้น:** `when` กับ `if` ต่างกัน — `if` เช็คทุก tick ตามลำดับใน Main Loop, `when` เป็น event block ที่ระบบประมวลผลก่อน main body ในแต่ละ tick (ดูลำดับการรันใน 4.6)

---

## 4.3 บล็อกทั้งหมดที่ใช้ได้ (5 กลุ่ม — ตาม Toolbox Mission 01)

ให้ยึดโครงเดียวกับที่ OBC ทำงานจริงในโมดูล 2 (ตั้งค่า → อ่านค่า → ตัดสินใจ → สั่งงาน) และแยก Setup ออกจาก Main Loop ชัดเจน

> **หมายเหตุ:** ตัดบล็อก ADCS (การหมุน/ทิศทาง), Propulsion, `deploy solar panel`, `capture image`, `transmit data` ออกจาก Mission 01 — พลังงานจากแสงอาทิตย์ผูกกับ `is daylight?` แบบ schedule ตายตัว ไม่ต้องคำนวณมุม

### 🔧 Setup Blocks (ใช้ได้เฉพาะในบล็อก `Setup` เท่านั้น)
| บล็อก | ทำหน้าที่ | ค่าเริ่มต้น (Mission 01) |
|---|---|---|
| `set battery threshold low = [__]%` | กำหนดค่าที่ถือว่า "แบตต่ำ" | 20% |
| `set battery threshold high = [__]%` | กำหนดค่าที่ถือว่า "แบตเต็ม/ปลอดภัย" | 80% |
| `set temp threshold min/max = [__]°C` | กำหนดช่วงอุณหภูมิที่ยอมรับได้ | 15–55°C |
| `set heater power = [__]%` | กำหนดกำลังไฟที่ฮีตเตอร์ใช้ต่อ tick | 30% |
| `enable payload: [camera / science_sensor / off]` | เลือกเปิด payload หรือไม่ | off |

### 📡 Sensor Blocks (บล็อกอ่านค่า — ใช้ใน Main Loop)
| บล็อก | อ่านค่าจากระบบไหน (ทวนโมดูล 2) | ชนิดข้อมูล | ตัวอย่างค่าที่ได้ |
|---|---|---|---|
| `battery level` | EPS | Number | เปอร์เซ็นต์แบตเตอรี่ (0–100%) |
| `temperature` | Payload/EPS (Thermal) | Number | อุณหภูมิปัจจุบัน (°C) |
| `is daylight?` | EPS (แสงอาทิตย์) | Boolean | true/false ตาม schedule ของ mission |
| `tick number` | OBC (รอบจำลอง) | Number | 1, 2, 3, … 10 |

### ⚙️ Actuator Blocks (บล็อกสั่งงาน — ใช้ใน Main Loop)
| บล็อก | สั่งไปที่ระบบไหน | ผลลัพธ์ |
|---|---|---|
| `turn heater [ON/OFF]` | EPS/Thermal | เปิด/ปิดฮีตเตอร์ (กินพลังงาน + เพิ่มอุณหภูมิตอนเปิด) |
| `turn payload [ON/OFF]` | Payload | เปิด/ปิด payload ชั่วคราว (กินพลังงานเล็กน้อย + เพิ่มความร้อนเล็กน้อย) |
| `enter safe mode` | ทุกระบบ | ปิด payload/heater ทันที ประหยัดพลังงานสุด (+2 แบต/tick) |
| `exit safe mode` | ทุกระบบ | กลับสู่โหมดปกติ (มีผลที่ tick ถัดไป ไม่ใช่ tick เดียวกัน) |

### 🧠 Control Blocks (ตรรกะ — ใช้ใน Main Loop)
| บล็อก | ทำหน้าที่ |
|---|---|
| `if [เงื่อนไข] then ... else ...` | เงื่อนไขมาตรฐาน (ซ้อนได้) |
| `when [event] do ...` | event-driven: `battery_low`, `battery_high`, `too_cold`, `too_hot`, `glitch_tick` |
| `[ค่า] < / <= / > / >= / = [ค่า]` | เปรียบเทียบตัวเลข (เช่น `battery level < 20`) |
| `wait 1 tick` | ข้ามไป tick ถัดไปโดยไม่ทำอะไร |
| `repeat until end of window` | วนหนึ่งรอบต่อ tick จนครบ window |

### 📋 โครงโปรแกรม (Program Structure)
| บล็อก | ทำหน้าที่ |
|---|---|
| `Setup` | ครอบบล็อก Setup ทั้งหมด — รันครั้งเดียวก่อนเริ่มจำลอง |
| `Main Loop` | ครอบ logic ทั้งหมด — รันซ้ำทุก tick จนครบ 10 tick |

---

## 4.4 ภารกิจ (Mission-based Progression)

หลักการ: **ทุก mission ต้อง "Run" แล้วเห็นผลจริงบน battery bar + temperature gauge ทุก tick** ไม่ใช่แค่ขึ้นเครื่องหมายถูก — Mission 01 รวม 4 บทเรียนย่อยไว้ใน **window เดียว 10 tick** แบ่งเป็น 3 เฟส + Comms Check โดยใช้ **banner คั่นเฟส** บน timeline แทนการโหลดฉากใหม่

### Mission 01: FIRST ORBIT SURVIVAL (`leo-orbital-launch`)

**เป้าหมายการเรียนรู้ (ไล่ระดับภายใน mission เดียว):** if/else พื้นฐาน → จัดการ 2 ทรัพยากรพร้อมกัน (แบต + อุณหภูมิ) → event-driven programming → วางแผน Setup ล่วงหน้าให้ผลลัพธ์ตรงเป้า

**Starting condition (demo mode):** แบตเริ่ม 55%, อุณหภูมิเริ่ม 50°C — ใช้ชุดค่าเดียวตายตัวเพื่อให้สาธิตคาดเดาได้

**Daylight schedule (10 tick):**
| Tick | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| `is daylight?` | ☀️ | ☀️ | 🌙 | ☀️ | 🌙 | 🌙 | ☀️ | 🌙+⚡ | ☀️ | ☀️ (check) |

- Tick 8: **radiation glitch** ลดแบต 25% ทันที (ตายตัว ไม่สุ่ม)
- Tick 10: **Comms Check** — ground station pass เกิดขึ้น ระบบเช็คผลรวมทั้งหมด (ไม่รับคำสั่งใหม่)

**เฟสภายใน Mission:**

| เฟส | Tick | สิ่งที่เกิดขึ้น | บล็อกใหม่ที่เน้นสอน |
|---|---|---|---|
| 🔋 Power Phase | 1–3 | `is daylight?` สลับ day/night, ยังไม่มีอุณหภูมิเปลี่ยนแรง | `battery level`, `is daylight?`, `turn payload [ON/OFF]` |
| 🌡️ Thermal Phase | 4–6 | เริ่มมีค่า `temperature` เข้ามาและลดลงเรื่อยๆ ฝั่ง night | + `temperature`, `turn heater [ON/OFF]` |
| ⚡ OBC Phase | 7–9 | `glitch_tick` ที่ tick 8 ลดแบต 25% | + `when [event] do`, `enter/exit safe mode`, `tick number` |
| 📡 Comms Check | 10 | เช็คผลรวม battery + temperature | ใช้ทักษะที่มีทั้งหมด — ไม่มีบล็อกใหม่ |

**โจทย์รวม:** เขียนโค้ดเดียวที่คุมพลังงาน + ความร้อนตลอด 9 tick แรก และตอบสนอง glitch ที่ tick 8 ได้ทัน เพื่อให้ ณ tick 10 แบตและอุณหภูมิอยู่ในเกณฑ์ **Perfect**

**Outcome ที่เห็น:**
- Battery bar + temperature gauge อัปเดต real-time ทุก tick
- Banner คั่นเฟส ("🔋 Power Phase" → "🌡️ Thermal Phase" → "⚡ OBC Phase") ตอน tick 4 และ 7
- Visual shake/flash สั้นๆ เมื่อ glitch เกิดที่ tick 8
- ผลลัพธ์ปิดท้าย: **"ดาวเทียมอยู่รอด: ใช่/ไม่ใช่ — ส่งข้อมูลกลับโลกได้: ใช่/ไม่ใช่"**

### ระบบให้คะแนน (Grading — Check Phase)

เมื่อจบ tick 10 ระบบเช็ค **battery level** และ **temperature** พร้อมกัน:

| ผลลัพธ์ | เงื่อนไข |
|---|---|
| ✅ **Perfect (สมบูรณ์)** | `battery_end` อยู่ 40–100% **และ** `temperature_end` อยู่กลางช่วง threshold (temp_min+5 ถึง temp_max−5) |
| ⚠️ **Risky (เสี่ยง)** | ไม่ Perfect แต่ `battery_end` ≥ 15% และ temp ยังอยู่ในช่วง min–max |
| ❌ **Fail (ไม่ผ่าน)** | `battery_end` < 15% **หรือ** temp หลุดช่วง min–max |

**ผลลัพธ์ที่คำนวณอัตโนมัติ (ผู้เรียนไม่เขียนโค้ดคุมเอง):**
- **Comms:** Perfect = ส่งข้อมูลสำเร็จครบ (+ โบนัสถ้า payload effective ณ tick 10) / Risky = ส่งได้บางส่วน / Fail = พลาด pass รอบนี้
- **Longevity:** Perfect = ไม่เสีย health / Risky = เสียเล็กน้อย / Fail = เสียมาก (ระบบสะสม health ยังเป็น coming soon)

### Capstone / โหมดฝึกฝนหลังเดโม (Coming Soon)
- หลาย starting condition ต่อ 1 mission (บังคับใช้ if/else จริง ไม่ hard-code ตัวเลข)
- ภารกิจเพิ่มเติมที่ขยายจาก Mission 01

---

## 4.5 Interactive Mechanic

- Block editor แบบลากวาง (drag-and-drop) 5 หมวดตาม Toolbox: **Setup / Main Loop / Sensors / Actuator / Safe Mode** — โครงโปรแกรมต้องมีบล็อก `Setup` และ `Main Loop` เป็นหลัก
- ปุ่ม **Run** จะ simulate ผลลัพธ์ **ทีละ tick** ไม่ใช่กระโดดไปผลลัพธ์สุดท้ายทันที — ให้เห็น battery/temperature เปลี่ยนทุก tick คล้าย debugger ง่ายๆ
- **Time acceleration:** tick ที่ไม่มีอะไรเกิด (เช่น 1–2 แรก) วิ่งเร็ว แล้วชะลอ normal speed ช่วง tick 7–10 ที่มี glitch และ pass
- ผลลัพธ์แสดงพร้อมกัน 2 จุด: (1) battery bar + temperature gauge real-time (2) timeline ไฮไลต์ tick ปัจจุบัน พร้อมจุดบอก "pass จะเกิดตรงนี้" (tick 10)
- ตอนจบแสดง grading card: Perfect / Risky / Fail + ผล Comms + ข้อความสรุป "ดาวเทียมอยู่รอด / ส่งข้อมูลกลับโลกได้"
- มี **pre-built script** ที่ผ่าน Perfect ไว้ล่วงหน้า เผื่อสาธิตเร็ว แล้วค่อยแก้โค้ดสดบางจุดให้เห็นว่าพัง/แก้ได้จริง

---

## 4.6 เกร็ดเทคนิคเบื้องหลังบล็อก (สำหรับความถูกต้อง — ใช้เป็น optional/advanced note ให้ LAIKA เปิดเผยเมื่อผู้เรียนถามลึกขึ้น)

เพื่อไม่ให้เนื้อหาความรู้ผิดเพี้ยนจากของจริง แม้จะย่อให้ง่ายด้วยบล็อก แต่หลักการเบื้องหลังควรอ้างอิงกับสถาปัตยกรรมจริงที่ CubeSat ใช้:

- **Setup vs Main Loop ในของจริง:** แยก "การตั้งค่าครั้งเดียวตอนบูต" กับ "ลูปทำงานต่อเนื่อง" ตรงกับ flight software จริงที่มี initialization phase แล้วเข้า main loop ไม่สิ้นสุด
- **`if battery < threshold → safe mode` ในของจริง** มักถูกเรียกว่า **watchdog logic** หรือ fault-detection routine ซึ่งเป็นส่วนสำคัญของ flight software แทบทุกดาวเทียม
- **`repeat until end of window` ในของจริง** คือสิ่งที่เรียกว่า **main loop** ของ flight software — โปรแกรมควบคุมดาวเทียมแทบทุกดวงเขียนเป็นลูปไม่สิ้นสุดที่วนอ่านค่า sensor → ประมวลผล → สั่งงาน ซ้ำไปเรื่อยๆ
- **`when [event] do` ในของจริง** สอดคล้องกับ **interrupt handler** หรือ event callback ใน embedded — เช่น เมื่อ radiation event เกิดขึ้น ระบบต้องตอบสนองทันทีไม่รอ main loop รอบถัดไป
- **Simulation physics (Mission 01 baseline):**
  - Battery ต่อ tick: day +12 / night −8; heater drain = `round(heater_power/10)`; payload drain −4; safe mode bonus +2; glitch tick 8: −25
  - Temperature ต่อ tick: day +3 / night −4; heater heat = `round(heater_power/15)`; payload heat +1
- **ลำดับการรันใน 1 tick (execution order):**
  1. อ่าน state ต้น tick
  2. ประมวลผล `when [event] do` ทั้งหมดที่เงื่อนไขเป็นจริง
  3. ประมวลผล main body (`if/else`, actuator, `wait`, `repeat`)
  4. resolve คำสั่ง actuator ที่ขัดแย้ง (priority: `enter safe mode` สูงสุด; last command wins)
  5. apply physics (battery/temperature delta)
  6. apply forced event (`glitch` tick 8)
  7. clamp + log + ขยับ tick ถัดไป
- **Comms ในของจริง** ต้องผ่าน ground station pass window (ทวนจากโมดูล 2) — ใน Mission 01 จำลองเป็น tick 10 ที่ระบบเช็คผลอัตโนมัติ ไม่ให้ผู้เรียนเขียนบล็อกส่งข้อมูลเองในเวอร์ชันนี้
- **ADCS, Propulsion, packet format, CSP** — ยังไม่อยู่ใน Mission 01 (coming soon / โมดูลขั้นสูง) แต่ถ้าผู้เรียนถามลึก ให้ LAIKA อธิบายว่ามีมาตรฐานจริงรองรับอยู่เบื้องหลัง

**หลักการเขียนบล็อกให้ทีม dev:** ชื่อบล็อกและ op ใน AST ต้องตรงกับ `allowedOps` ใน mission pack (`leo_orbital_launch.py`) และ Blockly block types (`m01_*.ts`) — ห้ามอ้างบล็อกที่ยังไม่ implement ในเนื้อหา LAIKA ของ Mission 01

---

## Checkpoint / Capstone
ใช้ Mission 01 เป็น checkpoint ปิดโมดูล — ประเมินจาก grading ตอนจบ (Perfect/Risky/Fail) และว่าผู้เรียนอธิบายเหตุผลของ logic ที่เลือกได้หรือไม่ (Setup thresholds, การตอบ glitch, การ balance แบต vs อุณหภูมิ) ไม่ใช่แค่ block ทำงานได้

---

## Glossary สั้นๆ สำหรับโมดูลนี้
| คำศัพท์ | ความหมายแบบเข้าใจง่าย |
|---|---|
| Data Type (ชนิดข้อมูล) | ประเภทของค่าที่ sensor เก็บไว้ เช่น ตัวเลข (Number), จริง-เท็จ (Boolean) |
| Tick (รอบจำลอง) | หน่วยหนึ่งรอบของการจำลองใน Mission 01 — ไม่ใช่เวลาจริง แต่เป็นขั้นตอนที่ deterministic |
| Setup / Threshold | ค่าที่กำหนดล่วงหน้าก่อนเริ่มจำลอง เช่น แบตต่ำกี่ % ถือว่าอันตราย |
| Loop / Main Loop (การวนซ้ำ) | ส่วนของโปรแกรมที่ทำงานซ้ำทุก tick ไม่หยุด ตราบใดที่ window ยังไม่จบ |
| Event-driven | รูปแบบโปรแกรมที่รอฟังเหตุการณ์ (เช่น glitch) แล้วตอบสนองทันที |
| Safe Mode (โหมดปลอดภัย) | โหมดประหยัดพลังงานสูงสุด — ปิด payload/heater ชั่วคราว |
| Radiation Glitch | เหตุการณ์รังสีที่ลดแบตทันที (ใน Mission 01 เกิดตายตัวที่ tick 8) |
| Grading (Perfect/Risky/Fail) | ระบบให้คะแนนจาก battery + temperature ตอนจบ window |
| Flight Software | ซอฟต์แวร์ที่ควบคุมการทำงานของดาวเทียมขณะบิน (สิ่งที่เรากำลังต่อบล็อกจำลองอยู่) |
| Watchdog / Fault-detection | ตรรกะที่คอยตรวจจับความผิดปกติแล้วสั่งรับมืออัตโนมัติ (เช่น safe mode) |
| Space Debris (ขยะอวกาศ) | วัตถุที่ลอยอยู่ในวงโคจรโดยไม่มีหน้าที่/ควบคุมไม่ได้อีกต่อไป |

## คำถามชวนคิดแบบ Socratic ที่ LAIKA ใช้ได้ระหว่างบทเรียน
- "ถ้าลืมตั้ง `battery threshold low` ใน Setup แล้วใช้ `when battery_low do` จะเกิดอะไรขึ้น?"
- "ทำไม `enter safe mode` ถึงมี priority สูงสุด — ถ้าสั่ง payload ON กับ safe mode ใน tick เดียวกัน อะไรชนะ?"
- "ถ้า OBC ไม่มีโปรแกรมสั่งไว้เลยแม้แต่บรรทัดเดียว ดาวเทียมจะกลายเป็นอะไร?"
- "ถ้าไม่มี `repeat until end of window` ครอบไว้ โปรแกรมจะทำงานกี่ tick แล้วหยุด?"
- "ทำไม glitch เกิดที่ tick 8 ตายตัว — ถ้าสุ่มได้ การสาธิตจะมีปัญหาอะไร?"
- "ถ้า Perfect แต่ payload ไม่ effective ณ tick 10 Comms จะได้โบนัสไหม?"
- "ถ้าแบต 39% กับ 40% ต่างกันยังไงใน grading — ทำไม boundary ถึงสำคัญ?"

---

## สิ่งที่ต้องเชื่อมไปขั้นถัดไป (สำหรับ LAIKA วางท่อนปิดท้าย)
- ปิดโมดูล 4 (และปิดคอร์ส CubeSat for Beginner ทั้งหมด) ด้วยการเชื่อมไปสู่ Arena: "นี่คือพื้นฐานของการสั่งงานดาวเทียม — ใน Arena Mission 01 (`FIRST ORBIT SURVIVAL`) คุณจะได้ลงมือต่อบล็อกจริง เจอ glitch จริง และเห็น battery/temperature เปลี่ยนทุก tick เหมือนวิศวกรดาวเทียมตัวจริง"
- Coming soon ใน Arena: หลาย starting condition, ภารกิจเพิ่มเติม, ระบบสะสม satellite health, ADCS/Propulsion, packet format
