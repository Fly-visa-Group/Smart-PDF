import { useState, useRef } from 'react';
import { Upload, Download, Image as ImageIcon, RefreshCw, Loader2 } from 'lucide-react';

const API_URL = 'http://localhost:8000';

const PdfToImageWorkspace = ({ initialFiles, onCancel }) => {
  const [file, setFile] = useState(initialFiles?.[0] || null);
  const [fmt, setFmt] = useState('png');
  const [dpi, setDpi] = useState(150);
  const [status, setStatus] = useState(file ? 'idle' : 'idle');
  const [images, setImages] = useState([]);
  const [error, setError] = useState('');
  const inputRef = useRef(null);

  const convert = async (f = file) => {
    if (!f) return;
    setStatus('loading');
    setError('');
    try {
      const form = new FormData();
      form.append('file', f);
      form.append('dpi', dpi);
      form.append('fmt', fmt);
      const res = await fetch(`${API_URL}/api/pdf-to-images`, { method: 'POST', body: form });
      if (!res.ok) throw new Error((await res.json()).detail || 'Lỗi chuyển đổi');
      const data = await res.json();
      setImages(data.images);
      setStatus('done');
    } catch (e) {
      setError(e.message);
      setStatus('error');
    }
  };

  const handleFile = (f) => { setFile(f); setImages([]); setStatus('idle'); };

  const downloadAll = () => {
    images.forEach((img, i) => {
      const a = document.createElement('a');
      a.href = `data:${img.mime};base64,${img.data}`;
      a.download = `${file.name.replace(/\.pdf$/i, '')}_page${img.page}.${img.ext}`;
      a.click();
    });
  };

  return (
    <div style={{ maxWidth: 700, margin: '40px auto', padding: 24 }}>
      <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 20 }}>PDF → Hình ảnh</h2>

      {/* File pick */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 20 }}>
        <button className="btn btn-outline" onClick={() => inputRef.current?.click()}>
          <Upload size={14} style={{ marginRight: 6 }} /> Chọn file PDF
        </button>
        <input ref={inputRef} type="file" accept=".pdf" hidden onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])} />
        {file && <span style={{ fontSize: 13, color: '#4a5568' }}>{file.name}</span>}
      </div>

      {/* Options */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 20 }}>
        <label style={{ fontSize: 13 }}>
          Định dạng:&nbsp;
          <select value={fmt} onChange={e => setFmt(e.target.value)} style={{ padding: '4px 8px', borderRadius: 6, border: '1px solid #e2e8f0' }}>
            <option value="png">PNG</option>
            <option value="jpg">JPG</option>
          </select>
        </label>
        <label style={{ fontSize: 13 }}>
          Chất lượng (DPI):&nbsp;
          <select value={dpi} onChange={e => setDpi(Number(e.target.value))} style={{ padding: '4px 8px', borderRadius: 6, border: '1px solid #e2e8f0' }}>
            <option value={96}>96 (thấp)</option>
            <option value={150}>150 (trung bình)</option>
            <option value={200}>200 (cao)</option>
            <option value={300}>300 (in ấn)</option>
          </select>
        </label>
      </div>

      <div style={{ display: 'flex', gap: 10 }}>
        <button className="btn btn-primary" onClick={() => convert()} disabled={!file || status === 'loading'}>
          {status === 'loading' ? <><Loader2 size={14} className="spin" /> Đang xử lý...</> : <><ImageIcon size={14} /> Chuyển đổi</>}
        </button>
        {images.length > 0 && (
          <button className="btn btn-primary" style={{ background: '#38a169', borderColor: '#38a169' }} onClick={downloadAll}>
            <Download size={14} style={{ marginRight: 6 }} /> Tải tất cả ({images.length} ảnh)
          </button>
        )}
        <button className="btn btn-outline" onClick={onCancel}><RefreshCw size={14} style={{ marginRight: 6 }} /> Chọn file khác</button>
      </div>

      {error && <p style={{ color: '#e53e3e', marginTop: 12, fontSize: 13 }}>{error}</p>}

      {images.length > 0 && (
        <div style={{ marginTop: 24, display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12 }}>
          {images.map(img => (
            <div key={img.page} style={{ border: '1px solid #e2e8f0', borderRadius: 8, overflow: 'hidden', background: '#f7fafc' }}>
              <img src={`data:${img.mime};base64,${img.data}`} alt={`Trang ${img.page}`} style={{ width: '100%', display: 'block' }} />
              <div style={{ padding: '6px 10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 12, color: '#718096' }}>Trang {img.page}</span>
                <a href={`data:${img.mime};base64,${img.data}`} download={`${file.name.replace(/\.pdf$/i, '')}_page${img.page}.${img.ext}`}
                  style={{ fontSize: 12, color: '#3182ce', textDecoration: 'none' }}>
                  <Download size={13} />
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default PdfToImageWorkspace;
