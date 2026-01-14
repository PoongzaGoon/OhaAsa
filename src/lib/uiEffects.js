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

const initPageTransitions = () => {
  const body = document.body;
  const applyEnter = () => {
    body.classList.remove('page-exit');
    body.classList.add('page-enter');
    requestAnimationFrame(() => {
      body.classList.add('page-enter-active');
    });
    window.setTimeout(() => {
      body.classList.remove('page-enter');
      body.classList.remove('page-enter-active');
    }, 320);
  };

  applyEnter();

  window.addEventListener('pageshow', () => {
    applyEnter();
  });

  document.addEventListener('click', (event) => {
    const link = event.target.closest('a');
    if (!link) return;
    if (link.target === '_blank' || link.hasAttribute('download')) return;
    if (link.origin !== window.location.origin) return;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const isSamePage =
      link.pathname === window.location.pathname &&
      link.search === window.location.search &&
      link.hash;
    if (isSamePage) return;
    if (prefersReducedMotion()) return;
    event.preventDefault();
    body.classList.add('page-exit');
    window.setTimeout(() => {
      window.location.href = link.href;
    }, 200);
  });
};

export const initUiEffects = () => {
  if (typeof window === 'undefined') return;
  initScoreObserver();
  initPageTransitions();
};
