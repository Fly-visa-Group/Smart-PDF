# TODO - Translate Workspace Continuous Scroll + Editable Translation

- [x] Refactor `frontend/src/components/TranslateWorkspace.jsx` to render all pages continuously in both original and translated panels.
- [x] Add editable HTML translation blocks with page-level refs and onBlur synchronization.
- [x] Add formatting toolbar actions (bold + line-height presets) for translated HTML editor.
- [x] Update download payload to include edited HTML pages so DOCX export can consume user edits.
- [x] Update `frontend/src/index.css` for multi-page continuous layout and editor toolbar styling.
- [x] Verify no broken references to removed pager/currentPage-only rendering flow.
- [x] Make left sidebar fixed width (no expand/collapse on hover).
- [x] Make translate dropzone full workspace area.
