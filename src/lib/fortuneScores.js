export const normalizeOhaasaScores = (scores) => {
  if (!scores) return null;
  const overall = scores.overall ?? scores.total ?? null;
  const total = overall ?? scores.total ?? null;

  return {
    overall,
    total,
    love: scores.love ?? null,
    study: scores.study ?? null,
    money: scores.money ?? null,
    health: scores.health ?? null,
  };
};