import { createSeededRandom } from './seedRandom';
import { getWesternZodiac } from './zodiacWestern';
import { getChineseZodiac } from './zodiacChinese';
import { normalizeOhaasaScores } from './fortuneScores';
import { getTodayKstString } from './dateKst';

const CATEGORY_LABELS = {
  total: '총운',
  love: '연애운',
  study: '학업운',
  money: '금전운',
  health: '건강운',
};

const SIGN_KO_BY_KEY = {
  'jp_おひつじ座': '양자리',
  'jp_おうし座': '황소자리',
  'jp_ふたご座': '쌍둥이자리',
  'jp_かに座': '게자리',
  'jp_しし座': '사자자리',
  'jp_おとめ座': '처녀자리',
  'jp_てんびん座': '천칭자리',
  'jp_さそり座': '전갈자리',
  'jp_いて座': '사수자리',
  'jp_やぎ座': '염소자리',
  'jp_みずがめ座': '물병자리',
  'jp_うお座': '물고기자리',
};

const FALLBACK_TEXT = {
  low: {
    title: '리듬을 천천히 맞춰보세요',
    body: '할 일을 한 번에 밀어붙이기보다 우선순위를 정하면 훨씬 수월합니다. 작은 정리가 흐름을 안정시켜 줍니다.',
    tip: '가벼운 체크리스트로 부담을 줄여보세요.',
    warning: '급한 판단은 한 번 더 확인하는 편이 좋습니다.',
  },
  mid: {
    title: '무난한 흐름을 유지할 수 있어요',
    body: '평소 루틴을 지키면 안정적인 결과를 기대할 수 있습니다. 주변과의 협업에서도 균형이 잘 맞습니다.',
    tip: '계획한 일정의 완성도를 먼저 챙겨보세요.',
    warning: '사소한 피로 신호를 넘기지 마세요.',
  },
  high: {
    title: '기회가 눈에 잘 들어오는 날입니다',
    body: '좋은 타이밍이 이어질 가능성이 높습니다. 다만 속도보다 방향을 맞추면 성과가 더 단단해집니다.',
    tip: '작게라도 먼저 실행해 감을 잡아보세요.',
    warning: '과도한 확신보다는 점검 습관을 유지하세요.',
  },
};

const FALLBACK_LUCKY_COLORS = [
  { name: '네온 바이올렛', value: '#8B7BFF' },
  { name: '코발트 블루', value: '#5AA7FF' },
  { name: '코스믹 핑크', value: '#FF7BD8' },
  { name: '에메랄드 그린', value: '#6DE5AE' },
  { name: '샌드 골드', value: '#D8B56E' },
  { name: '라피스 네이비', value: '#1F2B6F' },
];

const FALLBACK_ITEMS = ['작은 메모장', '텀블러', '정리 파우치', '가벼운 카드 지갑'];
const FALLBACK_KEYWORDS = ['집중', '균형', '회복', '정리'];

const isDev = typeof import.meta !== 'undefined' && !!import.meta.env?.DEV;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

const devWarn = (...args) => {
  if (isDev) console.warn('[fortune-normalize]', ...args);
};

const parseRank = (value) => {
  if (Number.isInteger(value)) return value;
  if (typeof value === 'string') {
    const digits = value.match(/\d+/g)?.join('') || '';
    if (!digits) return null;
    return Number.parseInt(digits, 10);
  }
  return null;
};

const normalizeStatusTag = (value) => {
  const text = typeof value === 'string' ? value.trim() : '';
  if (text === '상승' || text === '하락' || text === '안정') return text;
  if (!text) return '안정';
  if (text.includes('상')) return '상승';
  if (text.includes('하')) return '하락';
  return '안정';
};

const pickTone = (score) => {
  if (score < 40) return 'low';
  if (score < 70) return 'mid';
  return 'high';
};

const getOverallRangeByRank = (rank) => {
  if (rank >= 1 && rank <= 3) return { min: 85, max: 100 };
  if (rank >= 4 && rank <= 6) return { min: 65, max: 85 };
  if (rank >= 7 && rank <= 9) return { min: 45, max: 65 };
  if (rank >= 10 && rank <= 12) return { min: 20, max: 45 };
  return null;
};

export const normalizeRanking = (ranking, index = 0) => {
  const warnings = [];
  const next = { ...(ranking || {}) };

  const parsedRank = parseRank(next.rank);
  next.rank = Number.isInteger(parsedRank) && parsedRank >= 1 && parsedRank <= 12 ? parsedRank : null;
  if (next.rank == null) warnings.push(`invalid rank at index ${index}`);

  next.sign_key = typeof next.sign_key === 'string' && next.sign_key.trim() ? next.sign_key.trim() : null;
  if (!next.sign_key) warnings.push(`missing sign_key at index ${index}`);

  if (!next.sign_ko && next.sign_key) {
    next.sign_ko = SIGN_KO_BY_KEY[next.sign_key] || '';
  }

  next.scores = normalizeOhaasaScores(next.scores);
  next.status_tag = normalizeStatusTag(next.status_tag ?? next.trend ?? next.toneLabel);

  if (!next.ai || typeof next.ai !== 'object') {
    next.ai = null;
  } else {
    const safeCards = Array.isArray(next.ai.cards) ? next.ai.cards : null;
    const safeSummary = next.ai.summary && typeof next.ai.summary === 'object' ? next.ai.summary : null;
    next.ai = {
      ...next.ai,
      cards: safeCards,
      summary: safeSummary,
    };
  }

  return { ranking: next, warnings };
};

