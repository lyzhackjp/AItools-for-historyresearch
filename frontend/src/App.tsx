import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import MainLayout from './components/layout/MainLayout';
import AgentSoloPage from './pages/AgentSolo';
import HomePage from './pages/Home';
import ManualWorkspacePage from './pages/ManualWorkspace';
import SettingsPage from './pages/Settings';
import TaskCenterPage from './pages/TaskCenter';
import WorkflowPage from './pages/Workflow';

function App() {
  return (
    <BrowserRouter>
      <MainLayout>
        <Routes>
          <Route path="/" element={<Navigate to="/home" replace />} />
          <Route path="/home" element={<HomePage />} />
          <Route path="/manual" element={<ManualWorkspacePage />} />
          <Route path="/agent-solo" element={<AgentSoloPage />} />
          <Route path="/workflow" element={<WorkflowPage />} />
          <Route path="/tasks" element={<TaskCenterPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/home" replace />} />
        </Routes>
      </MainLayout>
    </BrowserRouter>
  );
}

export default App;
