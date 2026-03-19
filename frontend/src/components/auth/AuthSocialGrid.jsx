import React from 'react';

function AuthSocialGrid({ mode = '登录' }) {
  return (
    <>
      <div className="auth-divider">
        <span>或使用以下方式{mode}</span>
      </div>
      <div className="third-party-grid">
        <button type="button" className="auth-button secondary">微信</button>
        <button type="button" className="auth-button secondary">QQ</button>
        <button type="button" className="auth-button secondary">Apple ID</button>
        <button type="button" className="auth-button secondary">Google</button>
      </div>
    </>
  );
}

export default AuthSocialGrid;
