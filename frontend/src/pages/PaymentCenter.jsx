import { useEffect, useState } from 'react';
import {
  callbackMockPay,
  createMockPayIntent,
  createPaymentOrder,
  getCurrentUser,
  getPaymentEntitlements,
  getPaymentOrders,
  getPaymentProducts,
} from '../utils/api';
import SidebarMenu from '../components/layout/SidebarMenu';

import TopNav from "../components/layout/TopNav";
const PaymentCenter = () => {

  const [userData, setUserData] = useState({ username: '李同学' });
  const [products, setProducts] = useState([]);
  const [orders, setOrders] = useState([]);
  const [entitlements, setEntitlements] = useState([]);
  const [creatingCode, setCreatingCode] = useState('');
  const [payingOrderId, setPayingOrderId] = useState('');
  const [message, setMessage] = useState('');

  const loadData = async () => {
    const [p, o, e] = await Promise.all([
      getPaymentProducts(),
      getPaymentOrders(50),
      getPaymentEntitlements(),
    ]);
    setProducts(p || []);
    setOrders(o || []);
    setEntitlements(e || []);
  };

  useEffect(() => {
    const bootstrap = async () => {
      try {
        const user = await getCurrentUser();
        if (user) setUserData(prev => ({ ...prev, username: user.username }));
      } catch {
        // ignore
      }
      await loadData();
    };
    bootstrap();
  }, []);

  const handleCreateOrder = async (code) => {
    setCreatingCode(code);
    setMessage('');
    try {
      const res = await createPaymentOrder(code, 1);
      setMessage(`下单成功：订单 ${res?.order?.id?.slice(0, 8) || ''}`);
      await loadData();
    } catch (err) {
      setMessage(typeof err === 'string' ? err : '下单失败');
    } finally {
      setCreatingCode('');
    }
  };

  const handleMockPay = async (orderId) => {
    setPayingOrderId(orderId);
    setMessage('');
    try {
      const intent = await createMockPayIntent(orderId);
      const payload = intent?.callback_payload || {};
      const res = await callbackMockPay(payload);
      if (res?.status === 'paid') {
        setMessage('支付成功，权益已到账');
      } else {
        setMessage('支付回调完成');
      }
      await loadData();
    } catch (err) {
      setMessage(typeof err === 'string' ? err : '模拟支付失败');
    } finally {
      setPayingOrderId('');
    }
  };

  return (
    <div className="home-page web-dashboard dashboard-page">
      <TopNav username={userData.username} />
      <div className="main-layout">
        <div className="sidebar">
          <SidebarMenu />
        </div>
        <div className="content-area content-shell">
          <main className="reports-content">
            <div className="web-page-head">
              <div>
                <h2>支付中心</h2>
                <p>查看权益余额、商品与订单状态。</p>
              </div>
            </div>
            {message && <div className="card"><p>{message}</p></div>}

            <div className="card" style={{ marginBottom: 16 }}>
              <h3>我的权益余额</h3>
              <ul>
                {entitlements.map((x) => (
                  <li key={x.id}>
                    {x.feature_code}：余额 {x.balance}（累计发放 {x.total_granted}，累计消耗 {x.total_consumed}）
                  </li>
                ))}
                {entitlements.length === 0 && <li>暂无权益余额</li>}
              </ul>
            </div>

            <div className="card" style={{ marginBottom: 16 }}>
              <h3>商品列表</h3>
              <ul>
                {products.map((p) => (
                  <li key={p.code} style={{ marginBottom: 10 }}>
                    <strong>{p.name}</strong> | 价格 {(p.price_cents / 100).toFixed(2)} {p.currency}
                    <br />
                    权益：{Object.entries(p.entitlements || {}).map(([k, v]) => `${k} +${v}`).join(' | ')}
                    <br />
                    <button onClick={() => handleCreateOrder(p.code)} disabled={creatingCode === p.code}>
                      {creatingCode === p.code ? '下单中...' : '立即下单'}
                    </button>
                  </li>
                ))}
                {products.length === 0 && <li>暂无商品</li>}
              </ul>
            </div>

            <div className="card">
              <h3>我的订单</h3>
              <ul>
                {orders.map((o) => (
                  <li key={o.id} style={{ marginBottom: 10 }}>
                    {o.product_name} | {(o.total_price_cents / 100).toFixed(2)} {o.currency} | 状态 {o.status}
                    <br />
                    订单号：{o.id}
                    <br />
                    <button
                      onClick={() => handleMockPay(o.id)}
                      disabled={o.status === 'paid' || payingOrderId === o.id}
                    >
                      {payingOrderId === o.id ? '支付中...' : (o.status === 'paid' ? '已支付' : '模拟支付')}
                    </button>
                  </li>
                ))}
                {orders.length === 0 && <li>暂无订单</li>}
              </ul>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
};

export default PaymentCenter;
