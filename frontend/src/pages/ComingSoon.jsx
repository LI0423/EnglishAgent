import { Link, useLocation } from 'react-router-dom';

import TopNav from "../components/layout/TopNav";
const titleMap = {
  '/listening': '听力练习',
  '/reading': '阅读练习',
  '/speaking': '口语练习',
  '/reports': '学习报告',
  '/plans': '个性化计划',
  '/achievements': '成就中心',
  '/mock-exam': '模拟考试',
  '/profile': '个人中心',
};

function ComingSoon() {
  const location = useLocation();
  const title = titleMap[location.pathname] || '功能页面';

  return (
    <div className="home-page web-dashboard">
      <TopNav />
      <div className="content-area content-shell content-shell-sm">
        <div className="web-page-head">
          <div>
            <h2>{title}</h2>
            <p>该功能正在建设中。</p>
          </div>
        </div>
        <div className="card">
          <h3>该页面正在建设中</h3>
          <p>当前路径：{location.pathname}</p>
          <p>你可以先返回首页或进入已可用模块继续体验。</p>
          <p style={{ marginTop: 12 }}>
            <Link to="/">返回首页</Link> | <Link to="/writing">写作</Link> |{' '}
            <Link to="/mistakes">错题</Link> | <Link to="/vocabulary">词汇</Link>
          </p>
        </div>
      </div>
    </div>
  );
}

export default ComingSoon;