export const normalizeFortuneJson = (data) => {
  const warnings = [];
  const fallbackDate = getTodayKstString();
  const dateCandidate = typeof data?.date_kst === 'string' ? data.date_kst.trim() : '';
  const date_kst = DATE_RE.test(dateCandidate) ? dateCandidate : fallbackDate;
  if (date_kst !== dateCandidate) warnings.push('invalid date_kst');

  const inputRankings = Array.isArray(data?.rankings) ? data.rankings : [];
  const normalized = inputRankings.map((item, index) => normalizeRanking(item, index));
  normalized.forEach(({ warnings: itemWarnings }) => warnings.push(...itemWarnings));

  const rankings = normalized
    .map(({ ranking }) => ranking)
    .filter((item) => Number.isInteger(item.rank) && item.rank >= 1 && item.rank <= 12)
    .sort((a, b) => a.rank - b.rank);

  const deduped = [];
  const seenRanks = new Set();
  rankings.forEach((item) => {
    if (seenRanks.has(item.rank)) {
      warnings.push(`duplicate rank ${item.rank}`);
      return;
    }
    seenRanks.add(item.rank);
    deduped.push(item);
  });

  const nextStatus = warnings.length > 0 && data?.status === 'ok' ? 'partial' : data?.status || 'ok';
  if (warnings.length > 0) devWarn({ warnings });

  return {
    source: data?.source || 'asahi_ohaasa',
    date_kst,
    updated_at_kst: data?.updated_at_kst || null,
    status: nextStatus,
    error_message: data?.error_message || '',
    rankings: deduped,
    warnings,
  };
};

const createFallbackCard = (key, score) => {
  const tone = pickTone(score);
  const template = FALLBACK_TEXT[tone];
  return {
    key,
    name: CATEGORY_LABELS[key],
    score,
    tone,
    toneLabel: tone === 'low' ? '주의' : tone === 'mid' ? '안정' : '상승',
    headline: template.title,
    detail: template.body,
    tip: template.tip,
    caution: template.warning,
  };
};

const AI_CATEGORY_BY_KEY = {
  total: 'total',
  love: 'love',
  study: 'study',
  money: 'money',
  health: 'health',
};

const createCardFromAi = (key, score, aiCards, statusTag) => {
  const expectedCategory = AI_CATEGORY_BY_KEY[key];
  const card = Array.isArray(aiCards) ? aiCards.find((item) => item?.category === expectedCategory) : null;
  if (!card) return null;
  return {
    key,
    name: CATEGORY_LABELS[key],
    score,
    tone: pickTone(score),
    toneLabel: statusTag || '안정',
    headline: card.vibe || card.headline || card.title,
    detail: card.detail,
    tip: card.tip,
    caution: card.warning,
  };
};

export const generateFortune = (birthdate, todayKst, options = {}) => {
  const { rank = null, scores = null, ranking = null } = options;
  const seed = `${todayKst}|${birthdate}|ohaasa-v2`;
  const rng = createSeededRandom(seed);
  const normalizedRanking = ranking ? normalizeRanking(ranking).ranking : null;
  const normalizedScores = normalizeOhaasaScores(scores || normalizedRanking?.scores);
  const totalRange = normalizedScores?.total == null ? getOverallRangeByRank(rank) : null;

  const scoreFor = (key) => {
    if (Number.isFinite(normalizedScores?.[key])) return normalizedScores[key];
    if (key === 'total' && totalRange) return rng.nextInt(totalRange.min, totalRange.max);
    return rng.nextInt(25, 98);
  };

  const aiCards = normalizedRanking?.ai?.cards || null;
  const fortunes = ['total', 'love', 'study', 'money', 'health'].map((key) => {
    const score = scoreFor(key);
    return createCardFromAi(key, score, aiCards, normalizedRanking?.status_tag) || createFallbackCard(key, score);
  });

  const aiLucky = normalizedRanking?.ai?.lucky_points;
  const fallbackColor = rng.pick(FALLBACK_LUCKY_COLORS);
  const lucky = {
    color: aiLucky?.color_hex || fallbackColor.value,
    colorName: aiLucky?.color_name || fallbackColor.name,
    number: Number.isInteger(aiLucky?.number) ? aiLucky.number : rng.nextInt(1, 9),
    item: aiLucky?.item || rng.pick(FALLBACK_ITEMS),
    keyword: aiLucky?.keyword || rng.pick(FALLBACK_KEYWORDS),
  };

  const aiSummary = normalizedRanking?.ai?.summary;
  const summaryText = aiSummary
    ? [aiSummary.one_liner, aiSummary.focus, aiSummary.title, aiSummary.body].filter(Boolean).join(' · ')
    : normalizedRanking?.message_ko || normalizedRanking?.message_jp || '오늘의 흐름을 차분히 살펴보세요.';

  return {
    date: todayKst,
    birthdate,
    westernZodiac: getWesternZodiac(birthdate),
    chineseZodiac: getChineseZodiac(birthdate),
    summary: summaryText,
    summaryTip: null,
    summaryWarning: null,
    fortunes,
    lucky,
  };
};
