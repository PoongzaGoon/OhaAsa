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

  const handleAnimationEnd = () => {
    if (transitionStage === 'fade-out') {
      setDisplayLocation(location);
      setTransitionStage('fade-in');
    }
  };
  return (
    <div
      className={`page-transition ${transitionStage}`}
      onAnimationEnd={handleAnimationEnd}
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
