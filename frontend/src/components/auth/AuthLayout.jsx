import React from 'react';

function AuthLayout({ brandTitle, brandSubtitle, brandItems, children }) {
  return (
    <div className="auth-container">
      <section className="auth-illustration login-brand-panel">
        <div className="illustration-content">
          <div className="login-brand-badge">🎓 EnglishAgent</div>
          <h2>{brandTitle}</h2>
          <p>{brandSubtitle}</p>
          <ul>
            {brandItems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </section>
      {children}
    </div>
  );
}

export default AuthLayout;
