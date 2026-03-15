import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import DashboardLayout from "@/components/DashboardLayout";
import Dashboard from "@/pages/Dashboard";
import { IS_GH_PAGES_MODE, BASE_PATH } from "@/lib/config";

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
import FeatureNotAvailable from "@/components/FeatureNotAvailable";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter basename={BASE_PATH || "/"}>
        <DashboardLayout>
          <Routes>
            {/* Core analysis routes — always available */}
            <Route path="/" element={<Dashboard />} />
            <Route path="/quarterly" element={<QuarterlyTrends />} />
            <Route path="/funds" element={<FundPortfolio />} />
            <Route path="/funds/:fundId" element={<FundPortfolio />} />
            <Route path="/stocks" element={<StockBrowser />} />
            <Route path="/stock/:ticker" element={<StockAnalysis />} />

            {/* Funds Config — read-only in GH Pages mode */}
            <Route path="/funds-config" element={<FundsConfig />} />

            {/* AI & Database routes — available but disabled in GH Pages mode */}
            <Route path="/ai-ranking" element={<AIRanking />} />
            <Route path="/ai-diligence" element={<AIDueDiligence />} />

            {/* Restricted routes — completely unreachable in GH Pages mode for security */}
            {!IS_GH_PAGES_MODE && (
              <>
                <Route path="/ai-settings" element={<AISettings />} />
                <Route path="/database" element={<DatabasePage />} />
              </>
            )}

            {/* 404 */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </DashboardLayout>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
