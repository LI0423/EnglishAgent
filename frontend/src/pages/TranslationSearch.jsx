import { useEffect, useMemo, useState } from 'react';
import {
  checkTranslationAnswer,
  autoCollectVocabulary,
  createMistake,
  getDifficultyRecommendation,
  generateTranslationQuestion,
  getCurrentUser,
  postDeepSearch,
} from '../utils/api';
import SidebarMenu from '../components/layout/SidebarMenu';

import TopNav from "../components/layout/TopNav";
const TranslationSearch = () => {

  const [userData, setUserData] = useState({ username: '同学' });
  const [tab, setTab] = useState('translation');

  const [practiceMode, setPracticeMode] = useState('blind');
  const [difficulty, setDifficulty] = useState('easy');
  const [difficultyRecommendation, setDifficultyRecommendation] = useState(null);
  const [difficultyTouched, setDifficultyTouched] = useState(false);
  const [direction, setDirection] = useState('zh_to_en');
  const [topic, setTopic] = useState('education');
  const [question, setQuestion] = useState(null);
  const [translationInput, setTranslationInput] = useState('');
  const [translationResult, setTranslationResult] = useState(null);
  const [generatingQuestion, setGeneratingQuestion] = useState(false);
  const [checkingTranslation, setCheckingTranslation] = useState(false);
  const [showQuestionHint, setShowQuestionHint] = useState(false);
  const [translationError, setTranslationError] = useState('');
  const [translationSaveMessage, setTranslationSaveMessage] = useState('');
  const [modeSwitchMessage, setModeSwitchMessage] = useState('');

  const [searchQuery, setSearchQuery] = useState('');
  const [searchResult, setSearchResult] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [searchMaxIterations, setSearchMaxIterations] = useState(3);
  const [searchSaveMessage, setSearchSaveMessage] = useState('');

  const topicOptions = [
    { value: 'education', label: '教育' },
    { value: 'environment', label: '环境' },
    { value: 'technology', label: '科技' },
    { value: 'society', label: '社会' },
    { value: 'work', label: '工作' },
    { value: 'health', label: '健康' },
  ];

  const practiceModeConfig = {
    blind: {
      label: '盲译练习',
      badge: '当前：盲译',
      title: '先独立翻译，再复盘考点',
      description: '题目前不展示训练重点，避免提前暴露考点；提交批改后再展示本题词汇、句型和语法复盘。',
    },
    guided: {
      label: '词汇句型造句',
      badge: '当前：造句',
      title: '先看目标表达，再完成造句',
      description: '提前展示本题要练的词汇和句型，适合围绕目标表达进行主动输出训练。',
    },
  };

  const currentMode = practiceModeConfig[practiceMode];

  const handlePracticeModeChange = (mode) => {
    if (mode === practiceMode) return;
    const nextMode = practiceModeConfig[mode];
    setPracticeMode(mode);
    setShowQuestionHint(false);
    setTranslationInput('');
    setTranslationResult(null);
    setTranslationError('');
    setTranslationSaveMessage('');
    setModeSwitchMessage(`已切换到${nextMode.label}，作答区和批改结果已重置。`);
  };

  useEffect(() => {
    const fetchUserData = async () => {
      try {
        const user = await getCurrentUser();
        if (user) {
          setUserData((prev) => ({ ...prev, username: user.username || '同学' }));
        }
      } catch {
        // ignore user-info failures to keep module usable
      }
    };
    fetchUserData();
  }, []);

  useEffect(() => {
    const fetchRecommendation = async () => {
      try {
        const data = await getDifficultyRecommendation('translation');
        setDifficultyRecommendation(data);
        if (!difficultyTouched && data?.recommended_difficulty) {
          setDifficulty(data.recommended_difficulty);
        }
      } catch {
        setDifficultyRecommendation({
          recommended_difficulty: 'easy',
          label: '基础',
          reason: '暂时无法读取能力画像，先从基础难度开始。',
          confidence: 0,
          sample_count: 0,
          source: 'fallback',
        });
      }
    };
    fetchRecommendation();
  }, [difficultyTouched]);

  const overall = useMemo(
    () => Number(translationResult?.overall || 0).toFixed(1),
    [translationResult],
  );

  const handleGenerateQuestion = async () => {
    setTranslationError('');
    setTranslationResult(null);
    setTranslationSaveMessage('');
    setModeSwitchMessage('');
    setShowQuestionHint(false);
    setGeneratingQuestion(true);
    try {
      const data = await generateTranslationQuestion(difficulty, direction, topic);
      setQuestion(data);
      setTranslationInput('');
    } catch (error) {
      setTranslationError(typeof error === 'string' ? error : '生成翻译题目失败');
    } finally {
      setGeneratingQuestion(false);
    }
  };

  const getFocusPoints = () => (Array.isArray(question?.focus_points) ? question.focus_points.filter(Boolean) : []);

  const splitFocusPoints = () => {
    const points = getFocusPoints();
    const vocab = [];
    const patterns = [];
    points.forEach((item) => {
      const text = String(item || '').trim();
      if (!text) return;
      if (/句|从句|结构|语法|时态|主语|谓语|宾语|clause|sentence|grammar|structure/i.test(text)) {
        patterns.push(text);
      } else {
        vocab.push(text);
      }
    });
    if (!vocab.length && points.length) vocab.push(points[0]);
    if (!patterns.length && points.length > 1) patterns.push(points[1]);
    return { vocab, patterns, points };
  };

  const handleCheckTranslation = async () => {
    const sourceSentence = question?.source_sentence || question?.chinese_sentence || '';
    if (!sourceSentence || !translationInput.trim()) {
      setTranslationError('请先获取题目并输入你的译文');
      return;
    }
    setTranslationError('');
    setTranslationSaveMessage('');
    setModeSwitchMessage('');
    setCheckingTranslation(true);
    try {
      const data = await checkTranslationAnswer({
        chineseSentence: question.chinese_sentence,
        sourceSentence,
        userTranslation: translationInput.trim(),
        direction: question.direction || direction,
        topic: question.topic || topic,
        difficulty: question.difficulty || difficulty,
        practiceMode,
        usedHint: showQuestionHint,
      });
      setTranslationResult(data);
      try {
        const recommendation = await getDifficultyRecommendation('translation');
        setDifficultyRecommendation(recommendation);
        if (!difficultyTouched && recommendation?.recommended_difficulty) {
          setDifficulty(recommendation.recommended_difficulty);
        }
      } catch {
        // keep current recommendation if refresh fails
      }
    } catch (error) {
      setTranslationError(typeof error === 'string' ? error : '翻译批改失败');
    } finally {
      setCheckingTranslation(false);
    }
  };

  const handleSaveTranslationMistake = async () => {
    if (!translationResult || !question) return;
    setTranslationSaveMessage('');
    try {
      await createMistake({
        module: 'translation',
        question_id: `translation_${Date.now()}`,
        question_type: question.direction || direction,
        error_type: 'translation_feedback',
        content: question.source_sentence || question.chinese_sentence || '',
        user_answer: translationInput.trim(),
        correct_answer: translationResult.correct_translation || '',
        explanation: [
          translationResult.evaluation || '',
          ...(translationResult.suggestions || []),
        ].filter(Boolean).join('\n'),
        difficulty: question.difficulty || difficulty,
        tags: ['translation', question.topic || topic, question.direction || direction],
      });
      setTranslationSaveMessage('已加入错题本。');
    } catch (error) {
      setTranslationSaveMessage(typeof error === 'string' ? error : '加入错题本失败');
    }
  };

  const handleCollectTranslationVocabulary = async () => {
    if (!translationResult && !translationInput.trim()) return;
    setTranslationSaveMessage('');
    const text = [
      translationInput,
      translationResult?.correct_translation,
      ...(translationResult?.reusable_expressions || []),
    ].filter(Boolean).join('\n');
    try {
      const data = await autoCollectVocabulary(text, 'translation', topic, 12);
      setTranslationSaveMessage(`已沉淀词汇：${data.imported || 0}，已存在：${data.skipped_existing || 0}`);
    } catch (error) {
      setTranslationSaveMessage(typeof error === 'string' ? error : '沉淀词汇失败');
    }
  };

  const handleDeepSearch = async () => {
    if (!searchQuery.trim()) {
      setSearchError('请输入要检索的问题');
      return;
    }
    setSearchError('');
    setSearchSaveMessage('');
    setSearchLoading(true);
    try {
      const data = await postDeepSearch(searchQuery.trim(), {
        enableAgenticRag: true,
        maxIterations: Number(searchMaxIterations) || 3,
      });
      setSearchResult(data);
    } catch (error) {
      setSearchError(typeof error === 'string' ? error : '深度搜索失败');
    } finally {
      setSearchLoading(false);
    }
  };

  const handleCollectSearchVocabulary = async () => {
    if (!searchResult) return;
    const summary = searchResult.search?.final_summary || searchResult.response || '';
    try {
      const data = await autoCollectVocabulary(summary, 'deep_search', 'research_material', 20);
      setSearchSaveMessage(`已从深搜结果沉淀词汇：${data.imported || 0}，已存在：${data.skipped_existing || 0}`);
    } catch (error) {
      setSearchSaveMessage(typeof error === 'string' ? error : '沉淀词汇失败');
    }
  };

  const handleGenerateTranslationFromSearch = () => {
    const summary = searchResult?.search?.final_summary || searchResult?.response || '';
    const firstSentence = summary
      .replace(/\[[0-9]+\]/g, '')
      .split(/[。！？\n]/)
      .map((x) => x.trim())
      .find((x) => x.length >= 12);
    if (!firstSentence) {
      setSearchSaveMessage('没有找到适合生成翻译练习的句子。');
      return;
    }
    setDirection(/[a-zA-Z]/.test(firstSentence) ? 'en_to_zh' : 'zh_to_en');
    setTopic('education');
    setQuestion({
      source_sentence: firstSentence,
      chinese_sentence: firstSentence,
      direction: /[a-zA-Z]/.test(firstSentence) ? 'en_to_zh' : 'zh_to_en',
      difficulty: 'medium',
      topic: 'deep_search',
      focus_points: ['深搜素材转译', '观点表达准确性'],
    });
    setTranslationInput('');
    setTranslationResult(null);
    setTab('translation');
  };

  const renderDifficultyAnalysis = (analysis) => {
    const blocks = [
      ['long_sentence', '长难句'],
      ['idioms_or_collocations', '习语/搭配'],
      ['grammar_points', '语法点'],
      ['cultural_notes', '文化差异'],
      ['technique_tips', '技巧建议'],
    ];
    if (!analysis || !blocks.some(([key]) => Array.isArray(analysis[key]) && analysis[key].length > 0)) {
      return null;
    }
    return (
      <div className="ts-analysis-grid">
        {blocks.map(([key, label]) => (
          Array.isArray(analysis[key]) && analysis[key].length > 0 ? (
            <div key={key} className="ts-mini-card">
              <h5>{label}</h5>
              <ul className="ts-list">
                {analysis[key].map((item, idx) => <li key={idx}>{item}</li>)}
              </ul>
            </div>
          ) : null
        ))}
      </div>
    );
  };

  const getQuestionHints = () => {
    const source = question?.source_sentence || question?.chinese_sentence || '';
    const focus = Array.isArray(question?.focus_points) ? question.focus_points : [];
    const isZhToEn = (question?.direction || direction) === 'zh_to_en';
    const grammarHint = isZhToEn
      ? '先找中文句子的主干，再决定英文主句；让步、原因、结果等关系可用 although / because / so that 处理。'
      : '先判断英文主句和从句边界，再按中文习惯重组语序，避免逐词硬译。';
    const vocabHint = isZhToEn
      ? '优先保留核心名词和动词，普通表达可替换为更自然搭配，例如 provide access to、play a role in。'
      : '注意固定搭配的整体含义，像 flexibility、interaction、efficiency 这类抽象词要译得自然。';
    return {
      grammar: focus[0] || grammarHint,
      vocabulary: focus[1] || vocabHint,
      sourceLength: source.length,
    };
  };

  const renderFocusReview = () => {
    const { vocab, patterns, points } = splitFocusPoints();
    if (!points.length) return null;
    return (
      <div className="ts-focus-review">
        {vocab.length > 0 && (
          <div>
            <h4>考察词汇/表达</h4>
            <div className="ts-chip-row">
              {vocab.map((item, idx) => <span key={idx} className="ts-chip">{item}</span>)}
            </div>
          </div>
        )}
        {patterns.length > 0 && (
          <div>
            <h4>考察句型/语法</h4>
            <ul className="ts-list">
              {patterns.map((item, idx) => <li key={idx}>{item}</li>)}
            </ul>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="home-page web-dashboard translation-search-page">
      <TopNav username={userData.username} />

      <div className="main-layout">
        <div className="sidebar">
          <SidebarMenu />
        </div>

        <div className="content-area content-shell">
          <main className="content-shell translation-search-content">
            <div className="web-page-head">
              <div>
                <h2>翻译与深搜</h2>
                <p>在同一页面完成翻译练习与深度检索，适合素材积累和表达训练联动。</p>
              </div>
              <div className="ts-tab-row">
                <button
                  type="button"
                  className={`ts-tab-btn${tab === 'translation' ? ' active' : ''}`}
                  onClick={() => setTab('translation')}
                >
                  翻译练习
                </button>
                <button
                  type="button"
                  className={`ts-tab-btn${tab === 'search' ? ' active' : ''}`}
                  onClick={() => setTab('search')}
                >
                  深度搜索
                </button>
              </div>
            </div>

            {tab === 'translation' && (
              <section className="card ts-panel">
                <h3>翻译练习</h3>
                <div className="ts-mode-switch" aria-label="翻译练习模式">
                  <button
                    type="button"
                    className={`ts-mode-btn${practiceMode === 'blind' ? ' active' : ''}`}
                    aria-pressed={practiceMode === 'blind'}
                    onClick={() => handlePracticeModeChange('blind')}
                  >
                    <span>盲译练习</span>
                    <small>批改后看考点</small>
                    {practiceMode === 'blind' && <em>当前模式</em>}
                  </button>
                  <button
                    type="button"
                    className={`ts-mode-btn${practiceMode === 'guided' ? ' active' : ''}`}
                    aria-pressed={practiceMode === 'guided'}
                    onClick={() => handlePracticeModeChange('guided')}
                  >
                    <span>词汇句型造句</span>
                    <small>先看目标表达</small>
                    {practiceMode === 'guided' && <em>当前模式</em>}
                  </button>
                </div>
                <div className={`ts-mode-summary ${practiceMode}`}>
                  <span className="ts-mode-badge">{currentMode.badge}</span>
                  <div>
                    <h4>{currentMode.title}</h4>
                    <p>{currentMode.description}</p>
                  </div>
                </div>
                <div className="ts-form-grid">
                  <label>
                    方向
                    <select value={direction} onChange={(e) => setDirection(e.target.value)}>
                      <option value="zh_to_en">中译英</option>
                      <option value="en_to_zh">英译中</option>
                    </select>
                  </label>
                  <label>
                    主题
                    <select value={topic} onChange={(e) => setTopic(e.target.value)}>
                      {topicOptions.map((item) => (
                        <option key={item.value} value={item.value}>{item.label}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    难度
                    <select
                      value={difficulty}
                      onChange={(e) => {
                        setDifficultyTouched(true);
                        setDifficulty(e.target.value);
                      }}
                    >
                      <option value="easy">基础</option>
                      <option value="medium">进阶</option>
                      <option value="hard">高阶</option>
                    </select>
                  </label>
                  <button type="button" className="ts-primary-btn" onClick={handleGenerateQuestion} disabled={generatingQuestion}>
                    {generatingQuestion ? '生成中...' : '生成题目'}
                  </button>
                </div>
                {difficultyRecommendation && (
                  <div className="ts-difficulty-recommendation">
                    <span>智能推荐：{difficultyRecommendation.label || '基础'}</span>
                    <p>{difficultyRecommendation.reason}</p>
                    {difficultyTouched && (
                      <button
                        type="button"
                        className="ts-inline-link"
                        onClick={() => {
                          setDifficultyTouched(false);
                          setDifficulty(difficultyRecommendation.recommended_difficulty || 'easy');
                        }}
                      >
                        恢复推荐难度
                      </button>
                    )}
                  </div>
                )}

                {(question?.source_sentence || question?.chinese_sentence) && (
                  <div className="ts-result-card ts-question-card">
                    <p className="ts-meta">
                      主题：{question.topic || topic} ｜ 难度：{question.difficulty || difficulty} ｜
                      方向：{(question.direction || direction) === 'zh_to_en' ? '中译英' : '英译中'}
                    </p>
                    <div className="ts-question-mode-line">
                      <span className="ts-mode-badge">{currentMode.badge}</span>
                      <span>{currentMode.title}</span>
                    </div>
                    {modeSwitchMessage && <p className="ts-mode-reset-note">{modeSwitchMessage}</p>}
                    <p className="ts-strong">题目：{question.source_sentence || question.chinese_sentence}</p>
                    {practiceMode === 'guided' && getFocusPoints().length > 0 && (
                      <div className="ts-guided-targets">
                        <p className="ts-meta">请尽量使用下面的目标表达完成造句。</p>
                        {renderFocusReview()}
                      </div>
                    )}
                    {practiceMode === 'blind' && (
                      <div className="ts-action-row">
                        <button type="button" className="ts-secondary-btn" onClick={() => setShowQuestionHint((v) => !v)}>
                          {showQuestionHint ? '收起提示' : '查看提示'}
                        </button>
                      </div>
                    )}
                    {practiceMode === 'blind' && showQuestionHint && (
                      <div className="ts-hint-box">
                        <div>
                          <h5>语法提示</h5>
                          <p>{getQuestionHints().grammar}</p>
                        </div>
                        <div>
                          <h5>词汇提示</h5>
                          <p>{getQuestionHints().vocabulary}</p>
                        </div>
                      </div>
                    )}
                    <textarea
                      className="ts-translation-input"
                      placeholder={
                        practiceMode === 'guided'
                          ? ((question.direction || direction) === 'zh_to_en' ? '请结合目标词汇和句型写出英文句子...' : '请结合目标表达写出自然中文句子...')
                          : ((question.direction || direction) === 'zh_to_en' ? '请输入你的英文译文...' : '请输入你的中文译文...')
                      }
                      value={translationInput}
                      onChange={(e) => setTranslationInput(e.target.value)}
                    />
                    <div className="ts-submit-row">
                      <p className="ts-meta">
                        {practiceMode === 'blind'
                          ? '建议先独立完成，再查看提示或提交批改。'
                          : '重点看目标词汇和句型是否用得准确、自然。'}
                      </p>
                      <button type="button" className="ts-primary-btn" onClick={handleCheckTranslation} disabled={checkingTranslation}>
                        {checkingTranslation ? '批改中...' : '提交批改'}
                      </button>
                    </div>
                  </div>
                )}

                {translationError && <p className="ts-error">{translationError}</p>}

                {translationResult && (
                  <div className="ts-result-card ts-feedback-card">
                    <div className="ts-feedback-head">
                      <div>
                        <p className="ts-meta">评分结果</p>
                        <h4>总分 {overall}</h4>
                      </div>
                      <div className="ts-score-grid">
                        <span><strong>{translationResult.accuracy}</strong>准确性</span>
                        <span><strong>{translationResult.fluency}</strong>流畅度</span>
                        <span><strong>{translationResult.grammar}</strong>语法</span>
                        <span><strong>{translationResult.vocabulary}</strong>词汇</span>
                      </div>
                    </div>
                    <div className="ts-feedback-section">
                      <h4>总体反馈</h4>
                      <p>{translationResult.evaluation}</p>
                    </div>
                    <div className="ts-feedback-section">
                      <h4>参考译文</h4>
                      <p>{translationResult.correct_translation}</p>
                    </div>
                    {getFocusPoints().length > 0 && (
                      <div className="ts-feedback-section">
                        <h4>本题考点复盘</h4>
                        {renderFocusReview()}
                      </div>
                    )}
                    {renderDifficultyAnalysis(translationResult.difficulty_analysis)}
                    {Array.isArray(translationResult.reusable_expressions) && translationResult.reusable_expressions.length > 0 && (
                      <div className="ts-feedback-section">
                        <h4>可复用表达</h4>
                        <div className="ts-chip-row">
                          {translationResult.reusable_expressions.map((item, idx) => (
                            <span key={idx} className="ts-chip">{item}</span>
                          ))}
                        </div>
                      </div>
                    )}
                    {Array.isArray(translationResult.suggestions) && translationResult.suggestions.length > 0 && (
                      <div className="ts-feedback-section">
                        <h4>改进建议</h4>
                        <ul className="ts-list">
                          {translationResult.suggestions.map((item, idx) => (
                            <li key={idx}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    <div className="ts-action-row">
                      <button type="button" className="ts-secondary-btn" onClick={handleSaveTranslationMistake}>
                        加入错题本
                      </button>
                      <button type="button" className="ts-secondary-btn" onClick={handleCollectTranslationVocabulary}>
                        沉淀到词汇本
                      </button>
                    </div>
                    {translationSaveMessage && <p className="ts-meta">{translationSaveMessage}</p>}
                  </div>
                )}
              </section>
            )}

            {tab === 'search' && (
              <section className="card ts-panel">
                <h3>深度搜索</h3>
                <div className="ts-form-grid">
                  <label className="ts-full">
                    检索问题
                    <textarea
                      placeholder="例如：请帮我深度分析雅思写作教育类话题近三年趋势"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                    />
                  </label>
                  <label>
                    迭代轮次
                    <input
                      type="number"
                      min={1}
                      max={6}
                      value={searchMaxIterations}
                      onChange={(e) => setSearchMaxIterations(e.target.value)}
                    />
                  </label>
                  <button type="button" className="ts-primary-btn" onClick={handleDeepSearch} disabled={searchLoading}>
                    {searchLoading ? '检索中...' : '开始深搜'}
                  </button>
                </div>

                {searchError && <p className="ts-error">{searchError}</p>}

                {searchResult && (
                  <div className="ts-result-card">
                    <h4>结论摘要</h4>
                    <p className="ts-pre">{searchResult.search?.final_summary || searchResult.response}</p>
                    <p className="ts-meta">
                      迭代轮次：{Array.isArray(searchResult.search?.iterations) ? searchResult.search.iterations.length : 0}
                    </p>
                    {Array.isArray(searchResult.search?.iterations) && searchResult.search.iterations.length > 0 && (
                      <>
                        <h4>搜索过程</h4>
                        <div className="ts-iteration-list">
                          {searchResult.search.iterations.map((item) => (
                            <div key={item.iteration} className="ts-mini-card">
                              <h5>第 {item.iteration} 轮</h5>
                              <p className="ts-strong">{item.query}</p>
                              <p className="ts-meta">
                                来源：{(item.sources || []).map((source) => `${source.type}(${(source.results || []).length})`).join(' / ') || '无'}
                              </p>
                            </div>
                          ))}
                        </div>
                      </>
                    )}
                    {Array.isArray(searchResult.search?.citations) && searchResult.search.citations.length > 0 && (
                      <>
                        <h4>参考来源</h4>
                        <ul className="ts-list">
                          {searchResult.search.citations.slice(0, 8).map((item) => (
                            <li key={item.id || item.url}>
                              [{item.id}] {item.title} {item.url ? `(${item.url})` : ''}
                            </li>
                          ))}
                        </ul>
                      </>
                    )}
                    {searchResult.rag && (
                      <p className="ts-meta">
                        RAG状态：accepted={String(searchResult.rag.accepted)}，iterations={searchResult.rag.iterations ?? 0}
                      </p>
                    )}
                    <div className="ts-action-row">
                      <button type="button" className="ts-secondary-btn" onClick={handleGenerateTranslationFromSearch}>
                        用摘要生成翻译练习
                      </button>
                      <button type="button" className="ts-secondary-btn" onClick={handleCollectSearchVocabulary}>
                        沉淀关键词到词汇本
                      </button>
                    </div>
                    {searchSaveMessage && <p className="ts-meta">{searchSaveMessage}</p>}
                  </div>
                )}
              </section>
            )}
          </main>
        </div>
      </div>
    </div>
  );
};

export default TranslationSearch;
