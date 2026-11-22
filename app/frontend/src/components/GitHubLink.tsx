import { useQuery } from "@tanstack/react-query";
import { Star } from "lucide-react";

import { GitHubMark } from "@/components/GitHubMark";
import { REPO_API_URL, REPO_URL } from "@/lib/config";
import { cn } from "@/lib/utils";

const CACHE_KEY = "github:stars";
/** The unauthenticated GitHub API allows 60 calls an hour per visitor: read it at most this often. */
const CACHE_MS = 6 * 60 * 60 * 1000;

const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });

/** The repository's star count, cached in the browser; null when GitHub cannot be reached. */
async function fetchStars(): Promise<number | null> {
  try {
    const cached = JSON.parse(localStorage.getItem(CACHE_KEY) ?? "null") as {
      stars: number;
      at: number;
    } | null;
    if (cached && Date.now() - cached.at < CACHE_MS) return cached.stars;
  } catch {
    // A malformed cache entry is just refetched.
  }
  const response = await fetch(REPO_API_URL, {
    priority: "low",
    headers: { Accept: "application/vnd.github+json" },
  });
  if (!response.ok) return null;
  const body: { stargazers_count?: unknown } = await response.json();
  if (typeof body.stargazers_count !== "number") return null;
  localStorage.setItem(CACHE_KEY, JSON.stringify({ stars: body.stargazers_count, at: Date.now() }));
  return body.stargazers_count;
}

/**
 * The link to the source repository as a pill: the GitHub mark and name, then its
 * live star count once GitHub answers (the pill stays a plain link when it does not).
 */
export function GitHubLink({
  className,
  enabled = true,
}: {
  className?: string;
  enabled?: boolean;
}) {
  const { data: stars } = useQuery({
    queryKey: ["githubStars"],
    queryFn: fetchStars,
    enabled,
    staleTime: CACHE_MS,
    retry: false,
  });
  const hasStars = typeof stars === "number";
  return (
    <a
      href={REPO_URL}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={
        hasStars ? `GitHub repository, ${stars.toLocaleString("en-US")} stars` : "GitHub repository"
      }
      className={cn(
        "inline-flex h-8 items-center gap-2 rounded-full border border-border bg-card px-3 text-[13px] font-medium text-foreground transition-colors duration-[120ms] hover:bg-muted active:bg-secondary",
        className,
      )}
    >
      <GitHubMark className="h-4 w-4" />
      GitHub
      {hasStars && (
        <>
          <span aria-hidden="true" className="h-4 w-px bg-border" />
          <Star className="h-3.5 w-3.5 text-gold-text" aria-hidden="true" />
          <span className="tabular-nums">{compact.format(stars)}</span>
        </>
      )}
    </a>
  );
}
