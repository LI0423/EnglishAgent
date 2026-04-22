import { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  getAdminCampaignConversionReport,
  getAdminEntitlementLedger,
  getAdminEntitlementEfficiencyReport,
  getAdminFunnelReport,
  getAdminOrders,
  getAdminOverview,
  getAdminPendingComments,
  getAdminPendingPosts,
  getAdminRetentionReport,
  getCurrentUser,
  moderateAdminComment,
  moderateAdminPost,
} from '../utils/api';

const TABS = [
  { key: 'overview', label: '总览' },
  { key: 'reports', label: '报表' },
  { key: 'moderation', label: '审核台' },
  { key: 'orders', label: '订单台' },
  { key: 'ledger', label: '权益审计' },
];

const Admin = () => {
  const navItems = [
    { to: '/', label: '🏠 首页' },
    { to: '/payment', label: '💳 支付中心' },
    { to: '/community', label: '👥 学习社区' },
    { to: '/admin', label: '🛠️ 运营后台' },
  ];

  const [userData, setUserData] = useState({ username: '管理员' });
  const [tab, setTab] = useState('overview');
  const [overview, setOverview] = useState(null);
  const [pendingPosts, setPendingPosts] = useState([]);
  const [pendingComments, setPendingComments] = useState([]);
  const [orders, setOrders] = useState([]);
  const [ledger, setLedger] = useState([]);
  const [retention, setRetention] = useState(null);
  const [funnel, setFunnel] = useState(null);
  const [entitlementReport, setEntitlementReport] = useState(null);
  const [campaignReport, setCampaignReport] = useState(null);
  const [message, setMessage] = useState('');
  const [orderStatus, setOrderStatus] = useState('');
  const [orderUserId, setOrderUserId] = useState('');
  const [ledgerUserId, setLedgerUserId] = useState('');
  const [ledgerFeature, setLedgerFeature] = useState('');

  const loadOverview = async () => setOverview(await getAdminOverview());
  const loadModeration = async () => {
    const [p, c] = await Promise.all([getAdminPendingPosts(100), getAdminPendingComments(150)]);
    setPendingPosts(p || []);
    setPendingComments(c || []);
  };
  const loadOrders = async () => {
    setOrders(await getAdminOrders({ status: orderStatus, userId: orderUserId, limit: 150 }));
  };
  const loadLedger = async () => {
    setLedger(await getAdminEntitlementLedger({ userId: ledgerUserId, featureCode: ledgerFeature, limit: 300 }));
  };
  const loadReports = async () => {
    const [r, f, e, c] = await Promise.all([
      getAdminRetentionReport(14),
      getAdminFunnelReport(30),
      getAdminEntitlementEfficiencyReport('', 30),
      getAdminCampaignConversionReport(30),
    ]);
    setRetention(r || null);
    setFunnel(f || null);
    setEntitlementReport(e || null);
    setCampaignReport(c || null);
  };

  const bootstrap = async () => {
    try {
      const user = await getCurrentUser();
      if (user) setUserData(prev => ({ ...prev, username: user.username }));
      await Promise.all([loadOverview(), loadReports(), loadModeration(), loadOrders(), loadLedger()]);
    } catch (err) {
      setMessage(typeof err === 'string' ? err : '后台数据加载失败（请确认当前账号有管理员权限）');
    }
  };

  useEffect(() => {
    bootstrap();
  }, []);

  const handleModeratePost = async (id, action) => {
    try {
      await moderateAdminPost(id, action, action === 'approve' ? '通过内容审核' : '驳回内容审核');
      setMessage(`帖子 ${id.slice(0, 8)} 已${action === 'approve' ? '通过' : '驳回'}`);
      await loadModeration();
    } catch (err) {
      setMessage(typeof err === 'string' ? err : '操作失败');
    }
  };

  const handleModerateComment = async (id, action) => {
    try {
      await moderateAdminComment(id, action, action === 'approve' ? '通过评论审核' : '驳回评论审核');
      setMessage(`评论 ${id.slice(0, 8)} 已${action === 'approve' ? '通过' : '驳回'}`);
      await loadModeration();
    } catch (err) {
      setMessage(typeof err === 'string' ? err : '操作失败');
    }
  };

  return (
    <div className="dashboard-page">
      <header className="top-nav">
        <div className="nav-content">
          <div className="nav-left"><h1>🎓 IELTS Agent</h1></div>
          <div className="nav-right">
            <div className="user-profile"><span className="avatar">👤</span><span className="username">{userData.username}</span></div>
          </div>
        </div>
      </header>
      <div className="main-layout">
        <div className="sidebar">
          <div className="sidebar-header"><h2>🎓 IELTS Agent</h2></div>
          <nav className="sidebar-nav">
            <ul>
              {navItems.map((item) => (
                <li key={item.to}>
                  <NavLink to={item.to} end={item.to === '/'} className={({ isActive }) => `sidebar-nav-link${isActive ? ' active' : ''}`}>
                    {item.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>
        </div>
        <div className="content-area">
          <main className="reports-content">
            <div className="page-header">
              <div className="breadcrumb"><span>首页</span> &gt; <span>运营后台</span></div>
              <h1 className="page-title">🛠️ 运营后台</h1>
            </div>
            {message && <div className="card"><p>{message}</p></div>}

            <div className="task-type-switch" style={{ marginBottom: 16 }}>
              {TABS.map((x) => (
                <button key={x.key} className={`task-btn ${tab === x.key ? 'active' : ''}`} onClick={() => setTab(x.key)}>
                  {x.label}
                </button>
              ))}
            </div>

            {tab === 'overview' && (
              <div className="overview-cards">
                <div className="card"><h3>总用户</h3><p className="big-number">{overview?.total_users ?? 0}</p></div>
                <div className="card"><h3>7日活跃</h3><p className="big-number">{overview?.active_users_7d ?? 0}</p></div>
                <div className="card"><h3>总订单</h3><p className="big-number">{overview?.total_orders ?? 0}</p></div>
                <div className="card"><h3>已支付订单</h3><p className="big-number">{overview?.paid_orders ?? 0}</p></div>
                <div className="card"><h3>支付金额</h3><p className="big-number">{((overview?.paid_amount_cents ?? 0) / 100).toFixed(2)}</p></div>
                <div className="card"><h3>待审帖子</h3><p className="big-number">{overview?.pending_posts ?? 0}</p></div>
                <div className="card"><h3>待审评论</h3><p className="big-number">{overview?.pending_comments ?? 0}</p></div>
                <div className="card"><h3>写作权益库存</h3><p className="big-number">{overview?.writing_ai_review_balance_sum ?? 0}</p></div>
              </div>
            )}

            {tab === 'reports' && (
              <>
                <div className="card" style={{ marginBottom: 16 }}>
                  <h3>留存报表（近14天 cohort）</h3>
                  <p>D1 留存：<strong>{retention?.d1_retention_rate ?? 0}%</strong> | D7 留存：<strong>{retention?.d7_retention_rate ?? 0}%</strong> | 新增用户：<strong>{retention?.new_users ?? 0}</strong></p>
                  <ul>
                    {(retention?.cohorts || []).slice(-7).map((x) => (
                      <li key={x.date}>
                        {x.date} | 新增 {x.new_users} | D1 {x.d1_rate}% | D7 {x.d7_rate}%
                      </li>
                    ))}
                    {!(retention?.cohorts || []).length && <li>暂无留存数据</li>}
                  </ul>
                </div>

                <div className="card" style={{ marginBottom: 16 }}>
                  <h3>商业化漏斗（近30天）</h3>
                  <p>
                    曝光用户：<strong>{funnel?.exposure_users ?? 0}</strong> → 下单用户：<strong>{funnel?.order_users ?? 0}</strong> → 支付用户：<strong>{funnel?.paid_users ?? 0}</strong>
                  </p>
                  <p>
                    曝光→下单：{funnel?.exposure_to_order_rate ?? 0}% | 下单→支付：{funnel?.order_to_paid_rate ?? 0}% | 曝光→支付：{funnel?.exposure_to_paid_rate ?? 0}%
                  </p>
                  <p>支付金额：{((funnel?.paid_amount_cents ?? 0) / 100).toFixed(2)} | {funnel?.inferred_exposure ? '曝光口径为推断值' : '曝光口径为事件值'}</p>
                </div>

                <div className="card" style={{ marginBottom: 16 }}>
                  <h3>权益效率（近30天）</h3>
                  <ul>
                    {(entitlementReport?.feature_summary || []).map((x) => (
                      <li key={x.feature_code}>
                        {x.feature_code} | 发放 {x.granted_sum} | 消耗 {x.consumed_sum} | 剩余 {x.balance_sum} | 使用率 {x.usage_rate}%
                      </li>
                    ))}
                    {!(entitlementReport?.feature_summary || []).length && <li>暂无权益效率数据</li>}
                  </ul>
                </div>

                <div className="card">
                  <h3>活动转化（近30天）</h3>
                  <p>
                    活动数：<strong>{campaignReport?.campaign_count ?? 0}</strong> | 参与总量：<strong>{campaignReport?.participant_total ?? 0}</strong> | 完成总量：<strong>{campaignReport?.completed_total ?? 0}</strong>
                  </p>
                  <p>
                    平均完成率：{campaignReport?.avg_completion_rate ?? 0}% | 奖励积分成本：{campaignReport?.reward_cost_points_total ?? 0}
                  </p>
                  <ul>
                    {(campaignReport?.campaigns || []).slice(0, 8).map((x) => (
                      <li key={x.campaign_id}>
                        {x.title} | 参与 {x.participant_count} | 完成 {x.completed_count} | 完成率 {x.completion_rate}% | 成本 {x.reward_cost_points} 分
                      </li>
                    ))}
                    {!(campaignReport?.campaigns || []).length && <li>暂无活动转化数据</li>}
                  </ul>
                </div>
              </>
            )}

            {tab === 'moderation' && (
              <>
                <div className="card" style={{ marginBottom: 16 }}>
                  <h3>待审核帖子</h3>
                  <ul>
                    {pendingPosts.map((p) => (
                      <li key={p.id} style={{ marginBottom: 10 }}>
                        <strong>{p.title}</strong> | {p.post_type} | user {p.user_id}
                        <br />
                        {String(p.content || '').slice(0, 180)}
                        <br />
                        <button onClick={() => handleModeratePost(p.id, 'approve')}>通过</button>{' '}
                        <button onClick={() => handleModeratePost(p.id, 'reject')}>驳回</button>
                      </li>
                    ))}
                    {pendingPosts.length === 0 && <li>暂无待审核帖子</li>}
                  </ul>
                </div>
                <div className="card">
                  <h3>待审核评论</h3>
                  <ul>
                    {pendingComments.map((c) => (
                      <li key={c.id} style={{ marginBottom: 10 }}>
                        post {c.post_id}({c.post_title || '-'}) | user {c.user_id}
                        <br />
                        {c.content}
                        <br />
                        <button onClick={() => handleModerateComment(c.id, 'approve')}>通过</button>{' '}
                        <button onClick={() => handleModerateComment(c.id, 'reject')}>驳回</button>
                      </li>
                    ))}
                    {pendingComments.length === 0 && <li>暂无待审核评论</li>}
                  </ul>
                </div>
              </>
            )}

            {tab === 'orders' && (
              <div className="card">
                <h3>订单检索</h3>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                  <select value={orderStatus} onChange={(e) => setOrderStatus(e.target.value)}>
                    <option value="">全部状态</option>
                    <option value="pending">pending</option>
                    <option value="paid">paid</option>
                    <option value="failed">failed</option>
                    <option value="canceled">canceled</option>
                  </select>
                  <input value={orderUserId} onChange={(e) => setOrderUserId(e.target.value)} placeholder="按 user_id 过滤" />
                  <button onClick={loadOrders}>查询</button>
                </div>
                <ul>
                  {orders.map((o) => (
                    <li key={o.id}>
                      {o.id} | user {o.user_id} | {o.product_code} | {(o.total_price_cents / 100).toFixed(2)} | {o.status}
                    </li>
                  ))}
                  {orders.length === 0 && <li>无订单数据</li>}
                </ul>
              </div>
            )}

            {tab === 'ledger' && (
              <div className="card">
                <h3>权益审计流水</h3>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                  <input value={ledgerUserId} onChange={(e) => setLedgerUserId(e.target.value)} placeholder="按 user_id 过滤" />
                  <input value={ledgerFeature} onChange={(e) => setLedgerFeature(e.target.value)} placeholder="按 feature_code 过滤" />
                  <button onClick={loadLedger}>查询</button>
                </div>
                <ul>
                  {ledger.map((x) => (
                    <li key={x.id}>
                      {x.user_id} | {x.feature_code} | change {x.change_amount} | after {x.balance_after} | {x.source_type}
                    </li>
                  ))}
                  {ledger.length === 0 && <li>无审计数据</li>}
                </ul>
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
};

export default Admin;
