import { HashRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import LandingScreen from './screens/LandingScreen';
import DashboardScreen from './screens/DashboardScreen';
import RingListScreen from './screens/RingListScreen';
import RingDetailScreen from './screens/RingDetailScreen';
import AccountDetailScreen from './screens/AccountDetailScreen';
import ReportScreen from './screens/ReportScreen';

export default function App() {
  return (
    <HashRouter>
      <Routes>
        {/* Landing page — outside Layout, no sidebar */}
        <Route index element={<LandingScreen />} />

        {/* Investigation console — inside Layout with sidebar */}
        <Route element={<Layout />}>
          <Route path="dashboard" element={<DashboardScreen />} />
          <Route path="report" element={<ReportScreen />} />
          <Route path="rings" element={<RingListScreen />} />
          <Route path="rings/:ringId" element={<RingDetailScreen />} />
          <Route path="accounts/:accountId" element={<AccountDetailScreen />} />
        </Route>
      </Routes>
    </HashRouter>
  );
}
