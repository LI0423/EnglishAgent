import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { login } from '../utils/api';
import '../App.css';

const Login = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await login(username, password);
      navigate('/');
    } catch (err) {
      setError(err || 'Login failed. Please check your credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-form">
        <div className="auth-header">
          <h1>English Agent</h1>
          <p>登录您的账户</p>
        </div>

        {error && <div className="error-message">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="username">用户名或邮箱</label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="请输入用户名或邮箱"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">密码</label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="请输入密码"
              required
            />
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
            <Link to="/forgot-password" className="forgot-password">忘记密码？</Link>
          </div>

          <button type="submit" className="auth-button" disabled={isLoading}>
            {isLoading ? '登录中...' : '登录'}
          </button>

          <div className="auth-divider">
            <span>或</span>
          </div>

          <button type="button" className="auth-button secondary">
            使用微信登录
          </button>
        </form>

        <div className="auth-footer">
          <p>还没有账户？ <Link to="/register">立即注册</Link></p>
        </div>
      </div>

      <div className="auth-illustration">
        <div className="illustration-content">
          <h2>欢迎回到 English Agent</h2>
          <p>继续您的英语学习之旅，提升您的雅思成绩</p>
          <ul>
            <li>智能学习计划</li>
            <li>个性化辅导</li>
            <li>实时反馈</li>
            <li>模拟考试</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default Login;
