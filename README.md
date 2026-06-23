# SmartPDF

Công cụ xử lý và dịch PDF tiếng Việt sang tiếng Anh.

## Khởi chạy local

Mở **2 terminal riêng**, chạy cùng lúc:

### Terminal 1 — Backend

```bash
cd backend
py -3 -m uvicorn main:app --reload --port 8000
```

> API docs: http://localhost:8000/docs

### Terminal 2 — Frontend

```bash
cd frontend
npm install        # chỉ cần chạy lần đầu
npm run dev
```

> App: http://localhost:5173

---

## Biến môi trường

Tạo file `backend/.env` (tùy chọn):

```
GEMINI_API_KEY=your_key_here
DEEPL_API_KEY=your_key_here   # không bắt buộc
```

Nếu không có `.env`, backend dùng key mặc định trong `html_translator.py`.

---

## Deploy (Railway)

- **Backend**: tự động deploy từ thư mục `backend/`
- **Frontend**: cần set biến môi trường `VITE_API_URL=https://<backend-url>.railway.app`

---

## Các tính năng

| Công cụ | Mô tả |
|---|---|
| Gộp PDF | Ghép nhiều file PDF thành một |
| Nén PDF | Giảm dung lượng file PDF |
| Cắt PDF | Tách PDF theo khoảng trang |
| PDF → Word | Chuyển PDF sang DOCX |
| Word → PDF | Chuyển DOCX sang PDF |
| PDF → Hình ảnh | Xuất từng trang PDF thành ảnh PNG/JPG |
| Hình ảnh → PDF | Ghép nhiều ảnh thành PDF |
| Chuyển đổi ảnh | Chuyển định dạng JPG ↔ PNG ↔ WEBP |
| Dịch PDF | Dịch PDF tiếng Việt → tiếng Anh (Gemini Vision) |
