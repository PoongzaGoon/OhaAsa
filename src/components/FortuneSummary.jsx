function FortuneSummary({ dateDisplay, birthdate, westernZodiac, chineseZodiac }) {
  return (
    <section className="section">
      <div className="glass-card summary-card">
        <div className="summary-top">
          <div>
            <p className="helper">오늘 날짜 (KST)</p>
            <h2 style={{ margin: '6px 0 0' }}>{dateDisplay}</h2>
          </div>
          <div className="tag">{birthdate} 기준</div>
        </div>
        <div className="summary-main">
          <div className="zodiac-row">
            <span className="tag">서양 별자리: {westernZodiac}</span>
            <span className="tag">동양 띠: {chineseZodiac}</span>
          </div>
          <p className="detail" style={{ margin: 0 }}>
            별과 행성의 흐름을 담은 오늘의 인사이트를 확인해보세요.
          </p>
        </div>
      </div>
    </section>
  );
}

export default FortuneSummary;
