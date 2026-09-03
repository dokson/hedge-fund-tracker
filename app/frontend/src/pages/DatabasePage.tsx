import { Database } from "lucide-react";
import DatabaseOperations from "@/components/DatabaseOperations";
import { PanelTitle } from "@/components/ui/PanelTitle";
import { usePageMeta, pageTitle } from "@/hooks/usePageMeta";
import { IS_GH_PAGES_MODE } from "@/lib/config";
import { ROUTES } from "@/lib/routes";
import { canonicalUrl } from "@/lib/seo";

export default function DatabasePage() {
  usePageMeta({
    title: pageTitle("Update Operations"),
    description:
      "Local database maintenance: run the Python updater commands that fetch and consolidate SEC filings into the tracker's dataset.",
    canonical: canonicalUrl(ROUTES.database),
  });

  return (
    <div className="space-y-6 max-w-screen-2xl">
      <div>
        <h1 className="page-title">
          <Database className="h-5 w-5 text-muted-foreground" aria-hidden="true" /> Update
          Operations
        </h1>
        <p className="text-sm text-muted-foreground mt-1.5">
          Invoke local Python commands from{" "}
          <code className="font-mono bg-muted px-1 py-0.5 text-xs">database/updater.py</code>.
        </p>
      </div>

      {IS_GH_PAGES_MODE && (
        <div className="frame text-sm" role="note">
          <div className="frame-title text-warning">
            <PanelTitle>Backend restricted</PanelTitle>
          </div>
          <p className="p-3 text-muted-foreground">
            Database operations require direct access to the local filesystem and Python
            environment. These operations are disabled in this static web version.
          </p>
        </div>
      )}

      <DatabaseOperations />
    </div>
  );
}
