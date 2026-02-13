function Layout({ children }) {
  return (
    <div className="app-shell">
      <div className="bg-layers" aria-hidden>
        <div className="starfield" />
        <div className="constellation" />
      </div>
      <main className="content">
        <header className="header">
          <div className="brand">
            <div className="brand-mark">★</div>
            <div className="title-group">
              <h1>오하아사 오늘의 운세</h1>
              <p>KST 기준 운세로 오늘을 가볍게 점쳐보세요</p>
              <p className="header-note">번역과 조언은 ChatGPT를 활용해 제공돼요.</p>
            </div>
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}

export default Layout;
