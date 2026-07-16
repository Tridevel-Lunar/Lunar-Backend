# LAIKA knowledge corpus

เนื้อหาถูกจัดเป็น 3 module ตามแพลตฟอร์ม:

```
data/knowledge/
├── manifest.yaml       # ทะเบียนกลาง — id, module, stage, path, topic, license
├── README.md
└── space/              # บทเรียน Space (แยกตาม stage / course)
    └── cubesat-for-beginner/
        ├── Module1_Overview_of_Satellite_Content.md
        ├── Module2_Anatomy_of_CubeSat_Content.md
        ├── Module3_Physics_for_Space_LAIKA_v1.md
        └── Module4_Programming_Content.md
```

## Workflow

1. แก้/เพิ่ม `.md` ใน folder ที่เหมาะสม
2. ลงทะเบียนใน `manifest.yaml` (ใช้ `id` คงที่ — อย่าเปลี่ยนบ่อย)
3. Sync + ingest ผ่าน Backoffice → **Sync manifest** หรือ CLI:

```bash
docker compose exec backend python -m scripts.sync_knowledge_manifest
```

4. เอกสาร ad-hoc (PDF ฯลฯ) ยังอัปโหลดผ่าน Backoffice ได้โดยตรง (`source_origin: upload`)

## Manifest fields

| Field | คำอธิบาย |
|-------|----------|
| `id` | รหัสคงที่ (เช่น `space-cubesat-101-power`) |
| `module` | `space` \| `arena` \| `studio` |
| `stage` | ชื่อด่าน/course/mission หรือหัวข้อกลุ่ม (studio ใช้แทน subfolder) |
| `order` | ลำดับในด่าน (optional) |
| `path` | path จาก `data/knowledge/` |
| `topic` | ใช้ filter RAG / แสดง sources |
| `license` | สำคัญสำหรับ studio reference |
| `audience` | `learner` \| `studio` \| `both` |

## PDF (studio)

วางไฟล์ flat ใน `studio/` (เช่น `studio/nasa-cubesat-101.pdf`) เมื่อ license อนุญาต — ลงทะเบียนใน manifest ด้วย `type: pdf`
