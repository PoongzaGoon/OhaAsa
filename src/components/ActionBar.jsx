function ActionBar({ onBack, onShare, onRanking, shareLabel }) {
  return (
    <section className="section">
      <div className="actions">
        <button className="button secondary-button" onClick={onBack}>
          다시 입력하기
        </button>
        <button className="button" onClick={onShare}>
          {shareLabel}
        </button>
        {onRanking && (
          <button className="button secondary-button" onClick={onRanking}>
            오하아사 전체 순위 보기
          </button>
        )}
      </div>
    </section>
  );
}

export default ActionBar;
