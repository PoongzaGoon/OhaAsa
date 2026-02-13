import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import FortuneSummary from '../components/FortuneSummary';
import FortuneCards from '../components/FortuneCards';
import LuckyPanel from '../components/LuckyPanel';
import ActionBar from '../components/ActionBar';
import { getTodayKstString, formatKstDisplay } from '../lib/dateKst';
import { generateFortune, normalizeFortuneJson } from '../lib/fortuneEngine';
import { getWesternZodiac } from '../lib/zodiacWestern';
import { saveFortune } from '../lib/storage';

const isValidBirthdate = (value, today) => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return false;
  return value <= today;
};

function Result() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [fortune, setFortune] = useState(null);
  const todayKst = useMemo(() => getTodayKstString(), []);
  const birthdate = searchParams.get('birthdate') || '';

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      if (!isValidBirthdate(birthdate, todayKst)) {
        navigate('/input', { replace: true });
        return;
      }
      let rank = null;
      let scoreOverrides = null;
      let ranking = null;
      try {
        const response = await fetch('/fortune.json', { cache: 'no-store' });
        if (response.ok) {
          const payload = normalizeFortuneJson(await response.json());
          const westernZodiac = getWesternZodiac(birthdate);
          const match = payload.rankings?.find((item) => item.sign_ko === westernZodiac);
          ranking = match || null;
          rank = match?.rank ?? null;
          scoreOverrides = match?.scores ?? null;
        }
      } catch (error) {
        rank = null;
        scoreOverrides = null;
        ranking = null;
      }
      if (cancelled) return;
      const next = generateFortune(birthdate, todayKst, { rank, scores: scoreOverrides, ranking });
      setFortune(next);
      saveFortune(next);
    };

    load();
    return () => {
      cancelled = true;
    };
  }, [birthdate, todayKst, navigate]);

  if (!fortune) return null;

  const shareSupported = typeof navigator !== 'undefined' && !!navigator.share;
  const shareLabel = shareSupported ? '공유하기' : '클립보드에 복사하기';

  const shareText = `오하아사 오늘의 운세 - ${formatKstDisplay(fortune.date)}\n${fortune.birthdate}의 운세를 확인해보세요!\n총운 ${fortune.fortunes[0].score}점, 행운 컬러 ${fortune.lucky.colorName}`;

  const handleShare = async () => {
    try {
      if (shareSupported) {
        await navigator.share({ title: '오하아사 오늘의 운세', text: shareText, url: window.location.href });
      } else if (navigator.clipboard) {
        await navigator.clipboard.writeText(`${shareText}\n${window.location.href}`);
        alert('클립보드에 복사했어요. 원하는 곳에 붙여넣기 해보세요!');
      }
    } catch (error) {
      alert('공유에 실패했습니다. 잠시 후 다시 시도해주세요.');
    }
  };

  return (
    <div className="result-layout">
      <div>
        <FortuneSummary
          dateDisplay={formatKstDisplay(fortune.date)}
          birthdate={fortune.birthdate}
          westernZodiac={fortune.westernZodiac}
          chineseZodiac={fortune.chineseZodiac}
          summary={fortune.summary}
          summaryTip={fortune.summaryTip}
          summaryWarning={fortune.summaryWarning}
        />
        <LuckyPanel lucky={fortune.lucky} />
        <ActionBar
          onBack={() => navigate('/input')}
          onShare={handleShare}
          onRanking={() => navigate('/ranking')}
          shareLabel={shareLabel}
        />
      </div>
      <div className="result-stack">
        <FortuneCards fortunes={fortune.fortunes} zodiacName={fortune.westernZodiac} />
      </div>
    </div>
  );
}

export default Result;
