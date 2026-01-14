import { useEffect, useState } from 'react';
import { Routes, Route, useLocation } from 'react-router-dom';
import Layout from './components/Layout';
import Home from './pages/Home';
import Input from './pages/Input';
import Result from './pages/Result';
import Ranking from './pages/Ranking';

function App() {
  const location = useLocation();
  const [displayLocation, setDisplayLocation] = useState(location);
  const [transitionStage, setTransitionStage] = useState('fade-in');

  useEffect(() => {
    if (
      location.pathname !== displayLocation.pathname ||
      location.search !== displayLocation.search ||
      location.hash !== displayLocation.hash
    ) {
      setTransitionStage('fade-out');
    }
  }, [location, displayLocation]);

  useEffect(() => {
    if (transitionStage === 'pre-fade-in') {
      const raf = requestAnimationFrame(() => {
        setTransitionStage('fade-in');
      });
      return () => cancelAnimationFrame(raf);
    }
    return undefined;
  }, [transitionStage]);

  const handleTransitionEnd = (event) => {
    if (event.propertyName !== 'opacity') return;
    if (transitionStage === 'fade-out') {
      setDisplayLocation(location);
      setTransitionStage('pre-fade-in');
    }
  };

  return (
    <div
      className={`page-transition ${transitionStage}`}
      onTransitionEnd={handleTransitionEnd}
    >
      <Layout>
        <Routes location={displayLocation}>
          <Route path="/" element={<Home />} />
          <Route path="/input" element={<Input />} />
          <Route path="/result" element={<Result />} />
          <Route path="/ranking" element={<Ranking />} />
        </Routes>
      </Layout>
    </div>
  );
}

export default App;
