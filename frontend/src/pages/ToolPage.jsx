import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { UploadCloud, ChevronDown } from 'lucide-react';

import MergeWorkspace from '../components/MergeWorkspace';
import PdfToWordWorkspace from '../components/PdfToWordWorkspace';
import TranslateWorkspace from '../components/TranslateWorkspace';
import CompressWorkspace from '../components/CompressWorkspace';

const ToolPage = () => {
  const { toolId } = useParams();
  const [isDragActive, setIsDragActive] = useState(false);
  const [files, setFiles] = useState([]);

  const toolConfig = {
    'merge': { title: 'Gộp PDF', formats: ['PDF'] },
    'compress': { title: 'Nén PDF', formats: ['PDF'] },
    'split': { title: 'Cắt PDF', formats: ['PDF'] },
    'pdf-to-word': { title: 'PDF sang Word', formats: ['PDF'] },
    'pdf-to-image': { title: 'PDF sang Hình ảnh', formats: ['PDF'] },
    'translate': { title: 'Dịch PDF', formats: ['PDF', 'DOCX'] },
    'read': { title: 'Đọc PDF', formats: ['PDF'] },
  };

const config = toolConfig[toolId] || { title: 'Công cụ', formats: ['PDF'] };

  // Global drag listener for initial state
  useEffect(() => {
    if (files.length > 0) return; // Managed by workspace if files exist

    const handleDragOver = (e) => {
      e.preventDefault();
      setIsDragActive(true);
    };

    const handleDragLeave = (e) => {
      e.preventDefault();
      if (e.clientX === 0 && e.clientY === 0) {
        setIsDragActive(false);
      }
    };

    const handleDrop = (e) => {
      e.preventDefault();
      setIsDragActive(false);
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        setFiles(Array.from(e.dataTransfer.files));
      }
    };

    window.addEventListener('dragover', handleDragOver);
    window.addEventListener('dragleave', handleDragLeave);
    window.addEventListener('drop', handleDrop);

    return () => {
      window.removeEventListener('dragover', handleDragOver);
      window.removeEventListener('dragleave', handleDragLeave);
      window.removeEventListener('drop', handleDrop);
    };
  }, [files.length]);

  const onFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      setFiles(Array.from(e.target.files));
    }
  };

  return (
    <div className={files.length > 0 && toolId === 'merge' ? 'merge-workspace-wrapper' : 'tool-workspace'}>
      {/* Translate tool manages its own full-page UI */}
      {toolId === 'translate' ? (
        <TranslateWorkspace />
      ) : files.length === 0 ? (
        <div
          className={`dropzone ${isDragActive ? 'active' : ''}`}
          onClick={() => document.getElementById('file-upload').click()}
        >
          <UploadCloud className="dropzone-icon" size={60} />
          <button className="dropzone-btn">
            Chọn file <ChevronDown size={18} style={{marginLeft: '5px'}}/>
          </button>
          <input
            type="file"
            id="file-upload"
            multiple
            style={{ display: 'none' }}
            onChange={onFileChange}
          />
          <div className="dropzone-hint">Thêm các file PDF, hình ảnh, Word, Excel, và PowerPoint</div>
          <div className="dropzone-formats">
            Các định dạng được hỗ trợ:
            {config.formats.map(f => (
              <span key={f} className="format-badge ml-1" style={{ backgroundColor: '#fee2e2', color: '#ef4444' }}>{f}</span>
            ))}
          </div>
        </div>
      ) : toolId === 'merge' ? (
        <MergeWorkspace initialFiles={files} onCancel={() => setFiles([])} />
      ) : toolId === 'pdf-to-word' ? (
        <PdfToWordWorkspace initialFiles={files} onCancel={() => setFiles([])} />
      ) : toolId === 'compress' ? (
        <CompressWorkspace initialFiles={files} onCancel={() => setFiles([])} />
      ) : (
        <div style={{ textAlign: 'center', marginTop: '50px' }}>
          <h3>Đã chọn {files.length} file</h3>
          <ul style={{listStyle: 'none', padding: 0}}>
            {files.map(f => <li key={f.name}>{f.name} ({(f.size / 1024 / 1024).toFixed(2)} MB)</li>)}
          </ul>
          <div style={{ marginTop: '20px', display: 'flex', gap: '10px', justifyContent: 'center' }}>
            <button className="btn btn-primary">Xử lý ngay ({config.title})</button>
            <button className="btn btn-outline" onClick={() => setFiles([])}>Hủy</button>
          </div>
        </div>
      )}
    </div>
  );
};

export default ToolPage;
