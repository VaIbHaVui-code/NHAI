import React, { useState } from 'react';
import HighwayDashboard from './HighwayDashboard';
import AdminPanel from './AdminPanel';

function App() {
  const [currentView, setCurrentView] = useState('dashboard'); // 'dashboard' | 'admin'

  return (
    <>
      {currentView === 'dashboard' && <HighwayDashboard onNavigate={setCurrentView} />}
      {currentView === 'admin' && <AdminPanel onNavigate={setCurrentView} />}
    </>
  );
}

export default App;