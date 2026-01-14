function FortuneCards({ fortunes }) {
  return (
    <section className="section">
      <div className="grid cards-grid two-column">
        {fortunes.map((item) => (
          <div key={item.key} className="glass-card card">
            <div className="meta">
              <span className="tag">{item.name}</span>
              <span className="tag">{item.toneLabel}</span>
            </div>
            <div className="score">
              <span style={{ fontSize: 28 }}>{item.score}</span>
              <span>/ 100</span>
            </div>
            <div className="progress-bar score-bar" aria-label={`${item.name} 점수`}>
              <div className="progress-fill score-fill" data-score={item.score} />
            </div>
            <div className="headline">{item.headline}</div>
            <div className="detail">{item.detail}</div>
            <div className="tips">
              <div className="tip">Tip: {item.tip}</div>
              <div className="caution">주의: {item.caution}</div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default FortuneCards;
