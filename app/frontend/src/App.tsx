import { lazy, Suspense } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Loader2 } from "lucide-react";
import DashboardLayout from "@/components/DashboardLayout";
import Dashboard from "@/pages/Dashboard";
import { IS_GH_PAGES_MODE, BASE_PATH } from "@/lib/config";

// Route-level code splitting: each page ships as its own chunk and loads on navigation.
const QuarterlyTrends = lazy(() => import("@/pages/QuarterlyTrends"));
const FundPortfolio = lazy(() => import("@/pages/FundPortfolio"));
const StockAnalysis = lazy(() => import("@/pages/StockAnalysis"));
const StockBrowser = lazy(() => import("@/pages/StockBrowser"));
const AIRanking = lazy(() => import("@/pages/AIRanking"));
const AIDueDiligence = lazy(() => import("@/pages/AIDueDiligence"));
const AISettings = lazy(() => import("@/pages/AISettings"));
const FundsConfig = lazy(() => import("@/pages/FundsConfig"));
const DatabasePage = lazy(() => import("@/pages/DatabasePage"));
const NotFound = lazy(() => import("@/pages/NotFound"));

const queryClient = new QueryClient();

const RouteFallback = () => (
  <div className="flex items-center justify-center py-16 text-muted-foreground">
    <Loader2 className="h-5 w-5 animate-spin" />
  </div>
);

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter basename={BASE_PATH || "/"}>
        <DashboardLayout>
          <Suspense fallback={<RouteFallback />}>
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
          </Suspense>
        </DashboardLayout>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
