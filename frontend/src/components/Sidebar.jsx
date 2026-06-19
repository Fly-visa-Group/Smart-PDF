import { Home, Layers, FileArchive, FileText, Image as ImageIcon, Languages, FileOutput, ArrowLeftRight } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';

const Sidebar = () => {
  const location = useLocation();
  const menuItems = [
    { id: 'home',           icon: <Home size={20} />,         label: 'Trang Chủ',          path: '/' },
    { id: 'merge',          icon: <Layers size={20} />,       label: 'Gộp PDF',             path: '/tool/merge' },
    { id: 'compress',       icon: <FileArchive size={20} />,  label: 'Nén PDF',             path: '/tool/compress' },
    { id: 'pdf-to-word',    icon: <FileText size={20} />,     label: 'PDF → Word',          path: '/tool/pdf-to-word' },
    { id: 'word-to-pdf',    icon: <FileOutput size={20} />,   label: 'Word → PDF',          path: '/tool/word-to-pdf' },
    { id: 'pdf-to-image',   icon: <ImageIcon size={20} />,    label: 'PDF → Hình ảnh',     path: '/tool/pdf-to-image' },
    { id: 'image-to-pdf',   icon: <FileText size={20} />,     label: 'Hình ảnh → PDF',     path: '/tool/image-to-pdf' },
    { id: 'convert-image',  icon: <ArrowLeftRight size={20} />, label: 'Chuyển đổi ảnh',   path: '/tool/convert-image' },
    { id: 'translate',      icon: <Languages size={20} />,    label: 'Dịch PDF',            path: '/tool/translate' },
  ];

  return (
    <div className="sidebar">
      <div className="sidebar-logo">
        <span style={{ color: '#0062ff' }}>S</span>P
      </div>
      <div className="sidebar-menu">
        {menuItems.map(item => (
          <Link to={item.path} key={item.id} className={`sidebar-item ${location.pathname === item.path ? 'active' : ''}`}>
            <div className="icon">{item.icon}</div>
            <div className="label">{item.label}</div>
          </Link>
        ))}
      </div>
    </div>
  );
};

export default Sidebar;
