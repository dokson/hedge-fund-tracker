import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { getGICSHierarchy, type GICSEntry } from "@/lib/dataService";
import { Input } from "@/components/ui/input";
import { Search, Loader2, ChevronRight, ChevronDown } from "lucide-react";
import {
  Zap, Mountain, Factory, ShoppingCart, Apple, Heart,
  BarChart3, Cpu, Radio, Plug, Building2,
} from "lucide-react";

// ── Sector config ──
const SECTOR_CONFIG: Record<string, { icon: React.ElementType; color: string; bg: string; border: string; accent: string }> = {
  "10": { icon: Zap,          color: "text-gray-400",    bg: "bg-gray-900",    border: "border-gray-500",    accent: "#9ca3af" },
  "15": { icon: Mountain,     color: "text-slate-400",   bg: "bg-slate-800",   border: "border-slate-500",   accent: "#94a3b8" },
  "20": { icon: Factory,      color: "text-blue-500",    bg: "bg-blue-950",    border: "border-blue-600",    accent: "#3b82f6" },
  "25": { icon: ShoppingCart,  color: "text-yellow-500",  bg: "bg-yellow-950",  border: "border-yellow-500",  accent: "#eab308" },
  "30": { icon: Apple,         color: "text-orange-500",  bg: "bg-orange-950",  border: "border-orange-500",  accent: "#f97316" },
  "35": { icon: Heart,         color: "text-red-400",     bg: "bg-red-950",     border: "border-red-400",     accent: "#f87171" },
  "40": { icon: BarChart3,     color: "text-gray-300",    bg: "bg-gray-800",    border: "border-gray-400",    accent: "#d1d5db" },
  "45": { icon: Cpu,           color: "text-emerald-400", bg: "bg-emerald-950", border: "border-emerald-500", accent: "#34d399" },
  "50": { icon: Radio,         color: "text-blue-400",    bg: "bg-blue-950",    border: "border-blue-400",    accent: "#60a5fa" },
  "55": { icon: Plug,          color: "text-teal-400",    bg: "bg-teal-950",    border: "border-teal-400",    accent: "#2dd4bf" },
  "60": { icon: Building2,     color: "text-indigo-300",  bg: "bg-indigo-950",  border: "border-indigo-400",  accent: "#a5b4fc" },
};

function getSectorConfig(code: string) {
  return SECTOR_CONFIG[code] || { icon: BarChart3, color: "text-muted-foreground", bg: "bg-muted", border: "border-border", accent: "#888" };
}

// ── Types ──
interface GICSNode {
  code: string;
  label: string;
  children: GICSNode[];
}

function buildGICSTree(entries: GICSEntry[]): GICSNode[] {
  const sectorMap = new Map<string, { label: string; groups: Map<string, { label: string; industries: Map<string, { label: string; subs: { code: string; label: string }[] }> }> }>();

  for (const e of entries) {
    if (!sectorMap.has(e.sectorCode)) sectorMap.set(e.sectorCode, { label: e.sector, groups: new Map() });
    const sector = sectorMap.get(e.sectorCode)!;
    if (!sector.groups.has(e.industryGroupCode)) sector.groups.set(e.industryGroupCode, { label: e.industryGroup, industries: new Map() });
    const group = sector.groups.get(e.industryGroupCode)!;
    if (!group.industries.has(e.industryCode)) group.industries.set(e.industryCode, { label: e.industry, subs: [] });
    const industry = group.industries.get(e.industryCode)!;
    if (!industry.subs.find((s) => s.code === e.subIndustryCode)) industry.subs.push({ code: e.subIndustryCode, label: e.subIndustry });
  }

  const tree: GICSNode[] = [];
  for (const [code, s] of sectorMap) {
    const groupNodes: GICSNode[] = [];
    for (const [gCode, g] of s.groups) {
      const indNodes: GICSNode[] = [];
      for (const [iCode, ind] of g.industries) {
        indNodes.push({ code: iCode, label: ind.label, children: ind.subs.map((sub) => ({ code: sub.code, label: sub.label, children: [] })) });
      }
      groupNodes.push({ code: gCode, label: g.label, children: indNodes });
    }
    tree.push({ code, label: s.label, children: groupNodes });
  }
  return tree.sort((a, b) => a.code.localeCompare(b.code));
}

