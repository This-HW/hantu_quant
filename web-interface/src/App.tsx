import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import SimpleWatchlist from './pages/SimpleWatchlist';
import SimpleDailySelection from './pages/SimpleDailySelection';
import AIMonitoringPage from './pages/AIMonitoringPage';
import SimpleBacktest from './pages/SimpleBacktest';
import SettingsPage from './pages/SettingsPage';
import SystemMonitorPage from './pages/SystemMonitorPage';

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/watchlist" element={<SimpleWatchlist />} />
          <Route path="/daily-selection" element={<SimpleDailySelection />} />
          <Route path="/monitoring" element={<AIMonitoringPage />} />
          <Route path="/backtest" element={<SimpleBacktest />} />
          <Route path="/system" element={<SystemMonitorPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </Layout>
    </Router>
  );
}

export default App;
