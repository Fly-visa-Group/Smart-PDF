import { useState, useRef } from 'react';
import { Upload, Download, RefreshCw, Loader2, FileOutput } from 'lucide-react';

const API_URL = 'http://localhost:8000';

const WordToPdfWorkspace = ({ initialFiles, onCancel }) => {
  const [file, setFile] = useState(initialFiles?.[0] || null);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const inputRef = useRef(null);

  const handleFile = (f) => { setFile(f); setStatus('idle'); setError(''); };

  const convert = async () => {
    if (!file) return;
    setStatus('loading'); setError('');
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${API_URL}/api/word-to-pdf`, { method: 'POST', body: form });
      if (!res.ok) throw new Error((await res.json()).detail || 'Lỗi chuyển đổi');
      const blob = await res.blob();
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = file.name.replace(/\.(docx?|doc)$/i, '') + '.pdf';
      a.click();
      setStatus('done');
    } catch (e) {
      setError(e.message); setStatus('error');
    }
  };

  return (
    <div style={{ maxWidth: 500, margin: '80px auto', padding: 32, background: '#fff', borderRadius: 16, boxShadow: '0 4px 20px rgba(0,0,0,0.08)', textAlign: 'center' }}>
      <FileOutput size={48} color="#3182ce" style={{ marginBottom: 16 }} />
      <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>Word → PDF</h2>
      <p style={{ fontSize: 13, color: '#718096', marginBottom: 24 }}>Chuyển file .docx / .doc sang PDF giữ nguyên định dạng</p>

      <div style={{ display: 'flex', gap: 12, justifyContent: 'center', alignItems: 'center', marginBottom: 20 }}>
        <button className="btn btn-outline" onClick={() => inputRef.current?.click()}>
          <Upload size={14} style={{ marginRight: 6 }} /> Chọn file Word
        </button>
        <input ref={inputRef} type="file" accept=".doc,.docx" hidden onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])} />
      </div>

      {file && (
        <div style={{ background: '#f7fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: '10px 16px', marginBottom: 20, fontSize: 13, color: '#4a5568' }}>
          📄 {file.name} &nbsp;·&nbsp; {(file.size / 1024).toFixed(0)} KB
        </div>
      )}

      <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
        <button className="btn btn-primary" onClick={convert} disabled={!file || status === 'loading'}>
          {status === 'loading'
            ? <><Loader2 size={14} className="spin" /> Đang chuyển đổi...</>
            : <><Download size={14} /> Chuyển & Tải về PDF</>}
        </button>
        <button className="btn btn-outline" onClick={onCancel}><RefreshCw size={14} style={{ marginRight: 6 }} /> Chọn lại</button>
      </div>

      {status === 'done' && <p style={{ color: '#38a169', marginTop: 16, fontSize: 13 }}>✓ Đã tải về thành công!</p>}
      {error && <p style={{ color: '#e53e3e', marginTop: 16, fontSize: 13 }}>{error}</p>}
    </div>
  );
};

export default WordToPdfWorkspace;
