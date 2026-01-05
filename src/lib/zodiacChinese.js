const animals = ['쥐', '소', '호랑이', '토끼', '용', '뱀', '말', '양', '원숭이', '닭', '개', '돼지'];

export const getChineseZodiac = (birthdate) => {
  if (!birthdate) return '';
  const year = Number(birthdate.split('-')[0]);
  const index = (year - 4) % 12;
  return animals[index];
};
