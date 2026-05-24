import { useEffect, useState } from 'react';
import { getCurrentUser } from '../../utils/api';

export default function TopNav({
  username,
  showNotifications = true,
  notificationCount = 3,
  showSettings = true,
  showUser = true,
}) {
  const [fallbackUsername, setFallbackUsername] = useState('');
  const displayUsername = username || fallbackUsername;

  useEffect(() => {
    if (!showUser || username) return;
    let active = true;

    const loadUser = async () => {
      try {
        const user = await getCurrentUser();
        if (active && user?.username) {
          setFallbackUsername(user.username);
        }
      } catch {
        if (active) {
          setFallbackUsername('');
        }
      }
    };

    loadUser();
    return () => {
      active = false;
    };
  }, [showUser, username]);

  return (
    <header className="top-nav">
      <div className="nav-content">
        <div className="nav-left">
          <h1>IELTS Agent</h1>
        </div>
        {(showNotifications || showUser || showSettings) && (
          <div className="nav-right">
            {showNotifications && (
              <div className="notification">
                <span className="icon">🔔</span>
                <span className="badge">{notificationCount}</span>
              </div>
            )}
            {showUser && (
              <div className="user-profile">
                <span className="avatar">👤</span>
                <span className="username">{displayUsername || '同学'}</span>
              </div>
            )}
            {showSettings && (
              <div className="settings">
                <span className="icon">⚙️</span>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
