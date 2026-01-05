function LuckyPanel({ lucky }) {
  return (
    <section className="section">
      <div className="glass-card lucky-panel">
        <div className="summary-top">
          <h3 style={{ margin: 0 }}>행운 포인트</h3>
          <div className="tag">오늘의 조합</div>
        </div>
        <div className="lucky-grid">
          <div className="lucky-item">
            <div className="helper">Lucky Color</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span
                style={{
                  width: 22,
                  height: 22,
                  borderRadius: '50%',
                  border: '1px solid var(--border)',
                  background: lucky.color,
                }}
                aria-label={lucky.color}
              />
              <strong>{lucky.colorName}</strong>
            </div>
          </div>
          <div className="lucky-item">
            <div className="helper">Lucky Number</div>
            <strong style={{ fontSize: 20 }}>{lucky.number}</strong>
          </div>
          <div className="lucky-item">
            <div className="helper">Lucky Item</div>
            <strong>{lucky.item}</strong>
          </div>
          <div className="lucky-item">
            <div className="helper">Lucky Keyword</div>
            <strong>{lucky.keyword}</strong>
          </div>
        </div>
      </div>
    </section>
  );
}

export default LuckyPanel;
