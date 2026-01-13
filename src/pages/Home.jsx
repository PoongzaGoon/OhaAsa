import { useNavigate } from 'react-router-dom';

function Home() {
  const navigate = useNavigate();

  return (
    <div className="home-stack">
      <section className="section">
        <div className="glass-card start-card">
          <h2 className="section-title">오늘의 운세 시작하기</h2>
          <p className="section-subtitle">원하는 메뉴를 선택해서 바로 이동하세요.</p>
          <div className="start-actions">
            <button className="button" onClick={() => navigate('/input')}>
              생년월일 입력하기
            </button>
            <button className="button secondary-button" onClick={() => navigate('/ranking')}>
              오하아사 전체 순위 보기
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

export default Home;
