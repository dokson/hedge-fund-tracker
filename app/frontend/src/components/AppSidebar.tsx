import {
  FileText, BarChart3, Wallet, Search, ClipboardCheck, CandlestickChart, Settings2, Cpu, Database,
} from "lucide-react";
import { NavLink } from "@/components/NavLink";
import { useLocation } from "react-router-dom";
import { IS_GH_PAGES_MODE } from "@/lib/config";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarFooter,
} from "@/components/ui/sidebar";

const analysisNav = [
  { title: "Latest Filings", url: "/", icon: FileText },
  { title: "Quarterly Trends", url: "/quarterly", icon: BarChart3 },
  { title: "Hedge Fund Portfolios", url: "/funds", icon: Wallet },
  { title: "Stocks", url: "/stocks", icon: CandlestickChart },
];

const aiNav = [
  { title: "Most Promising Stocks", url: "/ai-ranking", icon: Search },
  { title: "Stock Due Diligence", url: "/ai-diligence", icon: ClipboardCheck },
];

const configNav = [
  { title: "Hedge Funds", url: "/funds-config", icon: Settings2 },
  ...(!IS_GH_PAGES_MODE ? [{ title: "AI Settings", url: "/ai-settings", icon: Cpu }] : []),
];

const databaseNav = [
  { title: "Update Operations", url: "/database", icon: Database },
];

export function AppSidebar() {
  const location = useLocation();

  const isActive = (path: string) => {
    if (path === "/") return location.pathname === "/";
    if (path === "/stocks") return location.pathname === "/stocks" || location.pathname.startsWith("/stock/");
    return location.pathname.startsWith(path);
  };

  return (
    <Sidebar collapsible="none">
      <SidebarContent className="pt-2">
        <SidebarGroup>
          <SidebarGroupLabel className="text-[10px] uppercase tracking-widest text-sidebar-foreground/50">
            Analysis
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {analysisNav.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild isActive={isActive(item.url)}>
                    <NavLink to={item.url} end={item.url === "/"}>
                      <item.icon className="h-4 w-4" />
                      <span>{item.title}</span>
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel className="text-[10px] uppercase tracking-widest text-sidebar-foreground/50">
            AI-Powered
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {aiNav.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild isActive={isActive(item.url)}>
                    <NavLink to={item.url}>
                      <item.icon className="h-4 w-4" />
                      <span>{item.title}</span>
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        <SidebarGroup>
          <SidebarGroupLabel className="text-[10px] uppercase tracking-widest text-sidebar-foreground/50">
            Configuration
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {configNav.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild isActive={isActive(item.url)}>
                    <NavLink to={item.url}>
                      <item.icon className="h-4 w-4" />
                      <span>{item.title}</span>
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>

        {!IS_GH_PAGES_MODE && (
          <SidebarGroup>
            <SidebarGroupLabel className="text-[10px] uppercase tracking-widest text-sidebar-foreground/50">
              Database
            </SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {databaseNav.map((item) => (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton asChild isActive={isActive(item.url)}>
                      <NavLink to={item.url}>
                        <item.icon className="h-4 w-4" />
                        <span>{item.title}</span>
                      </NavLink>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        )}
      </SidebarContent>

      <SidebarFooter className="px-4 py-3">
        <p className="text-[10px] text-sidebar-foreground/40">
          Data as of Q4 2025
        </p>
      </SidebarFooter>
    </Sidebar>
  );
}
