import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import DashboardLayout from "@/components/DashboardLayout";
import Dashboard from "@/pages/Dashboard";

import QuarterlyTrends from "@/pages/QuarterlyTrends";
import FundPortfolio from "@/pages/FundPortfolio";
import StockAnalysis from "@/pages/StockAnalysis";
import StockBrowser from "@/pages/StockBrowser";
import AIRanking from "@/pages/AIRanking";
import AIDueDiligence from "@/pages/AIDueDiligence";
import AISettings from "@/pages/AISettings";
import FundsConfig from "@/pages/FundsConfig";
import DatabasePage from "@/pages/DatabasePage";
import NotFound from "@/pages/NotFound";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <DashboardLayout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            
            <Route path="/quarterly" element={<QuarterlyTrends />} />
            <Route path="/funds" element={<FundPortfolio />} />
            <Route path="/funds/:fundId" element={<FundPortfolio />} />
            <Route path="/stocks" element={<StockBrowser />} />
            <Route path="/stock/:ticker" element={<StockAnalysis />} />
            <Route path="/ai-ranking" element={<AIRanking />} />
            <Route path="/ai-diligence" element={<AIDueDiligence />} />
            <Route path="/ai-settings" element={<AISettings />} />
            <Route path="/funds-config" element={<FundsConfig />} />
            <Route path="/database" element={<DatabasePage />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </DashboardLayout>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
