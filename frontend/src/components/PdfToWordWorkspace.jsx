import React, { useState, useRef } from 'react';
import {
  FileText, Download, RefreshCw, Loader2,
  AlertCircle, FileWarning, UploadCloud, CheckCircle2,
} from 'lucide-react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const PdfToWordWorkspace = () => {
  const [file, setFile]               = useState(null);
  const [status, setStatus]           = useState('idle'); // idle|loading|done|error
  const [progress, setProgress]       = useState(0);
  const [loadingStep, setLoadingStep] = useState('');
  const [errorMsg, setErrorMsg]       = useState('');
  const [resultBlob, setResultBlob]   = useState(null);
  const [resultName, setResultName]   = useState('');
  const [dragging, setDragging]       = useState(false);
  const inputRef = useRef(null);

  const formatSize = (b) => {
    if (!b) return '0 B';
    const k = 1024, s = ['B','KB','MB','GB'];
    const i = Math.floor(Math.log(b) / Math.log(k));
    return (b / Math.pow(k, i)).toFixed(1) + ' ' + s[i];
  };

  const isPdf = (f) => f && f.name.toLowerCase().endsWith('.pdf');

  // ── convert ─────────────────────────────────────────────────────────────────
  const convert = async (f) => {
    if (!f || !isPdf(f)) return;
    setFile(f);
    setStatus('loading');
    setProgress(0);
    setErrorMsg('');

    let p = 0;
    const steps = [
      { t: 20, msg: 'Đang phân tích cấu trúc PDF...' },
      { t: 50, msg: 'Đang nhận diện bảng biểu và định dạng...' },
      { t: 80, msg: 'Đang tạo file Word...' },
      { t: 98, msg: 'Hoàn thiện tài liệu...' },
    ];
    const timer = setInterval(() => {
      if (p < 25) p += Math.floor(Math.random() * 6) + 4;
      else if (p < 70) p += Math.floor(Math.random() * 3) + 1;
      else if (p < 97) p += 1;
      if (p > 97) p = 97;
      setProgress(p);
      setLoadingStep((steps.find(s => p < s.t) || steps[3]).msg);
    }, 200);

    try {
      const fd = new FormData();
      fd.append('file', f);
      const res = await fetch(`${API_URL}/api/pdf-to-word`, { method: 'POST', body: fd });
      clearInterval(timer);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Chuyển đổi thất bại');
      }
      const blob = await res.blob();
      setResultBlob(blob);
      setResultName(f.name.replace(/\.pdf$/i, '') + '.docx');
      setProgress(100);
      setTimeout(() => setStatus('done'), 350);
    } catch (err) {
      clearInterval(timer);
      setErrorMsg(err.message);
      setStatus('error');
    }
  };

  // ── file pick handlers ───────────────────────────────────────────────────────
  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (!f) return;
    if (!isPdf(f)) { alert('Vui lòng chọn file PDF'); return; }
    convert(f);
  };

  const handleChange = (e) => {
    const f = e.target.files?.[0];
    if (f) convert(f);
  };

  const reset = () => {
    setFile(null);
    setStatus('idle');
    setResultBlob(null);
    setResultName('');
    setErrorMsg('');
    setProgress(0);
  };

  const download = () => {
    if (!resultBlob) return;
    const a = document.createElement('a');
    a.href = URL.createObjectURL(resultBlob);
    a.download = resultName;
    a.click();
  };

  // ── idle: dropzone ───────────────────────────────────────────────────────────
  if (status === 'idle') return (
    <div
      className={`dropzone${dragging ? ' active' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={(e) => { if (e.currentTarget.contains(e.relatedTarget)) return; setDragging(false); }}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      style={{ cursor: 'pointer' }}
    >
      <input ref={inputRef} type="file" accept=".pdf" hidden onChange={handleChange} />
      <UploadCloud className="dropzone-icon" size={60} />
      <button className="dropzone-btn" onClick={(e) => { e.stopPropagation(); inputRef.current?.click(); }}>
        Chọn file PDF
      </button>
      <div className="dropzone-hint">hoặc kéo thả file PDF vào đây</div>
      <div className="dropzone-formats">
        Định dạng hỗ trợ:&nbsp;
        <span className="format-badge ml-1" style={{ background: '#fee2e2', color: '#ef4444' }}>PDF</span>
      </div>
    </div>
  );

  // ── loading ──────────────────────────────────────────────────────────────────
  if (status === 'loading') return (
    <div style={{ maxWidth: 500, margin: '80px auto', padding: 36, background: '#fff', borderRadius: 12, boxShadow: '0 4px 20px rgba(0,0,0,0.08)', textAlign: 'center' }}>
      <Loader2 size={44} style={{ color: '#0062ff', margin: '0 auto 20px', display: 'block', animation: 'spin 1.5s linear infinite' }} />
      <h3 style={{ fontSize: 18, fontWeight: 600, color: '#2d3748', marginBottom: 6 }}>Đang chuyển đổi PDF sang Word...</h3>
      <p style={{ fontSize: 13, color: '#718096', wordBreak: 'break-all', marginBottom: 28 }}>{file?.name}</p>
      <div style={{ width: '100%', height: 10, background: '#edf2f7', borderRadius: 5, overflow: 'hidden', marginBottom: 10 }}>
        <div style={{ width: `${progress}%`, height: '100%', background: 'linear-gradient(90deg,#0062ff,#00c6ff)', transition: 'width 0.25s ease-out', borderRadius: 5 }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, color: '#4a5568', fontWeight: 500 }}>
        <span>{loadingStep}</span>
        <span>{progress}%</span>
      </div>
    </div>
  );

  // ── error ────────────────────────────────────────────────────────────────────
  if (status === 'error') return (
    <div style={{ maxWidth: 500, margin: '80px auto', padding: 36, background: '#fff', borderRadius: 12, boxShadow: '0 4px 20px rgba(0,0,0,0.08)', textAlign: 'center' }}>
      <AlertCircle size={48} style={{ color: '#e53e3e', margin: '0 auto 16px' }} />
      <h3 style={{ fontSize: 18, fontWeight: 600, color: '#e53e3e', marginBottom: 8 }}>Chuyển đổi thất bại</h3>
      <p style={{ fontSize: 13, color: '#4a5568', marginBottom: 24 }}>{errorMsg}</p>
      <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
        <button className="btn btn-primary" style={{ display: 'flex', alignItems: 'center', gap: 6 }} onClick={() => convert(file)}>
          <RefreshCw size={15} /> Thử lại
        </button>
        <button className="btn btn-outline" onClick={reset}>Chọn file khác</button>
      </div>
    </div>
  );

  // ── done ─────────────────────────────────────────────────────────────────────
  return (
    <div style={{ maxWidth: 520, margin: '80px auto', padding: 36, background: '#fff', borderRadius: 14, boxShadow: '0 4px 24px rgba(0,0,0,0.09)', textAlign: 'center' }}>
      {/* Icon */}
      <div style={{ width: 70, height: 70, borderRadius: '50%', background: '#ebf8ff', color: '#0062ff', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 18px' }}>
        <CheckCircle2 size={38} />
      </div>

      <h3 style={{ fontSize: 20, fontWeight: 700, color: '#1a202c', marginBottom: 4 }}>Chuyển đổi thành công!</h3>
      <p style={{ fontSize: 13, color: '#718096', marginBottom: 24, wordBreak: 'break-all' }}>{file?.name}</p>

      {/* File card */}
      <div style={{ background: '#f7fafc', borderRadius: 10, padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 14, marginBottom: 28, textAlign: 'left' }}>
        <div style={{ width: 44, height: 44, background: '#dbeafe', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <FileText size={22} style={{ color: '#2563eb' }} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#2d3748', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {resultName}
          </div>
          <div style={{ fontSize: 12, color: '#718096', marginTop: 3 }}>
            Microsoft Word (.docx) · {formatSize(resultBlob?.size)}
          </div>
        </div>
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
        <button className="btn btn-primary"
          style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '10px 24px', background: '#0062ff', fontSize: 14 }}
          onClick={download}>
          <Download size={16} /> Tải file Word
        </button>
        <button className="btn btn-outline"
          style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '10px 18px', fontSize: 14 }}
          onClick={reset}>
          <RefreshCw size={14} /> Chuyển file khác
        </button>
      </div>
    </div>
  );
};

export default PdfToWordWorkspace;
