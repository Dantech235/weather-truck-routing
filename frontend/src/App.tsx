import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import PlannerPage from './pages/PlannerPage';
import PlanPage from './pages/PlanPage';

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Routes>
          <Route path="/" element={<PlannerPage />} />
          <Route path="/plan/:id" element={<PlanPage />} />
          <Route path="*" element={<PlannerPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
