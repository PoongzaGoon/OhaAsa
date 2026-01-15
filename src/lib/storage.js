const KEY = 'ohahasa-fortune-history';
const BIRTH_KEY = 'ohaasa_birth';

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

export const setBirthDate = (birthDate) => {
  const expires = new Date();
  expires.setFullYear(expires.getFullYear() + 1);
  document.cookie = `${BIRTH_KEY}=${encodeURIComponent(birthDate)}; expires=${expires.toUTCString()}; path=/; samesite=lax`;
};

export const getBirthDate = () => {
  if (typeof document === 'undefined') {
    return '';
  }
  const cookies = document.cookie ? document.cookie.split('; ') : [];
  const entry = cookies.find((cookie) => cookie.startsWith(`${BIRTH_KEY}=`));
  if (!entry) {
    return '';
  }
  return decodeURIComponent(entry.slice(BIRTH_KEY.length + 1));
};

export const clearBirthDate = () => {
  document.cookie = `${BIRTH_KEY}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; samesite=lax`;
};
