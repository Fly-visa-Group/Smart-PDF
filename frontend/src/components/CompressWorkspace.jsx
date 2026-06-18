import React, { useState } from 'react';
import { FileDown, RefreshCw, Loader2, Minimize2, Settings, Zap } from 'lucide-react';

const API_URL = 'http://localhost:8000';

const CompressWorkspace = ({ initialFiles, onCancel }) => {
  const file = initialFiles[0]; // Compress tool processes 1 file at a time
  const [level, setLevel] = useState('medium'); // medium | extreme
  const [status, setStatus] = useState('idle'); // idle | loading | done | error
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');

// Validate file type - only PDF allowed
  const isPdfFile = file && file.name.toLowerCase().endsWith('.pdf');

  // Show invalid file type error - only check once, not in render loop
  if (file && !isPdfFile && status === 'idle') {
    return (
      <div style={{ maxWidth: 500, margin: '80px auto', padding: 30, background: '#fff', borderRadius: 12, boxShadow: '0 4px 20px rgba(0,0,0,0.08)', textAlign: 'center' }}>
        <div style={{ width: 64, height: 64, background: '#fff5f5', color: '#e53e3e', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 20px' }}>
          <Minimize2 size={32} />
        </div>
        <h3 style={{ fontSize: 19, fontWeight: 700, color: '#2d3748', marginBottom: 8 }}>File không hợp lệ!</h3>
        <p style={{ fontSize: 13, color: '#718096', wordBreak: 'break-all', marginBottom: 16 }}>File: <strong>{file.name}</strong></p>
        <p style={{ fontSize: 14, color: '#e53e3e', marginBottom: 24 }}>
          Công cụ <strong>Nén PDF</strong> chỉ hỗ trợ file PDF (.pdf).<br/> File bạn chọn là <strong>{file.name.split('.').pop().toUpperCase()}</strong> - không thể nén được!
        </p>
        <button className="btn btn-outline" onClick={onCancel}>
          Chọn file PDF khác
        </button>
      </div>
    );
  }

  const formatSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const handleCompress = async () => {
    if (!file) return;
    setStatus('loading');
    setProgress(15);
    setErrorMsg('');

    // Smooth progress simulation
    let currentProgress = 15;
    const interval = setInterval(() => {
      if (currentProgress < 85) {
        currentProgress += Math.floor(Math.random() * 4) + 1;
      } else if (currentProgress < 98) {
        currentProgress += 1;
      }
      setProgress(currentProgress);
    }, 150);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('level', level);

      const res = await fetch(`${API_URL}/api/compress`, {
        method: 'POST',
        body: formData,
      });

clearInterval(interval);

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Nén file thất bại. Vui lòng thử lại.');
      }

      const blob = await res.blob();
      setProgress(100);

      setTimeout(() => {
        setResult({
          blob,
          originalSize: file.size,
          compressedSize: blob.size,
          savings: ((file.size - blob.size) / file.size * 100).toFixed(0),
          filename: `compressed_${file.name}`,
        });
        setStatus('done');
      }, 400);

    } catch (err) {
      clearInterval(interval);
      setErrorMsg(err.message);
      setStatus('error');
    }
  };

  const downloadFile = () => {
    if (!result) return;
    const a = document.createElement('a');
    a.href = URL.createObjectURL(result.blob);
    a.download = result.filename;
    a.click();
  };

  // ── Loading Status ──────────────────────────────────────────────────────────
  if (status === 'loading') {
    return (
      <div style={{ maxWidth: 500, margin: '80px auto', padding: 30, background: '#fff', borderRadius: 12, boxShadow: '0 4px 20px rgba(0,0,0,0.08)', textAlign: 'center' }}>
        <Loader2 size={40} className="spin" style={{ color: '#3182ce', animation: 'spin 1.5s linear infinite', margin: '0 auto 20px' }} />
        <h3 style={{ fontSize: 18, fontWeight: 600, color: '#2d3748', marginBottom: 8 }}>Đang tối ưu dung lượng PDF...</h3>
        <p style={{ fontSize: 13, color: '#718096', wordBreak: 'break-all', marginBottom: 24 }}>{file.name}</p>
        <div style={{ width: '100%', height: 10, background: '#edf2f7', borderRadius: 5, overflow: 'hidden', marginBottom: 12 }}>
          <div style={{ width: `${progress}%`, height: '100%', background: 'linear-gradient(90deg, #3182ce, #319795)', transition: 'width 0.2s ease-out', borderRadius: 5 }} />
        </div>
        <div style={{ fontSize: 14, color: '#4a5568', fontWeight: 500 }}>{progress}%</div>
      </div>
    );
  }

  // ── Success Results ────────────────────────────────────────────────────────
  if (status === 'done' && result) {
    return (
      <div style={{ maxWidth: 500, margin: '80px auto', padding: 30, background: '#fff', borderRadius: 12, boxShadow: '0 4px 20px rgba(0,0,0,0.08)', textAlign: 'center' }}>
        <div style={{ width: 64, height: 64, background: '#e6fffa', color: '#319795', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 20px' }}>
          <Minimize2 size={32} />
        </div>
        <h3 style={{ fontSize: 19, fontWeight: 700, color: '#2d3748', marginBottom: 8 }}>Tối ưu dung lượng hoàn tất!</h3>
        <p style={{ fontSize: 13, color: '#718096', wordBreak: 'break-all', marginBottom: 24 }}>{file.name}</p>

        {/* Compression Statistics Container */}
        <div style={{ background: '#f7fafc', padding: 20, borderRadius: 8, display: 'flex', justifyContent: 'space-around', alignItems: 'center', marginBottom: 24 }}>
          <div>
            <span style={{ display: 'block', fontSize: 12, color: '#718096' }}>Dung lượng gốc</span>
            <strong style={{ fontSize: 16, color: '#4a5568' }}>{formatSize(result.originalSize)}</strong>
          </div>
          <div style={{ height: 30, width: 1, background: '#e2e8f0' }} />
          <div>
            <span style={{ display: 'block', fontSize: 12, color: '#718096' }}>Dung lượng nén</span>
            <strong style={{ fontSize: 16, color: '#2b6cb0' }}>{formatSize(result.compressedSize)}</strong>
          </div>
          <div style={{ height: 30, width: 1, background: '#e2e8f0' }} />
          <div style={{ background: '#319795', color: '#fff', padding: '6px 12px', borderRadius: 6 }}>
            <span style={{ display: 'block', fontSize: 10 }}>Đã giảm</span>
            <strong style={{ fontSize: 16 }}>-{result.savings}%</strong>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
          <button className="btn btn-primary" style={{ display: 'flex', alignItems: 'center', gap: 6 }} onClick={downloadFile}>
            <FileDown size={16} /> Tải file đã nén
          </button>
          <button className="btn btn-outline" style={{ display: 'flex', alignItems: 'center', gap: 6 }} onClick={onCancel}>
            <RefreshCw size={16} /> Nén file khác
          </button>
        </div>
      </div>
    );
  }

  // ── Error screen ───────────────────────────────────────────────────────────
  if (status === 'error') {
    return (
      <div style={{ maxWidth: 500, margin: '80px auto', padding: 30, background: '#fff', borderRadius: 12, boxShadow: '0 4px 20px rgba(0,0,0,0.08)', textAlign: 'center' }}>
        <h3 style={{ color: '#e53e3e', marginBottom: 12 }}>Lỗi tối ưu dung lượng</h3>
        <p style={{ color: '#4a5568', marginBottom: 24 }}>{errorMsg}</p>
        <button className="btn btn-outline" onClick={() => setStatus('idle')}>Thử lại</button>
      </div>
    );
  }

  // ── Options Configuration Screen (Idle) ────────────────────────────────────
  return (
    <div style={{ maxWidth: 550, margin: '60px auto', padding: 30, background: '#fff', borderRadius: 12, boxShadow: '0 4px 25px rgba(0,0,0,0.06)' }}>
      <h3 style={{ fontSize: 19, fontWeight: 700, color: '#2d3748', textAlign: 'center', marginBottom: 6 }}>Nén dung lượng PDF</h3>
      <p style={{ fontSize: 13, color: '#718096', textAlign: 'center', marginBottom: 24 }}>
        Tải lên: <strong style={{ color: '#4a5568' }}>{file.name}</strong> ({formatSize(file.size)})
      </p>

      {/* Mode selectors */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginBottom: 30 }}>
        {/* Option 1: Medium */}
        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            padding: 20,
            borderRadius: 8,
            border: `2px solid ${level === 'medium' ? '#3182ce' : '#e2e8f0'}`,
            background: level === 'medium' ? '#f7fafc' : '#fff',
            cursor: 'pointer',
            transition: 'all 0.15s ease'
          }}
          onClick={() => setLevel('medium')}
        >
          <input type="radio" checked={level === 'medium'} onChange={() => {}} style={{ cursor: 'pointer' }} />
          <div style={{ width: 44, height: 44, background: '#ebf8ff', color: '#3182ce', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Settings size={22} />
          </div>
          <div style={{ flex: 1 }}>
            <strong style={{ display: 'block', fontSize: 15, color: '#2d3748' }}>Nén vừa (Khuyên dùng)</strong>
            <span style={{ fontSize: 12, color: '#718096' }}>Giảm kích thước đáng kể nhưng vẫn đảm bảo chữ viết cực kỳ sắc nét.</span>
          </div>
        </label>

{/* Option 2: Extreme */}
        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            padding: 20,
            borderRadius: 8,
            border: `2px solid ${level === 'extreme' ? '#e53e3e' : '#e2e8f0'}`,
            background: level === 'extreme' ? '#fff5f5' : '#fff',
            cursor: 'pointer',
            transition: 'all 0.15s ease'
          }}
          onClick={() => setLevel('extreme')}
        >
          <input type="radio" checked={level === 'extreme'} onChange={() => {}} style={{ cursor: 'pointer' }} />
          <div style={{ width: 44, height: 44, background: '#fff5f5', color: '#e53e3e', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Zap size={22} />
          </div>
          <div style={{ flex: 1 }}>
            <strong style={{ display: 'block', fontSize: 15, color: '#2d3748' }}>Nén cực mạnh</strong>
            <span style={{ fontSize: 12, color: '#718096' }}>Giảm dung lượng xuống mức tối đa (thích hợp để up lên các trang web nộp hồ sơ giới hạn dung lượng thấp).</span>
          </div>
        </label>

        {/* Option 3: Ultra - New option for maximum compression (~2MB target) */}
        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            padding: 20,
            borderRadius: 8,
            border: `2px solid ${level === 'ultra' ? '#553c9a' : '#e2e8f0'}`,
            background: level === 'ultra' ? '#faf5ff' : '#fff',
            cursor: 'pointer',
            transition: 'all 0.15s ease'
          }}
          onClick={() => setLevel('ultra')}
        >
          <input type="radio" checked={level === 'ultra'} onChange={() => {}} style={{ cursor: 'pointer' }} />
          <div style={{ width: 44, height: 44, background: '#faf5ff', color: '#553c9a', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Zap size={22} />
          </div>
          <div style={{ flex: 1 }}>
            <strong style={{ display: 'block', fontSize: 15, color: '#2d3748' }}>Nén siêu tối ưu (Target ~2MB)</strong>
            <span style={{ fontSize: 12, color: '#718096' }}>Giảm dung lượng tối đa, phù hợp khi cần file dưới 3MB để upload lên website.</span>
          </div>
        </label>
      </div>

      <div style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
        <button className="btn btn-primary" style={{ padding: '10px 24px' }} onClick={handleCompress}>
          Bắt đầu nén file
        </button>
        <button className="btn btn-outline" style={{ padding: '10px 24px' }} onClick={onCancel}>
          Hủy bỏ
        </button>
      </div>
    </div>
  );
};

export default CompressWorkspace;
