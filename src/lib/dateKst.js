const pad = (num) => String(num).padStart(2, '0');

const getKstDate = () => {
  const now = new Date();
  const utc = now.getTime() + now.getTimezoneOffset() * 60000;
  return new Date(utc + 9 * 60 * 60000);
};

export const getTodayKstString = () => {
  const kst = getKstDate();
  const y = kst.getFullYear();
  const m = pad(kst.getMonth() + 1);
  const d = pad(kst.getDate());
  return `${y}-${m}-${d}`;
};

export const formatKstDisplay = (dateString) => {
  const [y, m, d] = dateString.split('-');
  return `${y}년 ${m}월 ${d}일`;
};
