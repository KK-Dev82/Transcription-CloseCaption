# Fuzzy Match Dictionary

ใช้สำหรับ Fuzzy Match Post-processing ของข้อความ transcription ภาษาไทย
(ชื่อคน, คำศัพท์เฉพาะทาง ที่ ASR อาจสะกดผิด)

## โครงสร้างไฟล์

| ไฟล์ | รูปแบบ | จำนวน | ใช้สำหรับ |
|------|--------|-------|-----------|
| `names.txt` | หนึ่งบรรทัดต่อหนึ่งชื่อ | ~300 | ชื่อคน (Fuzzy Match ชื่อ) |
| `vocabulary.txt` | หนึ่งบรรทัดต่อหนึ่งคำ | ตามต้องการ | คำศัพท์เฉพาะทาง (ราชการ, วิชาการ, etc.) |
| `name_prefixes.txt` | หนึ่งบรรทัดต่อหนึ่งคำนำหน้า | ~10 | คำนำหน้าชื่อ (optional - สำหรับ strip ก่อน match) |

---

## รูปแบบไฟล์

### names.txt

- **Format:** หนึ่งบรรทัดต่อหนึ่งชื่อ
- **ไม่รวมคำนำหน้า** (นาย, นาง, นางสาว, etc.) — เก็บเฉพาะชื่อจริง + นามสกุล
- **Encoding:** UTF-8
- **Comment:** บรรทัดที่ขึ้นต้นด้วย `#` จะถูกข้าม

```
# รายชื่อสมาชิก (ตัวอย่าง)
สมชาย ใจดี
มานะ มีสุข
วิไล รักเมือง
กรรมาธิการ สมบัติ
```

### vocabulary.txt

- **Format:** หนึ่งบรรทัดต่อหนึ่งคำ
- **Encoding:** UTF-8
- **Comment:** บรรทัดที่ขึ้นต้นด้วย `#` จะถูกข้าม

```
# คำศัพท์เฉพาะทาง
กรรมาธิการ
ประชุมสภาแห่งชาติ
วุฒิสภา
สมาชิกสภา
ร่างกฎหมาย
```

### name_prefixes.txt (optional)

- **Format:** หนึ่งบรรทัดต่อหนึ่งคำนำหน้า
- **ใช้สำหรับ:** strip คำนำหน้าก่อน fuzzy match ชื่อ
- ถ้า ASR ได้ "นายสมชาย ใจดี" → strip "นาย" → match กับ "สมชาย ใจดี"

```
นาย
นาง
นางสาว
ด.ช.
ด.ญ.
อาจารย์
ศาสตราจารย์
ผู้ช่วยศาสตราจารย์
ร้อยเอก
พันเอก
```

---

## คำนำหน้าชื่อ: จำเป็นต้องมีไหม?

**ไม่จำเป็นต้องใส่ใน names.txt** — เก็บเฉพาะชื่อจริง + นามสกุล

**เหตุผล:**
1. ASR อาจได้ "นายสมชาย" หรือ "สมชาย" หรือ "สมชายใจดี"
2. เก็บชื่อจริง "สมชาย ใจดี" ใน dictionary
3. Code จะ strip คำนำหน้า (จาก name_prefixes.txt) ก่อน match
4. ลดความซ้ำซ้อน — ไม่อย่างนั้นต้องเก็บ "นายสมชาย", "นางสมชาย", "สมชาย" หลายบรรทัด

**ถ้าไม่ใช้ name_prefixes.txt:** Code จะ match แบบคำต่อคำ — "สมชาย" ใน text จะ match กับ "สมชาย ใจดี" (fuzzy) ได้อยู่แล้ว

---

## การเพิ่มข้อมูล

1. เปิดไฟล์ด้วย text editor ที่รองรับ UTF-8
2. เพิ่มรายการทีละบรรทัด
3. ไม่ต้องเรียงลำดับ
4. บรรทัดว่างจะถูกข้าม

---

## Path ที่ใช้ในโปรเจกต์

```
data/fuzzy_match/names.txt
data/fuzzy_match/vocabulary.txt
data/fuzzy_match/name_prefixes.txt  (optional)
```

Config path ใน `.env` (ถ้าต้องการ override):

```
FUZZY_MATCH_NAMES_PATH=data/fuzzy_match/names.txt
FUZZY_MATCH_VOCABULARY_PATH=data/fuzzy_match/vocabulary.txt
FUZZY_MATCH_NAME_PREFIXES_PATH=data/fuzzy_match/name_prefixes.txt
FUZZY_MATCH_NAME_THRESHOLD=0.85
FUZZY_MATCH_VOCAB_THRESHOLD=0.85
```

## เปิด/ปิดการใช้งาน

| ตัวแปร | ค่า | ใช้กับ |
|--------|-----|--------|
| `CC_FUZZY_MATCH_ENABLED` | `true` / `false` | FE CC (NeMo/TyPhoon + faster-whisper) |
| `FUZZY_MATCH_ENABLED_FOR_TRANSCRIPTION` | `true` / `false` | File transcription (aggregator) |
