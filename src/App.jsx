import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Home from './pages/Home';
import Input from './pages/Input';
import Result from './pages/Result';
import Ranking from './pages/Ranking';

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/input" element={<Input />} />
        <Route path="/result" element={<Result />} />
        <Route path="/ranking" element={<Ranking />} />
      </Routes>
    </Layout>
  );
}

export default App;
