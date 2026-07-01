# Document Translation Flow / Luồng dịch tài liệu

Technical overview of PDF/DOCX translation in AI Translation System.

---

## Tiếng Việt

### Phạm vi

| Hạng mục | Giá trị |
|----------|---------|
| File hỗ trợ | `.pdf`, `.docx` (luồng chính); Excel/PPT qua converter |
| Upload API | `POST /api/translation/document` |
| Trạng thái job | `GET /api/translation/document/status/{job_id}` |
| Tải kết quả | `GET /downloads/{filename}` |
| Xử lý | Bất đồng bộ (background + polling frontend) |

### Luồng tổng quan

1. **Frontend** — user chọn file, ngôn ngữ, tuỳ chọn OCR/song ngữ  
2. **API** — validate, trừ token, tạo job, trả `job_id`  
3. **Worker** — `TranslationService` + `FileService` xử lý file  
4. **PDF** — pipeline PDF → DOCX → dịch → khôi phục layout → PDF  
5. **DOCX** — dịch trực tiếp giữ paragraph/run/style  
6. **Hoàn tất** — copy vào `utils/download`, client poll → tải file  

### Pipeline PDF (10 bước chính)

1. **Analyzer** — text vs scan, bảng, cột, ảnh  
2. **Scan OCR** — nếu PDF scan → searchable PDF  
3. **PDF Cleaner** — xoay, deskew, enhance  
4. **PDF → DOCX** — `pdf2docx` (mặc định)  
5. **DOCX translation** — giữ run, style, bảng, heading  
6. **Layout recovery** — co font bảng, xuống dòng, ảnh  
7. **DOCX → PDF** — Word hoặc LibreOffice  
8. **Quality check** — phát hiện mất chữ/bảng  

Biến môi trường: xem `api_base/.env.example` (prefix `PDF_DOCX_*`, `DOCX_*`).

### Chế độ song ngữ

| Mode | Hành vi |
|------|---------|
| `none` | Chỉ bản dịch |
| `preserve_layout` | `Gốc \| Dịch` cùng đoạn |
| `newline` | Gốc và dịch trên 2 dòng |

PDF thường **chặn newline mode** để tránh chồng chữ.

### Nhà cung cấp dịch

Google Translate, DeepL, Gemini — chọn trên Dashboard hoặc gửi `translation_provider` trong form.

### Chi tiết đầy đủ

Xem [QUY_TRINH_DICH_FILE.md](../QUY_TRINH_DICH_FILE.md) (tiếng Việt, có sơ đồ Mermaid).

---

## English

### Scope

| Item | Value |
|------|-------|
| Supported files | `.pdf`, `.docx` (main flow) |
| Upload API | `POST /api/translation/document` |
| Job status | `GET /api/translation/document/status/{job_id}` |
| Download | `GET /downloads/{filename}` |
| Processing | Async background job + frontend polling |

### High-level flow

1. **Frontend** — user selects file, language, OCR/bilingual options  
2. **API** — validate, deduct tokens, create job, return `job_id`  
3. **Worker** — `TranslationService` + `FileService`  
4. **PDF** — PDF → DOCX → translate → layout recovery → PDF  
5. **DOCX** — direct translation preserving runs/styles  
6. **Complete** — output to `utils/download`, client polls and downloads  

### PDF pipeline (main stages)

1. **Analyzer** — text vs scan, tables, columns, images  
2. **Scan OCR** — searchable PDF for scanned documents  
3. **PDF Cleaner** — rotate, deskew, enhance  
4. **PDF → DOCX** — `pdf2docx` (default)  
5. **DOCX translation** — preserve runs, styles, tables  
6. **Layout recovery** — font fit, line breaks, images  
7. **DOCX → PDF** — Word or LibreOffice export  
8. **Quality check** — detect missing text/tables  

Environment variables: `api_base/.env.example` (`PDF_DOCX_*`, `DOCX_*`).

### Bilingual modes

| Mode | Behavior |
|------|----------|
| `none` | Translation only |
| `preserve_layout` | `Original \| Translation` inline |
| `newline` | Original and translation on separate lines |

PDF often **disables newline mode** to avoid text overlap.

### Translation providers

Google Translate, DeepL, Gemini — select on Dashboard or via `translation_provider` form field.

### Full technical doc

See [QUY_TRINH_DICH_FILE.md](../QUY_TRINH_DICH_FILE.md) (Vietnamese, Mermaid diagrams).

---

**See also:** [USER_GUIDE.md](./USER_GUIDE.md) · [INSTALLATION_GUIDE.md](./INSTALLATION_GUIDE.md)
