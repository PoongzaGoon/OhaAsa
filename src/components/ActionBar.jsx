function ActionBar({ onBack, onShare, shareLabel }) {
  return (
    <section className="section">
      <div className="actions">
        <button className="button secondary-button" onClick={onBack}>
          다시 입력하기
        </button>
        <button className="button" onClick={onShare}>
          {shareLabel}
        </button>
      </div>
    </section>
  );
}

export default ActionBar;
