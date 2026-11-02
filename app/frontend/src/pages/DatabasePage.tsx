import { Database } from "lucide-react";
import DatabaseOperations from "@/components/DatabaseOperations";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel } from "@/components/ui/Panel";
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
    <div className="min-w-0 space-y-6 max-w-screen-2xl">
      <PageHeader
        title="Update Operations"
        icon={Database}
        description="Fetch filings, review coverage gaps and apply corrections to your local dataset."
      />

      {IS_GH_PAGES_MODE && (
        <Panel title="Backend restricted" className="text-sm" headerClassName="text-warning">
          <p className="p-3 text-muted-foreground" role="note">
            Database operations require direct access to the local filesystem and Python
            environment. These operations are disabled in this static web version.
          </p>
        </Panel>
      )}

      <DatabaseOperations />
    </div>
  );
}
