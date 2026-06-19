import React, { useState, useCallback, useRef } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import {
  Upload, Download, Loader2,
  Languages, FileText, AlertCircle, RefreshCw,
  ZoomIn, ZoomOut, Tag
} from 'lucide-react';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

const API_URL = 'http://localhost:8000';

// ── Dropzone ──────────────────────────────────────────────────────────────────
const Dropzone = ({ onFiles }) => {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const files = Array.from(e.dataTransfer.files).filter(f => f.type === 'application/pdf');
    if (files.length) onFiles(files[0]);
  };

  return (
    <div
      className={`translate-dropzone ${dragging ? 'dragging' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
    >
      <input ref={inputRef} type="file" accept=".pdf" hidden onChange={e => e.target.files?.[0] && onFiles(e.target.files[0])} />
      <div className="translate-dropzone-icon">
        <Languages size={48} strokeWidth={1.5} />
      </div>
      <h2 className="translate-dropzone-title">Dịch tài liệu PDF</h2>
      <p className="translate-dropzone-sub">
        Hỗ trợ: Hợp đồng lao động · Học bạ · Giấy kết hôn · Giấy khai sinh · Giấy ủy quyền · Hộ chiếu/Visa
      </p>
      <button className="btn btn-primary translate-upload-btn">
        <Upload size={16} /> Chọn file PDF
      </button>
      <p className="translate-dropzone-hint">hoặc kéo thả file vào đây · Không giới hạn kích thước</p>
    </div>
  );
};

// ── HTML Page Renderer ────────────────────────────────────────────────────────
const HtmlTranslatedPage = ({ html, pageNum, onHtmlEdit, registerPageRef }) => (
  <div className="translated-page-shell" data-page-number={pageNum}>
    <div className="translated-page-label">Trang {pageNum}</div>
    <div
      ref={(el) => registerPageRef(pageNum, el)}
      className="translated-page-content translated-page-content-editable"
      contentEditable={true}
      suppressContentEditableWarning={true}
      style={{ fontFamily: '"Times New Roman", Times, serif', color: '#1a202c' }}
      onBlur={(e) => onHtmlEdit(pageNum, e.currentTarget.innerHTML)}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  </div>
);

// ── Block Renderer (legacy fallback) ─────────────────────────────────────────
const TranslatedPage = ({ pageData, pageNum, onBlockEdit }) => (
  <div className="translated-page-content" style={{ fontFamily: '"Times New Roman", Times, serif', color: '#1a202c' }}>
    {pageData.blocks.map((block, i) => {
      if (block.type === 'table') {
        const borderless = block.borderless;
        const borderStyle = borderless ? 'none' : '1px solid #a0aec0';
        const cellFontSize = block.font_size ? `${block.font_size}pt` : '12pt';
        const colWidths = block.col_widths || null;
        return (
          <div key={i} className="translated-table-wrapper" style={{ margin: borderless ? '3px 0' : '8px 0', overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', border: borderStyle }}>
              <tbody>
                {block.translated_cells.map((row, rIdx) => (
                  <tr key={rIdx} style={{ borderBottom: borderless ? 'none' : '1px solid #a0aec0' }}>
                    {row.map((cell, cIdx) => (
                      <td
                        key={cIdx}
                        contentEditable={true}
                        suppressContentEditableWarning={true}
                        onBlur={(e) => onBlockEdit(pageNum, i, e.target.innerText, rIdx, cIdx)}
                        style={{
                          border: borderStyle,
                          padding: borderless ? '1px 6px 1px 0' : '5px 8px',
                          fontSize: cellFontSize,
                          verticalAlign: 'top',
                          outline: 'none',
                          background: '#fff',
                          whiteSpace: 'pre-wrap',
                          lineHeight: '1.5',
                          width: colWidths ? colWidths[cIdx] : undefined,
                        }}
                      >
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      }

      const isHeading = block.is_heading;
      const align = block.align || 'left';
      const isBold = block.is_bold;
      const fontSize = block.font_size ? `${block.font_size}pt` : (isHeading ? '13pt' : '12pt');
      const marginBottom = block.margin_bottom !== undefined ? `${block.margin_bottom}px` : (isHeading ? '8px' : '4px');
      const marginTop = block.margin_top !== undefined ? `${block.margin_top}px` : '0px';
      const lineHeight = block.font_size && block.font_size >= 16 ? '1.3' : '1.6';

      return (
        <div
          key={i}
          className={`translated-block ${isHeading ? 'translated-heading' : 'translated-para'}`}
          contentEditable={true}
          suppressContentEditableWarning={true}
          onBlur={(e) => onBlockEdit(pageNum, i, e.target.innerText)}
          style={{
            fontSize,
            fontWeight: (isHeading || isBold) ? 'bold' : 'normal',
            textAlign: align,
            marginTop,
            marginBottom,
            lineHeight,
            whiteSpace: 'pre-wrap',
            outline: 'none',
            padding: '1px 2px',
            borderRadius: '3px',
            borderBottom: '1px dashed transparent',
            transition: 'background-color 0.15s ease',
          }}
          onFocus={(e) => { e.target.style.borderBottom = '1px dashed #3182ce'; e.target.style.backgroundColor = '#f7fafc'; }}
          onBlurCapture={(e) => { e.target.style.borderBottom = '1px dashed transparent'; e.target.style.backgroundColor = 'transparent'; }}
        >
          {block.translated}
        </div>
      );
    })}
  </div>
);

// ── Main Component ────────────────────────────────────────────────────────────
const TranslateWorkspace = () => {
  const [file, setFile] = useState(null);
  const [objectUrl, setObjectUrl] = useState(null);
  const [status, setStatus] = useState('idle'); // idle | loading | done | error
  const [errorMsg, setErrorMsg] = useState('');
  const [result, setResult] = useState(null);
  const [pdfNumPages, setPdfNumPages] = useState(null);
  const [pdfScale, setPdfScale] = useState(1.0);
  const [progress, setProgress] = useState(0);
  const [loadingStep, setLoadingStep] = useState('');

  const containerRef = useRef(null);
  const [containerWidth, setContainerWidth] = useState(480);
  const translatedPageRefs = useRef({});

  React.useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      if (entries[0]) {
        setContainerWidth(Math.floor(entries[0].contentRect.width - 32));
      }
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [file, status]);

  const fetchTranslation = async (f) => {
    setStatus('loading');
    setErrorMsg('');
    setProgress(0);
    setLoadingStep('Đang khởi tạo dịch...');

    let currentProgress = 0;
    const interval = setInterval(() => {
      const remaining = 99 - currentProgress;
      const increment = Math.max(0.1, remaining * 0.04);
      currentProgress = Math.min(99, currentProgress + increment);

      const displayProgress = Math.floor(currentProgress);
      setProgress(displayProgress);

      if (displayProgress < 25) {
        setLoadingStep('Đang đọc cấu trúc file PDF...');
      } else if (displayProgress < 50) {
        setLoadingStep('Đang phân tích bảng biểu và căn lề tự động...');
      } else if (displayProgress < 75) {
        setLoadingStep('Đang đối chiếu biểu mẫu dịch chuyên dụng...');
      } else if (displayProgress < 90) {
        setLoadingStep('Đang áp dụng từ điển thuật ngữ Lãnh sự...');
      } else {
        setLoadingStep('Đang hoàn thiện bố cục và đóng gói file Word...');
      }
    }, 250);

    try {
      const formData = new FormData();
      formData.append('file', f);

      const res = await fetch(`${API_URL}/api/translate-pdf/html`, { method: 'POST', body: formData });
      clearInterval(interval);
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Lỗi không xác định' }));
        throw new Error(err.detail);
      }
      const data = await res.json();
      setProgress(100);
      setLoadingStep('Hoàn thành!');

      setTimeout(() => {
        setResult({ ...data, mode: 'html' });
        setStatus('done');
      }, 400);
    } catch (err) {
      clearInterval(interval);
      setErrorMsg(err.message);
      setStatus('error');
    }
  };

  const handleFile = useCallback(async (f) => {
    setFile(f);
    setObjectUrl(URL.createObjectURL(f));
    setResult(null);
    await fetchTranslation(f);
  }, []);

  const handleReset = () => {
    setFile(null);
    setObjectUrl(null);
    setResult(null);
    setStatus('idle');
    setErrorMsg('');
  };

  const downloadTranslation = () => {
    if (!result) return;
    const isHtmlModeLocal = result.mode === 'html';
    let text = `BILINGUAL TRANSLATION — ${result.original_filename}\n`;
    if (!isHtmlModeLocal) {
      text += `Document type: ${result.doc_type_label}  |  Translator: ${(result.translator || 'gemini').toUpperCase()}\n`;
    }
    text += '='.repeat(70) + '\n\n';
    result.pages.forEach(page => {
      text += `--- Page ${page.page_num} ---\n\n`;
      if (isHtmlModeLocal) {
        // Strip HTML tags for plain text export
        const tmp = document.createElement('div');
        const el = translatedPageRefs.current[page.page_num];
        tmp.innerHTML = el ? el.innerHTML : (page.translated_html || '');
        text += (tmp.textContent || tmp.innerText || '') + '\n\n';
      } else {
        page.blocks?.forEach(b => {
          if (b.type === 'table') {
            text += `[TABLE]\n`;
            b.translated_cells.forEach((row, ri) => {
              text += `  Row ${ri + 1}: ${row.join(' | ')}\n`;
            });
            text += '\n';
          } else {
            text += `[VI] ${b.original}\n`;
            text += `[EN] ${b.translated}\n\n`;
          }
        });
      }
    });
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = (file?.name?.replace(/\.pdf$/i, '') || 'translation') + '_bilingual.txt';
    a.click();
  };

  const handleBlockEdit = (pageNum, blockIdx, newText, rIdx = null, cIdx = null) => {
    if (!result) return;
    setResult(prev => {
      const nextResult = JSON.parse(JSON.stringify(prev));
      const page = nextResult.pages.find(p => p.page_num === pageNum);
      if (page) {
        const block = page.blocks[blockIdx];
        if (block) {
          if (block.type === 'table' && rIdx !== null && cIdx !== null) {
            block.translated_cells[rIdx][cIdx] = newText;
          } else {
            block.translated = newText;
          }
        }
      }
      return nextResult;
    });
  };

  const registerPageRef = (pageNum, el) => {
    if (!el) {
      delete translatedPageRefs.current[pageNum];
      return;
    }
    translatedPageRefs.current[pageNum] = el;
  };

  const handleHtmlEdit = (pageNum, newHtml) => {
    setResult(prev => {
      if (!prev) return prev;
      const nextResult = JSON.parse(JSON.stringify(prev));
      const targetPage = nextResult.pages.find(p => p.page_num === pageNum);
      if (targetPage) {
        targetPage.translated_html = newHtml;
      }
      return nextResult;
    });
  };

  const applyEditorCommand = (command, value = null) => {
    document.execCommand(command, false, value);
  };

  const applyLineHeight = (lineHeight) => {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return;

    let node = selection.anchorNode;
    if (!node) return;
    if (node.nodeType === Node.TEXT_NODE) node = node.parentElement;
    if (!node) return;

    const editableRoot = node.closest('.translated-page-content-editable');
    if (!editableRoot) return;

    const block = node.closest('p, div, li, td, th, h1, h2, h3, h4, h5, h6') || node;
    if (block && editableRoot.contains(block)) {
      block.style.lineHeight = lineHeight;
    }
  };

  const downloadPdf = async () => {
    if (!result) return;
    try {
      const mergedResult = JSON.parse(JSON.stringify(result));
      Object.entries(translatedPageRefs.current).forEach(([pageNum, el]) => {
        const page = mergedResult.pages?.find(p => p.page_num === Number(pageNum));
        if (page && el) page.translated_html = el.innerHTML;
      });
      const res = await fetch(`${API_URL}/api/translate-pdf/download-pdf`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ result: mergedResult }),
      });
      if (!res.ok) throw new Error('Không thể tạo file PDF');
      const blob = await res.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = (result.original_filename?.replace(/\.pdf$/i, '') || 'translation') + '_translated.pdf';
      a.click();
    } catch (err) {
      alert(err.message);
    }
  };

  const downloadDocx = async () => {
    if (!result) return;
    try {
      const htmlPages = Object.entries(translatedPageRefs.current).map(([pageNum, el]) => ({
        page_num: Number(pageNum),
        translated_html: el?.innerHTML || '',
      }));

      const mergedResult = JSON.parse(JSON.stringify(result));
      if (htmlPages.length > 0) {
        htmlPages.forEach(({ page_num, translated_html }) => {
          const page = mergedResult.pages?.find((p) => p.page_num === page_num);
          if (page) {
            page.translated_html = translated_html;
          }
        });
      }

      const res = await fetch(`${API_URL}/api/translate-pdf/download-edited-docx`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ result: mergedResult }),
      });
      if (!res.ok) throw new Error('Không thể tải file Word');
      const blob = await res.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = (result.original_filename?.replace(/\.pdf$/i, '') || 'translation') + '_translated.docx';
      a.click();
    } catch (err) {
      alert(err.message);
    }
  };

  if (status === 'idle') return <Dropzone onFiles={handleFile} />;

  if (status === 'loading') {
    const cuteTips = [
      '☕ Hệ thống đang pha một ly tiếng Anh thật mượt cho bạn...',
      '🧠 AI đang cân từng dấu chấm phẩy để bản dịch đẹp hơn...',
      '✨ Chỉnh bố cục để file nhìn chuyên nghiệp như bản công chứng...',
      '🎯 Sắp xong rồi, chuẩn bị tải về nhé!'
    ];
    const tipIndex = Math.min(cuteTips.length - 1, Math.floor(progress / 25));

    return (
      <div className="translate-loading-stage">
        <div className="translate-loading-glow translate-loading-glow-1" />
        <div className="translate-loading-glow translate-loading-glow-2" />

        <div className="translate-loading-card">
          <div className="translate-loading-head">
            <div className="translate-loading-spinner-wrap">
              <Loader2 size={32} className="spin" />
            </div>
            <div>
              <h3 className="translate-loading-title">Đang dịch tài liệu cho bạn ✨</h3>
              <p className="translate-loading-file">{file?.name}</p>
            </div>
          </div>

          <div className="translate-loading-progress-wrap">
            <div className="translate-loading-progress-meta">
              <span>{loadingStep}</span>
              <span>{progress}%</span>
            </div>
            <div className="translate-loading-progress-bar">
              <div className="translate-loading-progress-fill" style={{ width: `${progress}%` }} />
            </div>
          </div>

          <p className="translate-loading-tip">{cuteTips[tipIndex]}</p>

          <div className="translate-loading-skeleton-grid">
            <div className="translate-loading-skeleton-page">
              <div className="translate-loading-skeleton-title">📄 Bản gốc</div>
              <div className="skeleton-line w-90" />
              <div className="skeleton-line w-70" />
              <div className="skeleton-line w-85" />
              <div className="skeleton-line w-60" />
              <div className="skeleton-line w-80" />
            </div>
            <div className="translate-loading-skeleton-page">
              <div className="translate-loading-skeleton-title">🌐 Bản dịch</div>
              <div className="skeleton-line w-80" />
              <div className="skeleton-line w-65" />
              <div className="skeleton-line w-90" />
              <div className="skeleton-line w-70" />
              <div className="skeleton-line w-85" />
            </div>
          </div>

          <div className="translate-loading-bottom">
            <div className="translate-loading-mini-cards">
              <div className="loading-mini-card">
                <div className="loading-mini-emoji">🧩</div>
                <div>
                  <div className="loading-mini-title">Giữ nguyên bố cục</div>
                  <div className="loading-mini-sub">Canh lề · khoảng cách · bảng biểu</div>
                </div>
              </div>
              <div className="loading-mini-card">
                <div className="loading-mini-emoji">📚</div>
                <div>
                  <div className="loading-mini-title">Thuật ngữ chuyên ngành</div>
                  <div className="loading-mini-sub">Ưu tiên văn phong hồ sơ pháp lý</div>
                </div>
              </div>
              <div className="loading-mini-card">
                <div className="loading-mini-emoji">🛡️</div>
                <div>
                  <div className="loading-mini-title">Xử lý an toàn</div>
                  <div className="loading-mini-sub">Tài liệu của bạn đang được xử lý cục bộ</div>
                </div>
              </div>
            </div>

            <div className="translate-loading-fun-strip">
              <span className="fun-dot" />
              <span className="fun-text">Gần xong rồi… chuẩn bị nhận bản dịch đẹp lung linh ✨</span>
              <span className="fun-dot" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="translate-status-screen">
        <AlertCircle size={48} color="#e53e3e" />
        <h3 style={{ color: '#e53e3e' }}>Dịch thất bại</h3>
        <p>{errorMsg}</p>
        <button className="btn btn-outline" onClick={handleReset} style={{ marginTop: 16, display: 'flex', gap: 8 }}>
          <RefreshCw size={15} /> Thử lại
        </button>
      </div>
    );
  }

  const isHtmlMode = result.mode === 'html';

  return (
    <div className="translate-result-container">
      <div className="translate-result-topbar">
        <div className="translate-topbar-left">
          <span className="translate-filename">{result.original_filename}</span>
          <span className="translate-meta">
            {result.total_pages} trang · {isHtmlMode ? '🟣 Gemini HTML' : (result.translator === 'deepl' ? '🔵 DeepL' : '🟢 Google Translate')}
          </span>
        </div>
        <div className="translate-topbar-right">
          <div className="translate-zoom-controls">
            <button className="toolbar-icon-btn" onClick={() => setPdfScale(s => Math.max(0.5, s - 0.2))} title="Thu nhỏ">
              <ZoomOut size={15} />
            </button>
            <span style={{ fontSize: 12, minWidth: 40, textAlign: 'center' }}>{Math.round(pdfScale * 100)}%</span>
            <button className="toolbar-icon-btn" onClick={() => setPdfScale(s => Math.min(2.5, s + 0.2))} title="Phóng to">
              <ZoomIn size={15} />
            </button>
          </div>
          <button className="btn btn-outline" style={{ fontSize: 13, padding: '6px 14px', display: 'flex', gap: 6 }} onClick={handleReset}>
            <RefreshCw size={14} /> Dịch file khác
          </button>
        </div>
      </div>

      <div className="translate-panels">
        <div className="translate-dual-pages-scroll" ref={containerRef}>
          <Document file={objectUrl} onLoadSuccess={({ numPages }) => setPdfNumPages(numPages)}>
            <div className="translate-dual-pages-grid">
              {Array.from({ length: pdfNumPages || 0 }, (_, idx) => {
                const pageNumber = idx + 1;
                const translatedPage = result.pages?.find((p) => p.page_num === pageNumber);

                return (
                  <React.Fragment key={pageNumber}>
                    <div className="translate-panel translate-panel-left">
                      <div className="translate-panel-header">
                        <FileText size={14} /> Bản gốc (Tiếng Việt) · Trang {pageNumber}
                      </div>
                      <div className="translate-panel-scroll">
                        <div className="translate-page-shell">
                          <Page
                            pageNumber={pageNumber}
                            scale={pdfScale}
                            width={Math.min(595, containerWidth)}
                            renderTextLayer={false}
                            renderAnnotationLayer={false}
                          />
                        </div>
                      </div>
                    </div>

                    <div className="translate-panel translate-panel-right">
                      <div className="translate-panel-header">
                        <Languages size={14} /> Bản dịch (English) · Trang {pageNumber}
                      </div>
                      <div className="translate-panel-scroll">
                        {translatedPage ? (
                          isHtmlMode ? (
                            <HtmlTranslatedPage
                              html={translatedPage.translated_html || ''}
                              pageNum={translatedPage.page_num}
                              onHtmlEdit={handleHtmlEdit}
                              registerPageRef={registerPageRef}
                            />
                          ) : (
                            <div className="translated-page-shell">
                              <TranslatedPage
                                pageData={translatedPage}
                                pageNum={translatedPage.page_num}
                                onBlockEdit={handleBlockEdit}
                              />
                            </div>
                          )
                        ) : (
                          <div className="translated-page-shell">
                            <div className="translated-page-content">Không có nội dung cho trang này.</div>
                          </div>
                        )}
                      </div>
                    </div>
                  </React.Fragment>
                );
              })}
            </div>
          </Document>
        </div>
      </div>

      <div className="translate-pager translate-editor-toolbar">
        <button className="btn btn-outline" onClick={() => applyEditorCommand('bold')}>
          <Tag size={14} style={{ marginRight: 6 }} /> Tô đậm
        </button>
        <button className="btn btn-outline" onClick={() => applyLineHeight('1.3')}>Giãn dòng 1.3</button>
        <button className="btn btn-outline" onClick={() => applyLineHeight('1.5')}>Giãn dòng 1.5</button>
        <button className="btn btn-outline" onClick={() => applyLineHeight('1.8')}>Giãn dòng 1.8</button>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="btn btn-primary" style={{ fontSize: 13, padding: '6px 14px', display: 'flex', gap: 6 }} onClick={downloadDocx}>
            <Download size={14} /> Tải DOCX
          </button>
          <button className="btn btn-primary" style={{ fontSize: 13, padding: '6px 14px', display: 'flex', gap: 6, background: '#38a169', borderColor: '#38a169' }} onClick={downloadPdf}>
            <Download size={14} /> Tải PDF
          </button>
          <button className="btn btn-outline" style={{ fontSize: 13, padding: '6px 14px', display: 'flex', gap: 6 }} onClick={downloadTranslation}>
            <Download size={14} /> Tải .txt
          </button>
        </div>
      </div>
    </div>
  );
};

export default TranslateWorkspace;
