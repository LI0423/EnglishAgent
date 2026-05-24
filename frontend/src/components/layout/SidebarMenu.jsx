import { NavLink } from 'react-router-dom';
import { SIDEBAR_NAV_ITEMS } from './navigation';

const GROUP_ORDER = ['learning', 'management', 'system', 'other'];

const ROUTE_GROUP = {
  '/': 'learning',
  '/chat': 'learning',
  '/translation-search': 'learning',
  '/listening': 'learning',
  '/reading': 'learning',
  '/writing': 'learning',
  '/speaking': 'learning',
  '/vocabulary': 'learning',
  '/mistakes': 'management',
  '/plans': 'management',
  '/reports': 'management',
  '/reminders': 'management',
  '/achievements': 'management',
  '/mock-exam': 'management',
  '/community': 'system',
  '/groups': 'system',
  '/payment': 'system',
  '/admin': 'system',
  '/campaigns': 'system',
};

const GROUP_LABEL = {
  learning: '学习模块',
  management: '学习管理',
  system: '系统功能',
  other: '其他',
};

export default function SidebarMenu({ items = SIDEBAR_NAV_ITEMS }) {
  const grouped = {};
  GROUP_ORDER.forEach((key) => {
    grouped[key] = [];
  });
  (items || []).forEach((item) => {
    const key = ROUTE_GROUP[item.to] || 'other';
    grouped[key].push(item);
  });

  return (
    <nav className="sidebar-nav">
      {GROUP_ORDER.map((key) => (
        grouped[key].length > 0 ? (
          <div key={key} className="sidebar-group">
            <p className="sidebar-group-title">{GROUP_LABEL[key]}</p>
            <ul>
              {grouped[key].map((item) => (
                <li key={item.to}>
                  <NavLink to={item.to} end={item.to === '/'} className={({ isActive }) => `sidebar-nav-link${isActive ? ' active' : ''}`}>
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ) : null
      ))}
    </nav>
  );
}
