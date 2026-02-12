import { useEffect, useMemo, useRef, useState } from 'react';
import { normalizeOhaasaScores } from '../lib/fortuneScores';
import { getZodiacColorStyle } from '../lib/zodiacColors';

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
  const [expandedRank, setExpandedRank] = useState(null);
  const detailRefs = useRef(new Map());
  const [detailHeights, setDetailHeights] = useState({});

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
        ? data.error_message || '일부 AI 멘트가 제공되지 않습니다.'
        : '';

  const handleToggle = (rank) => {
    setExpandedRank((prev) => (prev === rank ? null : rank));
  };

  const setDetailRef = (rank) => (node) => {
    if (node) {
      detailRefs.current.set(rank, node);
    } else {
      detailRefs.current.delete(rank);
    }
  };

  const updateDetailHeight = (rank) => {
    const node = detailRefs.current.get(rank);
    if (!node) return;
    setDetailHeights((prev) => ({ ...prev, [rank]: node.scrollHeight }));
  };

  useEffect(() => {
    if (expandedRank == null) return;
    updateDetailHeight(expandedRank);
  }, [expandedRank, rankings]);

  useEffect(() => {
    const handleResize = () => {
      if (expandedRank == null) return;
      updateDetailHeight(expandedRank);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [expandedRank]);

  return (
    <section className="section">
      <div className="fortune-rank-header">
        <div>
          <h2 className="section-title">오하아사 전체 순위</h2>
          <p className="section-subtitle">순위를 눌러 상세 멘트를 확인해보세요.</p>
        </div>
        <span className="tag">{formatDate(data.date_kst) || '업데이트 대기'}</span>
      </div>
      {statusMessage && <div className="status-banner">{statusMessage}</div>}
      <div className="ranking-list">
        {rankings.map((item) => {
          const message = item.message_ko || item.message_jp;
          const isExpanded = expandedRank === item.rank;
          const scores = normalizeOhaasaScores(item.scores) || {};
          const detailId = `ranking-detail-${item.rank}`;
          return (
            <div
              key={`${item.rank}-${item.sign_jp}`}
              className={`glass-card ranking-item ${isExpanded ? 'open' : ''}`}
              style={getZodiacColorStyle(item.sign_ko)}
            >
              <button
                className="ranking-toggle"
                type="button"
                onClick={() => handleToggle(item.rank)}
                aria-expanded={isExpanded}
                aria-controls={detailId}
              >
                <span className={`rank-badge rank-${item.rank}`}>#{item.rank}</span>
                <div className="ranking-sign">
                  <h3>{item.sign_ko || '알 수 없음'}</h3>
                  <p className="rank-subtitle">{item.sign_jp}</p>
                </div>
                <span className="ranking-hint">{isExpanded ? '닫기' : '자세히 보기'}</span>
              </button>
              <div
                className="ranking-details"
                id={detailId}
                ref={setDetailRef(item.rank)}
                aria-hidden={!isExpanded}
                style={{ maxHeight: isExpanded ? `${detailHeights[item.rank] ?? 0}px` : '0px' }}
              >
                <p className="rank-message">{message}</p>
                {!item.message_ko && <p className="rank-translation-warning">AI 생성 누락 · 일본어 원문</p>}
                <div className="rank-score">
                  <span>overall {scores.overall ?? 0}점</span>
                  <div className="progress-bar score-bar">
                    <div className="progress-fill score-fill" data-score={scores.overall ?? 0} />
                  </div>
                </div>
                <div className="rank-categories">
                  {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                    <div key={key} className="rank-category">
                      <div className="rank-category-label">
                        <span>{label}</span>
                        <span>{scores[key] ?? 0}</span>
                      </div>
                      <div className="mini-bar">
                        <div className="mini-fill" data-score={scores[key] ?? 0} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

export default OhaasaRanking;
