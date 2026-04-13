import { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  createCommunityComment,
  createCommunityPost,
  getCommunityComments,
  getCommunityPosts,
  getCurrentUser,
  getMyCommunitySummary,
  voteCommunityComment,
  voteCommunityPost,
} from '../utils/api';

const Community = () => {
  const navItems = [
    { to: '/', label: '🏠 首页' },
    { to: '/chat', label: '🤖 智能对话' },
    { to: '/listening', label: '🎧 听力练习' },
    { to: '/reading', label: '📚 阅读练习' },
    { to: '/writing', label: '📝 写作练习' },
    { to: '/speaking', label: '💬 口语练习' },
    { to: '/vocabulary', label: '📋 词汇学习' },
    { to: '/mistakes', label: '🔖 错题本' },
    { to: '/community', label: '👥 学习社区' },
    { to: '/reports', label: '📊 学习报告' },
    { to: '/achievements', label: '🏆 成就中心' },
  ];

  const [userData, setUserData] = useState({ username: '李同学' });
  const [summary, setSummary] = useState({ post_count: 0, comment_count: 0, vote_count: 0 });
  const [postTypeFilter, setPostTypeFilter] = useState('');
  const [keyword, setKeyword] = useState('');
  const [posts, setPosts] = useState([]);
  const [selectedPost, setSelectedPost] = useState(null);
  const [comments, setComments] = useState([]);
  const [newTitle, setNewTitle] = useState('');
  const [newContent, setNewContent] = useState('');
  const [newTags, setNewTags] = useState('');
  const [newPostType, setNewPostType] = useState('discussion');
  const [newComment, setNewComment] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  const loadPosts = async () => {
    setLoading(true);
    try {
      const rows = await getCommunityPosts({
        postType: postTypeFilter || null,
        keyword,
        limit: 30,
        offset: 0,
      });
      setPosts(rows || []);
    } catch (err) {
      setMessage(typeof err === 'string' ? err : '加载社区帖子失败');
    } finally {
      setLoading(false);
    }
  };

  const loadSummary = async () => {
    try {
      const data = await getMyCommunitySummary();
      setSummary(data || { post_count: 0, comment_count: 0, vote_count: 0 });
    } catch {
      // ignore
    }
  };

  const loadComments = async (postId) => {
    try {
      const rows = await getCommunityComments(postId, 120);
      setComments(rows || []);
    } catch (err) {
      setMessage(typeof err === 'string' ? err : '加载评论失败');
    }
  };

  useEffect(() => {
    const bootstrap = async () => {
      try {
        const user = await getCurrentUser();
        if (user) setUserData(prev => ({ ...prev, username: user.username }));
      } catch {
        // ignore
      }
      await Promise.all([loadPosts(), loadSummary()]);
    };
    bootstrap();
  }, []);

  useEffect(() => {
    loadPosts();
  }, [postTypeFilter]);

  const handleCreatePost = async () => {
    if (!newTitle.trim() || !newContent.trim()) return;
    setMessage('');
    try {
      const res = await createCommunityPost({
        post_type: newPostType,
        title: newTitle.trim(),
        content: newContent.trim(),
        tags: newTags.split(',').map(x => x.trim()).filter(Boolean),
        is_anonymous: false,
      });
      setMessage(res?.message || '发布成功');
      setNewTitle('');
      setNewContent('');
      setNewTags('');
      await Promise.all([loadPosts(), loadSummary()]);
    } catch (err) {
      setMessage(typeof err === 'string' ? err : '发布失败');
    }
  };

  const handleSelectPost = async (post) => {
    setSelectedPost(post);
    await loadComments(post.id);
  };

  const handleVotePost = async (postId, vote) => {
    try {
      const stat = await voteCommunityPost(postId, vote);
      setPosts(prev => prev.map(x => (
        x.id === postId ? { ...x, upvotes: stat.upvotes, downvotes: stat.downvotes } : x
      )));
      if (selectedPost?.id === postId) {
        setSelectedPost(prev => prev ? { ...prev, upvotes: stat.upvotes, downvotes: stat.downvotes } : prev);
      }
      await loadSummary();
    } catch (err) {
      setMessage(typeof err === 'string' ? err : '点赞失败');
    }
  };

  const handleCreateComment = async () => {
    if (!selectedPost?.id || !newComment.trim()) return;
    try {
      const res = await createCommunityComment(selectedPost.id, {
        content: newComment.trim(),
        is_anonymous: false,
      });
      if (res.status !== 'published') {
        setMessage('评论已提交，等待审核');
      }
      setNewComment('');
      await Promise.all([loadComments(selectedPost.id), loadPosts(), loadSummary()]);
    } catch (err) {
      setMessage(typeof err === 'string' ? err : '评论失败');
    }
  };

  const handleVoteComment = async (commentId, vote) => {
    try {
      const stat = await voteCommunityComment(commentId, vote);
      setComments(prev => prev.map(x => (
        x.id === commentId ? { ...x, upvotes: stat.upvotes, downvotes: stat.downvotes } : x
      )));
      await loadSummary();
    } catch (err) {
      setMessage(typeof err === 'string' ? err : '评论投票失败');
    }
  };

  return (
    <div className="dashboard-page">
      <header className="top-nav">
        <div className="nav-content">
          <div className="nav-left"><h1>🎓 IELTS Agent</h1></div>
          <div className="nav-right">
            <div className="notification"><span className="icon">🔔</span><span className="badge">3</span></div>
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
              <div className="breadcrumb"><span>首页</span> &gt; <span>学习社区</span></div>
              <h1 className="page-title">👥 学习社区</h1>
            </div>

            <div className="overview-cards" style={{ marginBottom: 16 }}>
              <div className="card"><h3>我的发帖</h3><p className="big-number">{summary.post_count}</p></div>
              <div className="card"><h3>我的评论</h3><p className="big-number">{summary.comment_count}</p></div>
              <div className="card"><h3>我的互动</h3><p className="big-number">{summary.vote_count}</p></div>
              <div className="card"><h3>状态</h3><p className="small-text">讨论/问答/经验分享已开放</p></div>
            </div>

            <div className="card" style={{ marginBottom: 16 }}>
              <h3>发布新帖</h3>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                <select value={newPostType} onChange={(e) => setNewPostType(e.target.value)}>
                  <option value="discussion">讨论</option>
                  <option value="question">问答</option>
                  <option value="share">经验分享</option>
                </select>
                <input value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="标题（4-120字）" style={{ minWidth: 260, flex: 1 }} />
                <input value={newTags} onChange={(e) => setNewTags(e.target.value)} placeholder="标签，逗号分隔（如 写作,口语）" style={{ minWidth: 260, flex: 1 }} />
              </div>
              <textarea rows={4} value={newContent} onChange={(e) => setNewContent(e.target.value)} placeholder="写下你的问题、经验或观点..." style={{ width: '100%', marginBottom: 8 }} />
              <button onClick={handleCreatePost}>发布帖子</button>
              {message && <p style={{ marginTop: 8 }}>{message}</p>}
            </div>

            <div className="card" style={{ marginBottom: 16 }}>
              <h3>社区广场</h3>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
                <select value={postTypeFilter} onChange={(e) => setPostTypeFilter(e.target.value)}>
                  <option value="">全部类型</option>
                  <option value="discussion">讨论</option>
                  <option value="question">问答</option>
                  <option value="share">经验分享</option>
                </select>
                <input value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="关键词搜索" />
                <button onClick={loadPosts} disabled={loading}>{loading ? '加载中...' : '搜索'}</button>
              </div>
              <ul>
                {posts.map((p) => (
                  <li key={p.id} style={{ marginBottom: 10 }}>
                    <strong>{p.title}</strong> [{p.post_type}] by {p.author_alias}
                    <br />
                    <span style={{ color: '#4b5563' }}>{String(p.content || '').slice(0, 120)}...</span>
                    <br />
                    <span>👍 {p.upvotes} | 👎 {p.downvotes} | 💬 {p.comment_count} | 👀 {p.view_count}</span>
                    <br />
                    <button onClick={() => handleSelectPost(p)}>查看讨论</button>{' '}
                    <button onClick={() => handleVotePost(p.id, 1)}>点赞</button>{' '}
                    <button onClick={() => handleVotePost(p.id, -1)}>点踩</button>{' '}
                    <button onClick={() => handleVotePost(p.id, 0)}>取消投票</button>
                  </li>
                ))}
                {posts.length === 0 && <li>暂无帖子，快来发第一条</li>}
              </ul>
            </div>

            {selectedPost && (
              <div className="card">
                <h3>帖子评论：{selectedPost.title}</h3>
                <textarea rows={3} value={newComment} onChange={(e) => setNewComment(e.target.value)} placeholder="写下你的评论..." style={{ width: '100%', marginBottom: 8 }} />
                <button onClick={handleCreateComment}>发表评论</button>
                <ul style={{ marginTop: 10 }}>
                  {comments.map((c) => (
                    <li key={c.id} style={{ marginBottom: 8 }}>
                      {c.author_alias}：{c.content}
                      <br />
                      👍 {c.upvotes} | 👎 {c.downvotes}
                      <br />
                      <button onClick={() => handleVoteComment(c.id, 1)}>赞同</button>{' '}
                      <button onClick={() => handleVoteComment(c.id, -1)}>反对</button>{' '}
                      <button onClick={() => handleVoteComment(c.id, 0)}>取消</button>
                    </li>
                  ))}
                  {comments.length === 0 && <li>暂无评论</li>}
                </ul>
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
};

export default Community;
