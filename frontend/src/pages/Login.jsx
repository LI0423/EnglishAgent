import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { confirmPasswordResetByCode, login, normalizeUiError, requestPasswordResetCode } from '../utils/api';
import AuthLayout from '../components/auth/AuthLayout';
import AuthSocialGrid from '../components/auth/AuthSocialGrid';
import '../App.css';

const Login = () => {
  const [account, setAccount] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showReset, setShowReset] = useState(false);
  const [resetAccount, setResetAccount] = useState('');
  const [resetChannel, setResetChannel] = useState('email');
  const [resetCode, setResetCode] = useState('');
  const [resetPassword, setResetPassword] = useState('');
  const [resetMessage, setResetMessage] = useState('');
  const [isRequestingReset, setIsRequestingReset] = useState(false);
  const [isConfirmingReset, setIsConfirmingReset] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const notice = sessionStorage.getItem('login_notice');
    if (notice) {
      setError(notice);
      sessionStorage.removeItem('login_notice');
    }
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await login(account, password);
      navigate('/');
    } catch (err) {
      setError(normalizeUiError(err, '登录失败，请检查账号或密码'));
    } finally {
      setIsLoading(false);
    }
  };

  const handleRequestReset = async () => {
    setResetMessage('');
    if (!String(resetAccount || '').trim()) {
      setResetMessage('请输入账号（用户名/手机号/邮箱）');
      return;
    }
    setIsRequestingReset(true);
    try {
      const result = await requestPasswordResetCode(resetAccount.trim(), resetChannel);
      if (result?.verification_code) {
        setResetCode(result.verification_code);
      }
      setResetMessage(result?.message || '重置请求已提交');
    } catch (err) {
      setResetMessage(normalizeUiError(err, '重置请求失败'));
    } finally {
      setIsRequestingReset(false);
    }
  };

  const handleConfirmReset = async () => {
    setResetMessage('');
    if (!resetCode.trim()) {
      setResetMessage('请输入验证码');
      return;
    }
    if (resetPassword.length < 6) {
      setResetMessage('新密码长度至少 6 位');
      return;
    }
    setIsConfirmingReset(true);
    try {
      const result = await confirmPasswordResetByCode(resetAccount.trim(), resetCode.trim(), resetPassword);
      setResetMessage(result?.message || '密码重置成功，请使用新密码登录');
      setShowReset(false);
    } catch (err) {
      setResetMessage(normalizeUiError(err, '密码重置失败'));
    } finally {
      setIsConfirmingReset(false);
    }
  };

  return (
    <AuthLayout
      brandTitle="AI助力，雅思高分触手可及"
      brandSubtitle="从诊断到提分，给你可执行的每日学习路径。"
      brandItems={[
        '听说读写全模块训练',
        '即时评分与改进建议',
        '个性化学习计划与提醒',
        '错题与词汇智能复习',
      ]}
    >
      <section className="auth-form login-form-panel">
        <div className="auth-header">
          <h1>欢迎登录</h1>
          <p>继续你的雅思学习旅程</p>
        </div>
        {error && <div className="error-message">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="account">邮箱/手机号/用户名</label>
            <input
              type="text"
              id="account"
              value={account}
              onChange={(e) => setAccount(e.target.value)}
              placeholder="请输入邮箱或手机号"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">密码</label>
            <div className="password-input-wrap">
              <input
                type={showPassword ? 'text' : 'password'}
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="请输入密码"
                required
              />
              <button
                type="button"
                className="password-toggle-btn"
                onClick={() => setShowPassword((prev) => !prev)}
                aria-label={showPassword ? '隐藏密码' : '显示密码'}
              >
                {showPassword ? '🙈' : '👁️'}
              </button>
            </div>
          </div>

          <div className="form-options">
            <label className="remember-me">
              <input
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
              />
              <span>记住我</span>
            </label>
            <button
              type="button"
              className="forgot-password inline-link-btn"
              onClick={() => setShowReset((prev) => !prev)}
            >
              忘记密码？
            </button>
          </div>

          {showReset && (
            <div className="form-group" style={{ marginTop: 8 }}>
              <label htmlFor="reset-account">找回密码</label>
              <input
                id="reset-account"
                type="text"
                value={resetAccount}
                onChange={(e) => setResetAccount(e.target.value)}
                placeholder="输入用户名/手机号/邮箱"
              />
              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <select
                  value={resetChannel}
                  onChange={(e) => setResetChannel(e.target.value)}
                  style={{ minWidth: 120 }}
                >
                  <option value="email">邮箱验证码</option>
                  <option value="sms">短信验证码</option>
                </select>
                <button
                  type="button"
                  className="inline-link-btn"
                  onClick={handleRequestReset}
                  disabled={isRequestingReset}
                >
                  {isRequestingReset ? '请求中...' : '获取验证码'}
                </button>
              </div>
              <input
                style={{ marginTop: 8 }}
                type="text"
                value={resetCode}
                onChange={(e) => setResetCode(e.target.value)}
                placeholder="验证码"
              />
              <input
                style={{ marginTop: 8 }}
                type="password"
                value={resetPassword}
                onChange={(e) => setResetPassword(e.target.value)}
                placeholder="输入新密码（至少6位）"
              />
              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <button
                  type="button"
                  className="inline-link-btn"
                  onClick={handleConfirmReset}
                  disabled={isConfirmingReset}
                >
                  {isConfirmingReset ? '提交中...' : '确认重置'}
                </button>
              </div>
            </div>
          )}

          {resetMessage && <div className="error-message" style={{ marginTop: 10 }}>{resetMessage}</div>}

          <button type="submit" className="auth-button" disabled={isLoading}>
            {isLoading ? '登录中...' : '登录'}
          </button>
          <AuthSocialGrid mode="登录" />
        </form>

        <div className="auth-footer">
          <p>还没有账户？ <Link to="/register">立即注册</Link></p>
          <p className="auth-legal-links">
            登录即表示同意 <a href="#">用户协议</a> 与 <a href="#">隐私政策</a>
          </p>
        </div>
      </section>
    </AuthLayout>
  );
};

export default Login;
