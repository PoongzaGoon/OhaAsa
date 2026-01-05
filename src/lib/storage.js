const KEY = 'ohahasa-fortune-history';

export const saveFortune = (fortune) => {
  try {
    const existing = JSON.parse(localStorage.getItem(KEY) || '[]');
    const next = [fortune, ...existing].slice(0, 5);
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch (e) {
    // storage not available
  }
};

export const loadFortunes = () => {
  try {
    return JSON.parse(localStorage.getItem(KEY) || '[]');
  } catch (e) {
    return [];
  }
};