// ── Depth labels ──
const DEPTH_LABELS = ["Industry Group", "Industry", "Sub-Industry"];

// ── Recursive horizontal tree branch ──
function TreeBranch({
  node,
  depth,
  accentColor,
  searchQuery,
  isLast,
}: {
  node: GICSNode;
  depth: number;
  accentColor: string;
  searchQuery: string;
  isLast: boolean;
}) {
  const [expanded, setExpanded] = useState(!!searchQuery);
  const hasChildren = node.children.length > 0;

  return (
    <div className="flex items-stretch">
      {/* Vertical connector line + horizontal branch */}
      <div className="flex flex-col items-center shrink-0 w-5">
        {/* Top half of vertical line */}
        <div className="w-px flex-1" style={{ backgroundColor: accentColor, opacity: 0.3 }} />
        {/* Horizontal connector */}
        <div className="w-5 h-px" style={{ backgroundColor: accentColor, opacity: 0.3 }} />
        {/* Bottom half of vertical line (hidden if last) */}
        <div
          className="w-px flex-1"
          style={{ backgroundColor: isLast ? "transparent" : accentColor, opacity: 0.3 }}
        />
      </div>

      <div className="flex flex-col min-w-0 py-0.5">
        {/* Node button */}
        <button
          onClick={() => hasChildren && setExpanded(!expanded)}
          className={`flex items-center gap-1.5 py-1 px-2 rounded-md transition-colors text-left
            ${hasChildren ? "hover:bg-muted/50 cursor-pointer" : "cursor-default"}
            ${depth === 0 ? "font-semibold text-sm" : depth === 1 ? "text-sm" : "text-xs text-muted-foreground"}`}
        >
          {hasChildren ? (
            expanded ? (
              <ChevronDown className="h-3 w-3 shrink-0" style={{ color: accentColor }} />
            ) : (
              <ChevronRight className="h-3 w-3 shrink-0" style={{ color: accentColor }} />
            )
          ) : (
            <span
              className="inline-block h-1.5 w-1.5 rounded-full shrink-0"
              style={{ backgroundColor: accentColor, opacity: 0.7 }}
            />
          )}
          <span className="font-mono text-[10px] text-muted-foreground shrink-0">{node.code}</span>
          <span className="truncate">{node.label}</span>
          {hasChildren && (
            <span className="text-[10px] text-muted-foreground shrink-0 ml-1">
              ({node.children.length})
            </span>
          )}
        </button>

        {/* Children: rendered horizontally (indented to the right) */}
        {expanded && hasChildren && (
          <div className="flex items-stretch">
            {/* Vertical line running down from parent */}
            <div className="shrink-0 w-5 flex justify-center">
              <div className="w-px h-full" style={{ backgroundColor: accentColor, opacity: 0.2 }} />
            </div>
            <div className="flex flex-col min-w-0">
              {node.children.map((child, i) => (
                <TreeBranch
                  key={child.code}
                  node={child}
                  depth={depth + 1}
                  accentColor={accentColor}
                  searchQuery={searchQuery}
                  isLast={i === node.children.length - 1}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main component ──
export default function GICSTreeVisual() {
  const [search, setSearch] = useState("");
  const [expandedSectors, setExpandedSectors] = useState<Set<string>>(new Set());

  const { data: gicsEntries = [], isLoading } = useQuery({
    queryKey: ["gics-hierarchy"],
    queryFn: getGICSHierarchy,
  });

  const gicsTree = useMemo(() => buildGICSTree(gicsEntries), [gicsEntries]);

  const filteredTree = useMemo(() => {
    if (!search) return gicsTree;
    const q = search.toLowerCase();
    function filterNode(node: GICSNode): GICSNode | null {
      if (node.label.toLowerCase().includes(q) || node.code.includes(q)) return node;
      const fc = node.children.map(filterNode).filter(Boolean) as GICSNode[];
      if (fc.length > 0) return { ...node, children: fc };
      return null;
    }
    return gicsTree.map(filterNode).filter(Boolean) as GICSNode[];
  }, [gicsTree, search]);

  // Auto-expand all when searching
  const effectiveExpanded = useMemo(() => {
    if (search) return new Set(filteredTree.map((s) => s.code));
    return expandedSectors;
  }, [search, filteredTree, expandedSectors]);

  const toggleSector = (code: string) => {
    setExpandedSectors((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  };

  const totals = useMemo(() => {
    let groups = 0, industries = 0, subs = 0;
    for (const s of gicsTree) {
      groups += s.children.length;
      for (const g of s.children) {
        industries += g.children.length;
        for (const i of g.children) subs += i.children.length;
      }
    }
    return { sectors: gicsTree.length, groups, industries, subs };
  }, [gicsTree]);

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground py-12 justify-center">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading GICS® hierarchy…
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row gap-4 items-start justify-between">
        <div className="relative w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search sector or industry…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 bg-card border-border"
          />
        </div>
        <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
          <span><strong className="text-foreground">{totals.sectors}</strong> Sectors</span>
          <span><strong className="text-foreground">{totals.groups}</strong> Industry Groups</span>
          <span><strong className="text-foreground">{totals.industries}</strong> Industries</span>
          <span><strong className="text-foreground">{totals.subs}</strong> Sub-Industries</span>
        </div>
      </div>

      {/* Vertical sector list with horizontal tree expansion */}
      <div className="space-y-1">
        {filteredTree.map((sector) => {
          const config = getSectorConfig(sector.code);
          const Icon = config.icon;
          const isExpanded = effectiveExpanded.has(sector.code);
          const subCount = sector.children.reduce(
            (a, g) => a + g.children.reduce((b, i) => b + i.children.length, 0), 0
          );

          return (
            <div key={sector.code} className="rounded-lg border border-border bg-card overflow-hidden">
              {/* Sector row — clickable */}
              <button
                onClick={() => toggleSector(sector.code)}
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-muted/30 transition-colors text-left"
              >
                {/* Icon */}
                <div
                  className={`h-9 w-9 rounded-full flex items-center justify-center shrink-0 ${config.bg} border-2 ${config.border}`}
                  style={{ borderColor: config.accent, opacity: 0.85 }}
                >
                  <Icon className="h-4 w-4" style={{ color: config.accent }} />
                </div>

                {/* Expand chevron */}
                {isExpanded ? (
                  <ChevronDown className="h-4 w-4 shrink-0" style={{ color: config.accent }} />
                ) : (
                  <ChevronRight className="h-4 w-4 shrink-0" style={{ color: config.accent }} />
                )}

                {/* Label */}
                <span className="font-mono text-xs text-muted-foreground w-6 shrink-0">{sector.code}</span>
                <span className="font-bold text-sm flex-1">{sector.label}</span>

                {/* Counts */}
                <div className="flex gap-3 text-[10px] text-muted-foreground shrink-0">
                  <span>{sector.children.length} groups</span>
                  <span>{sector.children.reduce((a, g) => a + g.children.length, 0)} ind.</span>
                  <span>{subCount} sub-ind.</span>
                </div>
              </button>

              {/* Expanded tree — horizontal branching */}
              {isExpanded && (
                <div className="border-t border-border px-4 py-2 overflow-x-auto">
                  <div className="flex flex-col min-w-0">
                    {sector.children.map((group, i) => (
                      <TreeBranch
                        key={group.code}
                        node={group}
                        depth={0}
                        accentColor={config.accent}
                        searchQuery={search}
                        isLast={i === sector.children.length - 1}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {filteredTree.length === 0 && (
        <p className="text-center text-muted-foreground py-8">No matching sectors.</p>
      )}
    </div>
  );
}
