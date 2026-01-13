import { useNavigate } from 'react-router-dom';
import OhaasaRanking from '../components/OhaasaRanking';

function Ranking() {
  const navigate = useNavigate();

  return (
    <div className="home-stack">
      <section className="section">
        <div className="actions">
          <button className="button secondary-button" onClick={() => navigate('/')}>
            시작 화면으로
          </button>
          <button className="button" onClick={() => navigate('/input')}>
            생년월일 입력하기
          </button>
        </div>
      </section>
      <OhaasaRanking />
    </div>
  );
}

export default Ranking;
