import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { normalizeUiError, register } from '../utils/api';
import AuthLayout from '../components/auth/AuthLayout';
import AuthSocialGrid from '../components/auth/AuthSocialGrid';
import '../App.css';

const Register = () => {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [agreePolicy, setAgreePolicy] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const navigate = useNavigate();

  const passwordStrength =
    password.length < 8
      ? 'weak'
      : /[A-Za-z]/.test(password) && /\d/.test(password)
        ? 'strong'
        : 'medium';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (password !== confirmPassword) {
      setError('密码不匹配');
      return;
    }

    if (password.length < 6) {
      setError('密码长度至少为6个字符');
      return;
    }

    if (!agreePolicy) {
      setError('请先同意用户协议和隐私政策');
      return;
    }

    setIsLoading(true);

    try {
      await register(username, email, password);
      navigate('/');
    } catch (err) {
      setError(normalizeUiError(err, '注册失败，请稍后重试'));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthLayout
      brandTitle="开始你的AI雅思提分计划"
      brandSubtitle="3分钟完成注册，立即获取个性化学习路径。"
      brandItems={[
        '新用户注册可体验核心功能',
        '智能诊断定位薄弱点',
        '听说读写训练闭环',
        '学习进度与反馈可视化',
      ]}
    >
      <section className="auth-form login-form-panel">
        <div className="auth-header">
          <h1>创建账户</h1>
          <p>加入 EnglishAgent，开始高效备考</p>
        </div>

        {error && <div className="error-message">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="username">用户名</label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="请输入用户名"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="email">邮箱</label>
            <input
              type="email"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="请输入邮箱"
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
                placeholder="至少8位，建议包含字母和数字"
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
            <p className={`password-strength strength-${passwordStrength}`}>
              密码强度：{passwordStrength === 'weak' ? '弱' : passwordStrength === 'medium' ? '中' : '强'}
            </p>
          </div>

          <div className="form-group">
            <label htmlFor="confirmPassword">确认密码</label>
            <div className="password-input-wrap">
              <input
                type={showConfirmPassword ? 'text' : 'password'}
                id="confirmPassword"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="请再次输入密码"
                required
              />
              <button
                type="button"
                className="password-toggle-btn"
                onClick={() => setShowConfirmPassword((prev) => !prev)}
                aria-label={showConfirmPassword ? '隐藏密码' : '显示密码'}
              >
                {showConfirmPassword ? '🙈' : '👁️'}
              </button>
            </div>
          </div>

          <label className="policy-check-wrap">
            <input
              type="checkbox"
              checked={agreePolicy}
              onChange={(e) => setAgreePolicy(e.target.checked)}
            />
            <span>
              我已阅读并同意 <a href="#">用户协议</a> 与 <a href="#">隐私政策</a>
            </span>
          </label>

          <button type="submit" className="auth-button" disabled={isLoading}>
            {isLoading ? '注册中...' : '注册'}
          </button>
          <AuthSocialGrid mode="注册" />
        </form>

        <div className="auth-footer">
          <p>已有账户？ <Link to="/login">立即登录</Link></p>
          <p className="auth-legal-links">注册即表示同意平台条款与隐私规则</p>
        </div>
      </section>
    </AuthLayout>
  );
};

export default Register;
