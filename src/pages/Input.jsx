import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import BirthInputCard from '../components/BirthInputCard';

function Input() {
  const navigate = useNavigate();
  const [birthdate, setBirthdate] = useState('');
  const [error, setError] = useState('');

  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);

  const validate = (value) => {
    if (!value) {
      return '생년월일을 입력해주세요.';
    }
    if (value > today) {
      return '미래 날짜는 입력할 수 없어요.';
    }
    return '';
  };

  const handleChange = (value) => {
    setBirthdate(value);
    setError(validate(value));
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
      birthdate={birthdate}
      error={error}
      onChange={handleChange}
      onSubmit={handleSubmit}
      disabled={!birthdate || !!error}
    />
  );
}

export default Input;
