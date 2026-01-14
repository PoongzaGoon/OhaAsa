const prefersReducedMotion = () =>
  window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

const animateScoreBars = () => {
  const fills = document.querySelectorAll('.score-fill, .mini-fill');
  fills.forEach((fill) => {
    if (fill.dataset.animated) return;
    const raw = Number(fill.dataset.score ?? 0);
    const value = Math.min(100, Math.max(0, Number.isNaN(raw) ? 0 : raw));
    fill.dataset.animated = 'true';
    if (prefersReducedMotion()) {
      fill.style.width = `${value}%`;
      return;
    }
    fill.style.width = '0%';
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        fill.style.width = `${value}%`;
      });
    });
  });
};

const initScoreObserver = () => {
  const root = document.getElementById('root');
  if (!root) return;
  const observer = new MutationObserver(() => {
    animateScoreBars();
  });
  observer.observe(root, { subtree: true, childList: true });
  animateScoreBars();
};



export const initUiEffects = () => {
  if (typeof window === 'undefined') return;
  initScoreObserver();
};
