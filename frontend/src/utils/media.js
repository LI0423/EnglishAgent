/**
 * 音频/静态资源的 URL 拼装。
 *
 * 后端返回的 audio_url 可能是 `/media/tts/xxx.mp3` 这类相对路径，
 * 需要拼上 API 基地址。此前 VocabularyStudy.jsx / Vocabulary.jsx 各自实现了一份，
 * 容易在 VITE_API_URL 处理上分叉，这里统一。
 */

export const API_BASE = String(import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '');

export const toAudioSrc = (url) => {
  const raw = String(url || '').trim();
  if (!raw) return '';
  if (raw.startsWith('http://') || raw.startsWith('https://')) return raw;
  return raw.startsWith('/') ? `${API_BASE}${raw}` : `${API_BASE}/${raw}`;
};

export default toAudioSrc;
