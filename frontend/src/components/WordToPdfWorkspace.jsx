import { useState, useRef, useEffect } from 'react';
import { Upload, Download, RefreshCw, Loader2, FileOutput, AlertCircle, Eye, FileWarning } from 'lucide-react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const WordToPdfWorkspace = ({ initialFiles, onCancel }) => {
  const [file, setFile] = useState(initialFiles?.[0] || null);
  const [status, setStatus] = useState('idle');   // idle | loading | done | error
  const [error, setError] = useState('');
  const [resultBlob, setResultBlob] = useState(null);
  const [resultUrl, setResultUrl] = useState(null);
  const [resultFilename, setResultFilename] = useState('');
  const inputRef = useRef(null);
  const hasStarted = useRef(false);

  const isWord = file && /\.(docx?|doc)$/i.test(file.name);

  const formatSize = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const handleFile = (f) => {
    setFile(f);
    setStatus('idle');
    setError('');
    setResultBlob(null);
    if (resultUrl) { URL.revokeObjectURL(resultUrl); setResultUrl(null); }
    hasStarted.current = false;
  };

  const convert = async () => {
    if (!file || !isWord) return;
    setStatus('loading');
    setError('');
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${API_URL}/api/word-to-pdf`, { method: 'POST', body: form });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || 'Lỗi chuyển đổi');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      setResultBlob(blob);
      setResultUrl(url);
      setResultFilename(file.name.replace(/\.(docx?|doc)$/i, '') + '.pdf');
      setStatus('done');
    } catch (e) {
      setError(e.message);
      setStatus('error');
    }
  };

  useEffect(() => {
    if (file && isWord && status === 'idle' && !hasStarted.current) {
      hasStarted.current = true;
      convert();
    }
    return () => { if (resultUrl) URL.revokeObjectURL(resultUrl); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const download = () => {
    if (!resultBlob) return;
    const a = document.createElement('a');
    a.href = URL.createObjectURL(resultBlob);
    a.download = resultFilename;
    a.click();
  };

  // ── No file ──────────────────────────────────────────────────────────────────
  if (!file) return (
    <div style={{ maxWidth: 500, margin: '80px auto', padding: 30, background: '#fff', borderRadius: 12, boxShadow: '0 4px 20px rgba(0,0,0,0.08)', textAlign: 'center' }}>
      <FileWarning size={48} style={{ color: '#e53e3e', margin: '0 auto 16px' }} />
      <h3 style={{ fontSize: 18, color: '#2d3748', marginBottom: 8 }}>Chưa chọn file</h3>
      <button className="btn btn-outline" onClick={onCancel}>Quay lại</button>
    </div>
  );

  // ── Wrong type ───────────────────────────────────────────────────────────────
  if (!isWord) return (
    <div style={{ maxWidth: 500, margin: '80px auto', padding: 30, background: '#fff', borderRadius: 12, boxShadow: '0 4px 20px rgba(0,0,0,0.08)', textAlign: 'center' }}>
      <FileWarning size={48} style={{ color: '#e53e3e', margin: '0 auto 16px' }} />
      <h3 style={{ fontSize: 18, color: '#2d3748', marginBottom: 8 }}>File không hợp lệ</h3>
      <p style={{ color: '#e53e3e', marginBottom: 20 }}>Chỉ hỗ trợ file <strong>.docx / .doc</strong></p>
      <button className="btn btn-outline" onClick={onCancel}>Chọn file khác</button>
    </div>
  );

  // ── Loading ──────────────────────────────────────────────────────────────────
  if (status === 'loading') return (
    <div style={{ maxWidth: 500, margin: '80px auto', padding: 36, background: '#fff', borderRadius: 12, boxShadow: '0 4px 20px rgba(0,0,0,0.08)', textAlign: 'center' }}>
      <Loader2 size={44} style={{ color: '#0062ff', margin: '0 auto 20px', display: 'block', animation: 'spin 1.5s linear infinite' }} />
      <h3 style={{ fontSize: 18, fontWeight: 600, color: '#2d3748', marginBottom: 6 }}>Đang chuyển đổi Word sang PDF...</h3>
      <p style={{ fontSize: 13, color: '#718096', wordBreak: 'break-all' }}>{file.name}</p>
    </div>
  );

  // ── Error ────────────────────────────────────────────────────────────────────
  if (status === 'error') return (
    <div style={{ maxWidth: 500, margin: '80px auto', padding: 36, background: '#fff', borderRadius: 12, boxShadow: '0 4px 20px rgba(0,0,0,0.08)', textAlign: 'center' }}>
      <AlertCircle size={48} style={{ color: '#e53e3e', margin: '0 auto 16px' }} />
      <h3 style={{ fontSize: 18, fontWeight: 600, color: '#e53e3e', marginBottom: 8 }}>Chuyển đổi thất bại</h3>
      <p style={{ fontSize: 13, color: '#4a5568', marginBottom: 24 }}>{error}</p>
      <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
        <button className="btn btn-primary" style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          onClick={() => { hasStarted.current = false; convert(); }}>
          <RefreshCw size={15} /> Thử lại
        </button>
        <button className="btn btn-outline" onClick={onCancel}>Chọn file khác</button>
      </div>
    </div>
  );

  // ── Done: topbar + PDF preview ───────────────────────────────────────────────
  if (status === 'done') return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>

      {/* Top bar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 24px', background: '#fff',
        borderBottom: '1px solid #e2e8f0', flexShrink: 0, gap: 16, flexWrap: 'wrap',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
          <div style={{ width: 36, height: 36, background: '#fee2e2', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <FileOutput size={18} style={{ color: '#dc2626' }} />
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#1a202c', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: 320 }}>
              {resultFilename}
            </div>
            <div style={{ fontSize: 12, color: '#718096' }}>
              {formatSize(resultBlob?.size)} · PDF Document
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 10, flexShrink: 0 }}>
          <button
            className="btn btn-primary"
            style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '8px 18px', fontSize: 13 }}
            onClick={download}
          >
            <Download size={15} /> Tải file PDF
          </button>
          <button
            className="btn btn-outline"
            style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '8px 16px', fontSize: 13 }}
            onClick={() => { handleFile(null); onCancel?.(); }}
          >
            <RefreshCw size={14} /> Chuyển file khác
          </button>
        </div>
      </div>

      {/* Preview area */}
      <div style={{ flex: 1, overflow: 'hidden', background: '#f1f5f9', display: 'flex', flexDirection: 'column', minHeight: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '14px 24px 0', color: '#64748b', fontSize: 13, fontWeight: 500 }}>
          <Eye size={15} />
          Xem trước tài liệu PDF
        </div>
        <div style={{ flex: 1, padding: '12px 16px 16px', minHeight: 0 }}>
          <iframe
            src={resultUrl}
            title="PDF Preview"
            style={{
              width: '100%',
              height: '100%',
              border: 'none',
              borderRadius: 4,
              boxShadow: '0 2px 16px rgba(0,0,0,0.10)',
              background: '#fff',
              minHeight: 500,
            }}
          />
        </div>
      </div>
    </div>
  );

  // ── Idle fallback ─────────────────────────────────────────────────────────────
  return (
    <div style={{ maxWidth: 500, margin: '60px auto', padding: 36, background: '#fff', borderRadius: 12, boxShadow: '0 4px 25px rgba(0,0,0,0.06)', textAlign: 'center' }}>
      <FileOutput size={40} color="#dc2626" style={{ margin: '0 auto 16px' }} />
      <h3 style={{ fontSize: 19, fontWeight: 700, color: '#2d3748', marginBottom: 6 }}>Word sang PDF</h3>
      <p style={{ fontSize: 13, color: '#718096', marginBottom: 24 }}>
        File: <strong style={{ color: '#4a5568' }}>{file.name}</strong> ({formatSize(file.size)})
      </p>
      <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginBottom: 16 }}>
        <button className="btn btn-primary" style={{ padding: '10px 28px', fontSize: 14 }} onClick={convert}>
          Chuyển đổi ngay
        </button>
        <button className="btn btn-outline" style={{ padding: '10px 20px', fontSize: 14 }} onClick={() => inputRef.current?.click()}>
          <Upload size={14} style={{ marginRight: 6 }} /> Đổi file
        </button>
        <button className="btn btn-outline" style={{ padding: '10px 20px', fontSize: 14 }} onClick={onCancel}>
          Hủy
        </button>
      </div>
      <input ref={inputRef} type="file" accept=".doc,.docx" hidden onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])} />
    </div>
  );
};

export default WordToPdfWorkspace;
