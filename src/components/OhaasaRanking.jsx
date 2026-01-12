import { useEffect, useMemo, useState } from 'react';

const CATEGORY_LABELS = {
  total: '총운',
  love: '연애',
  study: '학업',
  money: '금전',
  health: '건강',
};

const formatDate = (value) => {
  if (!value) return '';
  return value.replace(/-/g, '.');
};

function OhaasaRanking() {
  const [data, setData] = useState({ status: 'loading', rankings: [], error_message: null });
  const [fetchError, setFetchError] = useState('');

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const response = await fetch('/fortune.json', { cache: 'no-store' });
        if (!response.ok) {
          throw new Error('fortune.json을 불러오지 못했습니다.');
        }
        const payload = await response.json();
        if (!cancelled) {
          setData(payload);
        }
      } catch (error) {
        if (!cancelled) {
          setFetchError(error.message || '데이터를 불러오지 못했습니다.');
        }
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const rankings = useMemo(() => {
    return [...(data.rankings || [])].sort((a, b) => a.rank - b.rank);
  }, [data.rankings]);

  const statusMessage = fetchError
    ? fetchError
    : data.status === 'error'
      ? data.error_message || '데이터를 불러오지 못했습니다.'
      : data.status === 'partial'
        ? data.error_message || '일부 번역이 제공되지 않습니다.'
        : '';

  return (
    <section className="section">
      <div className="fortune-rank-header">
        <div>
          <h2 className="section-title">오늘의 오하아사 순위</h2>
          <p className="section-subtitle">아사히 오하아사 별자리 운세를 기반으로 정리했어요.</p>
        </div>
        <span className="tag">{formatDate(data.date_kst) || '업데이트 대기'}</span>
      </div>
      {statusMessage && <div className="status-banner">{statusMessage}</div>}
      <div className="rank-grid">
        {rankings.map((item) => {
          const isTop = item.rank <= 3;
          const message = item.message_ko || item.message_jp;
          return (
            <article key={`${item.rank}-${item.sign_jp}`} className={`glass-card rank-card ${isTop ? 'rank-top' : ''}`}>
              <div className="rank-card-header">
                <div className={`rank-badge rank-${item.rank}`}>#{item.rank}</div>
                <div>
                  <h3>{item.sign_ko || '알 수 없음'}</h3>
                  <p className="rank-subtitle">{item.sign_jp}</p>
                </div>
              </div>
              <p className="rank-message">{message}</p>
              {!item.message_ko && <p className="rank-translation-warning">번역 실패 · 일본어 원문</p>}
              <div className="rank-score">
                <span>overall {item.scores?.overall ?? 0}점</span>
                <div className="progress-bar">
                  <div className="progress-fill" style={{ width: `${item.scores?.overall ?? 0}%` }} />
                </div>
              </div>
              <div className="rank-categories">
                {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                  <div key={key} className="rank-category">
                    <div className="rank-category-label">
                      <span>{label}</span>
                      <span>{item.scores?.[key] ?? 0}</span>
                    </div>
                    <div className="mini-bar">
                      <div className="mini-fill" style={{ width: `${item.scores?.[key] ?? 0}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export default OhaasaRanking;
