function BirthInputCard({ birthdate, error, onChange, onSubmit, disabled }) {
  return (
    <section className="section">
      <div className="glass-card input-card">
        <div className="input-row">
          <label className="label" htmlFor="birthdate">
            생년월일
          </label>
          <input
            id="birthdate"
            className="date-input"
            type="date"
            value={birthdate}
            max={new Date().toISOString().slice(0, 10)}
            onChange={(e) => onChange(e.target.value)}
          />
          {error ? <div className="error">{error}</div> : <div className="helper">YYYY-MM-DD 형식으로 입력해주세요.</div>}
          <button className="button" onClick={onSubmit} disabled={disabled}>
            오늘의 운세 보기
          </button>
        </div>
      </div>
    </section>
  );
}

export default BirthInputCard;
