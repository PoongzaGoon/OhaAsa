const getDaysInMonth = (year, month) => {
  if (!year || !month) {
    return 31;
  }
  return new Date(Number(year), Number(month), 0).getDate();
};

function BirthInputCard({ birthParts, error, onChangeParts, onSubmit, disabled }) {
  const currentYear = new Date().getFullYear();
  const years = Array.from({ length: currentYear - 1899 }, (_, index) => String(currentYear - index));
  const months = Array.from({ length: 12 }, (_, index) => String(index + 1).padStart(2, '0'));
  const daysInMonth = getDaysInMonth(birthParts.year, birthParts.month);
  const days = Array.from({ length: daysInMonth }, (_, index) => String(index + 1).padStart(2, '0'));

  return (
    <section className="section">
      <div className="glass-card input-card">
        <div className="input-row">
          <label className="label" htmlFor="birthdate">
            생년월일
          </label>
          <div className="date-select-group" id="birthdate">
            <select
              className="date-select"
              value={birthParts.year}
              onChange={(event) => onChangeParts({ ...birthParts, year: event.target.value })}
            >
              <option value="">년</option>
              {years.map((year) => (
                <option key={year} value={year}>
                  {year}년
                </option>
              ))}
            </select>
            <select
              className="date-select"
              value={birthParts.month}
              onChange={(event) => onChangeParts({ ...birthParts, month: event.target.value })}
            >
              <option value="">월</option>
              {months.map((month) => (
                <option key={month} value={month}>
                  {Number(month)}월
                </option>
              ))}
            </select>
            <select
              className="date-select"
              value={birthParts.day}
              onChange={(event) => onChangeParts({ ...birthParts, day: event.target.value })}
            >
              <option value="">일</option>
              {days.map((day) => (
                <option key={day} value={day}>
                  {Number(day)}일
                </option>
              ))}
            </select>
          </div>
          {error ? <div className="error">{error}</div> : <div className="helper">연/월/일을 선택하면 자동으로 저장돼요.</div>}
          <button className="button" onClick={onSubmit} disabled={disabled}>
            오늘의 운세 보기
          </button>
        </div>
      </div>
    </section>
  );
}

export default BirthInputCard;
