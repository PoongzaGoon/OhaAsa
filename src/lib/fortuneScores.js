const SCORE_KEYS = ['total', 'love', 'study', 'money', 'health'];

const clampScore = (value, fallback = null) => {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(0, Math.min(100, parsed));
};

export const scoreToPercent = (score) => clampScore(score, 0);

export const normalizeOhaasaScores = (scores) => {
  if (!scores || typeof scores !== 'object') return null;

  const next = {};
  const normalizedTotal = clampScore(scores.total ?? scores.overall, null);

  SCORE_KEYS.forEach((key) => {
    const value = clampScore(scores[key], null);
    next[key] = value;
  });

  next.total = normalizedTotal ?? next.total;

  if (next.total == null) {
    const categoryAverage = ['love', 'study', 'money', 'health']
      .map((key) => next[key])
      .filter(Number.isFinite);
    if (categoryAverage.length > 0) {
      const avg = Math.round(categoryAverage.reduce((acc, value) => acc + value, 0) / categoryAverage.length);
      next.total = clampScore(avg, 50);
    }
  }

  if (next.total == null) next.total = 50;
  return next;
};
