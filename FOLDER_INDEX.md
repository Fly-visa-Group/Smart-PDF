# SmartPDF Folder Index

Generated on: 2026-06-23
Root: `D:\Fly_Visa\SmartPDF`

## Top-level
- `.blackboxcli/` — Blackbox CLI local settings
- `.claude/` — Claude local settings
- `backend/` — Python backend (API + PDF/translation services)
- `frontend/` — Vite/React frontend app
- `.gitignore` — Git ignore rules
- `CLAUDE.md` — Agent instructions/context
- `README.md` — Project overview
- `TODO.md` — Task notes

## Backend (`backend/`)
- `main.py` — Backend entry/API routes
- `requirements.txt` — Python dependencies
- `services/` — Core business logic
  - `pdf_compressor.py` — Compress PDF
  - `pdf_merger.py` — Merge PDFs
  - `pdf_page_merger.py` — Merge selected pages
  - `pdf_to_word.py` — PDF to Word conversion
  - `translation/` — Translation pipeline
    - `engine.py` — Translation engine integration
    - `extractor.py`, `html_extractor.py` — Content extraction
    - `html_translator.py`, `template_translator.py` — Translation/rendering logic
    - `docx_builder.py` — Build DOCX output
    - `document_detector.py` — Document type detection
    - `glossaries/` — Domain glossaries
      - `birth_cert.py`, `marriage_cert.py`, `consular.py`, `employment.py`, `school_transcript.py`, `general_legal.py`, `base.py`

## Frontend (`frontend/`)
- `package.json` — JS dependencies and scripts
- `vite.config.js` — Vite config
- `eslint.config.js` — Lint config
- `index.html` — App shell
- `src/` — React source
  - `main.jsx`, `App.jsx`
  - `index.css`
  - `pages/` — `Home.jsx`, `ToolPage.jsx`
  - `components/` — Workspaces and UI components:
    - `MergeWorkspace.jsx`, `SplitWorkspace.jsx`, `CompressWorkspace.jsx`
    - `PdfToWordWorkspace.jsx`, `WordToPdfWorkspace.jsx`
    - `PdfToImageWorkspace.jsx`, `ImageConvertWorkspace.jsx`
    - `TranslateWorkspace.jsx`
    - `Header.jsx`, `Layout.jsx`, `Sidebar.jsx`, `PdfRenderer.jsx`, `MergeResult.jsx`
  - `assets/` — UI images/icons
- `public/` — Static assets and sample PDFs
- `dist/` — Built frontend artifacts

## Notable generated/temporary artifacts
- `__pycache__/` folders under backend
- `frontend/dist/` build output

## Quick map by concern
- **API/backend runtime:** `backend/main.py`
- **PDF ops:** `backend/services/pdf_*.py`
- **Translation core:** `backend/services/translation/`
- **Frontend routing/views:** `frontend/src/pages/`
- **Frontend tool UIs:** `frontend/src/components/*Workspace.jsx`
- **Build/deps (frontend):** `frontend/package.json`
- **Build/deps (backend):** `backend/requirements.txt`
