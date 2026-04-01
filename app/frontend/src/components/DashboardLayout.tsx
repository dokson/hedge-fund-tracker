import { AppSidebar } from "@/components/AppSidebar";
import { SidebarProvider } from "@/components/ui/sidebar";
import { GithubIcon, BarChart3, Sun, Moon } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useTheme } from "next-themes";
import { BASE_PATH } from "@/lib/config";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const { theme, setTheme } = useTheme();
  return (
    <SidebarProvider>
      <div className="h-screen flex flex-col w-full">
        <header className="h-14 flex items-center justify-between border-b border-border px-5 shrink-0 bg-background z-10">
          <div
            className="flex items-center gap-3 cursor-pointer"
            onClick={() => navigate("/")}
          >
            <img src={`${BASE_PATH}/logo.png`} alt="Hedge Fund Tracker" className="h-9 w-9 rounded-lg shrink-0" />
            <div>
              <h1 className="text-lg font-bold tracking-tight text-foreground leading-tight">Hedge Fund Tracker</h1>
              <p className="text-[9px] text-muted-foreground leading-tight">by <a href="https://github.com/dokson" target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors">Alessandro Colace</a></p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              className="text-muted-foreground hover:text-foreground transition-colors p-1 rounded cursor-pointer"
              aria-label="Toggle theme"
            >
              <Sun className="h-5 w-5 hidden dark:block" />
              <Moon className="h-5 w-5 block dark:hidden" />
            </button>
            <a
              href="https://github.com/dokson/hedge-fund-tracker"
              target="_blank"
              rel="noopener noreferrer"
              className="text-muted-foreground hover:text-foreground transition-colors"
            >
              <GithubIcon className="h-5 w-5" />
            </a>
          </div>
        </header>
        <div className="flex flex-1 overflow-hidden">
          <AppSidebar />
          <main className="flex-1 overflow-auto p-6">
            {children}
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
}
