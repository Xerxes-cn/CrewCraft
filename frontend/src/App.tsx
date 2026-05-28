import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import CrewList from './pages/CrewList';
import CrewDetail from './pages/CrewDetail';
import CrewRun from './pages/CrewRun';
import TaskDetail from './pages/TaskDetail';

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<CrewList />} />
        <Route path="/crews/:id" element={<CrewDetail />} />
        <Route path="/crews/:id/run" element={<CrewRun />} />
        <Route path="/tasks/:id" element={<TaskDetail />} />
      </Route>
    </Routes>
  );
}
