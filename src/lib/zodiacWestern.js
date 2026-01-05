const ranges = [
  { name: '염소자리', start: '12-22', end: '01-19' },
  { name: '물병자리', start: '01-20', end: '02-18' },
  { name: '물고기자리', start: '02-19', end: '03-20' },
  { name: '양자리', start: '03-21', end: '04-19' },
  { name: '황소자리', start: '04-20', end: '05-20' },
  { name: '쌍둥이자리', start: '05-21', end: '06-21' },
  { name: '게자리', start: '06-22', end: '07-22' },
  { name: '사자자리', start: '07-23', end: '08-22' },
  { name: '처녀자리', start: '08-23', end: '09-23' },
  { name: '천칭자리', start: '09-24', end: '10-22' },
  { name: '전갈자리', start: '10-23', end: '11-22' },
  { name: '사수자리', start: '11-23', end: '12-21' },
];

const toDayValue = (mmdd) => parseInt(mmdd.replace('-', ''), 10);

export const getWesternZodiac = (birthdate) => {
  if (!birthdate) return '';
  const [, month, day] = birthdate.split('-');
  const value = toDayValue(`${month}-${day}`);

  const match = ranges.find(({ start, end }) => {
    const startVal = toDayValue(start);
    const endVal = toDayValue(end);
    if (startVal > endVal) {
      return value >= startVal || value <= endVal;
    }
    return value >= startVal && value <= endVal;
  });

  return match ? match.name : '';
};
