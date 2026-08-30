import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import DashboardScreen from './screens/DashboardScreen';
import RingListScreen from './screens/RingListScreen';
import RingDetailScreen from './screens/RingDetailScreen';
import AccountDetailScreen from './screens/AccountDetailScreen';

export default function App() {
  return (
    <HashRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<DashboardScreen />} />
          <Route path="dashboard" element={<Navigate to="/" replace />} />
          <Route path="rings" element={<RingListScreen />} />
          <Route path="rings/:ringId" element={<RingDetailScreen />} />
          <Route path="accounts/:accountId" element={<AccountDetailScreen />} />
        </Route>
      </Routes>
    </HashRouter>
  );
}
