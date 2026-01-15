import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import BirthInputCard from '../components/BirthInputCard';

const getDaysInMonth = (year, month) => {
  if (!year || !month) {
    return 31;
  }
  return new Date(Number(year), Number(month), 0).getDate();
};

function Input() {
  const navigate = useNavigate();
  const [birthParts, setBirthParts] = useState({ year: '', month: '', day: '' });
  const [error, setError] = useState('');

  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const birthdate = useMemo(() => {
    if (!birthParts.year || !birthParts.month || !birthParts.day) {
      return '';
    }
    return `${birthParts.year}-${birthParts.month}-${birthParts.day}`;
  }, [birthParts]);

  const validate = (value) => {
    if (!value) {
      return '생년월일을 입력해주세요.';
    }
    if (value > today) {
      return '미래 날짜는 입력할 수 없어요.';
    }
    return '';
  };

  const handlePartsChange = (nextParts) => {
    const daysInMonth = getDaysInMonth(nextParts.year, nextParts.month);
    const normalizedDay =
      nextParts.day && Number(nextParts.day) <= daysInMonth ? nextParts.day : '';
    const normalizedParts = { ...nextParts, day: normalizedDay };
    setBirthParts(normalizedParts);

    const nextDate =
      normalizedParts.year && normalizedParts.month && normalizedParts.day
        ? `${normalizedParts.year}-${normalizedParts.month}-${normalizedParts.day}`
        : '';
    setError(nextDate ? validate(nextDate) : '');
  };

  const handleSubmit = () => {
    const validation = validate(birthdate);
    if (validation) {
      setError(validation);
      return;
    }
    navigate(`/result?birthdate=${birthdate}`);
  };

  return (
    <BirthInputCard
      birthParts={birthParts}
      error={error}
      onChangeParts={handlePartsChange}
      onSubmit={handleSubmit}
      disabled={!birthdate || !!error}
    />
  );
}

export default Input;
