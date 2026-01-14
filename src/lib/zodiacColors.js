export const ZODIAC_COLORS = {
  aries: '#E5533D',
  taurus: '#4F8A5B',
  gemini: '#F2B705',
  cancer: '#4A7EBB',
  leo: '#E08E1B',
  virgo: '#6B8E6E',
  libra: '#8A6BBE',
  scorpio: '#7B2C3F',
  sagittarius: '#2F8F9D',
  capricorn: '#5A5A5A',
  aquarius: '#3FA7D6',
  pisces: '#6A5ACD',
};

const ZODIAC_NAME_MAP = {
  양자리: 'aries',
  황소자리: 'taurus',
  쌍둥이자리: 'gemini',
  게자리: 'cancer',
  사자자리: 'leo',
  처녀자리: 'virgo',
  천칭자리: 'libra',
  전갈자리: 'scorpio',
  사수자리: 'sagittarius',
  염소자리: 'capricorn',
  물병자리: 'aquarius',
  물고기자리: 'pisces',
};

const toRgba = (hex, alpha) => {
  const value = hex.replace('#', '');
  const size = value.length === 3 ? 1 : 2;
  const toChannel = (start) => {
    const raw = value.slice(start, start + size);
    const expanded = size === 1 ? `${raw}${raw}` : raw;
    return parseInt(expanded, 16);
  };
  const r = toChannel(0);
  const g = toChannel(size);
  const b = toChannel(size * 2);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

export const getZodiacColorByName = (name) => {
  if (!name) return '#d4d4d8';
  const key = ZODIAC_NAME_MAP[name.trim()];
  return ZODIAC_COLORS[key] || '#d4d4d8';
};

export const getZodiacColorStyle = (name) => {
  const color = getZodiacColorByName(name);
  return {
    '--zodiac-color': color,
    '--zodiac-color-glow': toRgba(color, 0.25),
  };
};
