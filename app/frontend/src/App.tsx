import { lazy, Suspense } from "react";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Loader2 } from "lucide-react";
import DashboardLayout from "@/components/DashboardLayout";
import Dashboard from "@/pages/Dashboard";
import Landing from "@/pages/Landing";
import { IS_GH_PAGES_MODE, BASE_PATH } from "@/lib/config";
import { ROUTES } from "@/lib/routes";

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
              {/* Home / landing — inside the shell so the sidebar persists */}
              <Route path={ROUTES.home} element={<Landing />} />

              {/* Core analysis routes — always available */}
              <Route path={ROUTES.latest} element={<Dashboard />} />
              <Route path={ROUTES.quarterly} element={<QuarterlyTrends />} />
              <Route path={ROUTES.funds} element={<FundPortfolio />} />
              <Route path={`${ROUTES.funds}/:fundId`} element={<FundPortfolio />} />
              <Route path={ROUTES.stocks} element={<StockBrowser />} />
              <Route path={`${ROUTES.stock}/:ticker`} element={<StockAnalysis />} />

              {/* AI routes — available but disabled in GH Pages mode */}
              <Route path={ROUTES.aiRanking} element={<AIRanking />} />
              <Route path={ROUTES.aiDiligence} element={<AIDueDiligence />} />

              {/* Restricted routes — completely unreachable in GH Pages mode for security */}
              {!IS_GH_PAGES_MODE && (
                <>
                  <Route path={ROUTES.fundsConfig} element={<FundsConfig />} />
                  <Route path={ROUTES.aiSettings} element={<AISettings />} />
                  <Route path={ROUTES.database} element={<DatabasePage />} />
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
