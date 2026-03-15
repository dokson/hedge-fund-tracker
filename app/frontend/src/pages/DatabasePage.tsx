import { Database, Terminal, AlertTriangle } from "lucide-react";
import DatabaseOperations from "@/components/DatabaseOperations";
import { IS_GH_PAGES_MODE } from "@/lib/config";

export default function DatabasePage() {
  return (
    <div className="space-y-5 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <Database className="h-6 w-6" /> Update Operations
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Invoke local Python commands from <code className="font-mono bg-muted px-1 py-0.5 rounded text-xs">database/updater.py</code>.
        </p>
      </div>

      {IS_GH_PAGES_MODE && (
        <div className="rounded-lg border border-warning/20 bg-warning/5 p-4 flex gap-3 items-start">
          <AlertTriangle className="h-5 w-5 text-warning shrink-0 mt-0.5" />
          <div className="text-sm text-warning-foreground">
            <p className="font-semibold text-warning">Backend Restricted</p>
            <p className="text-muted-foreground mt-0.5">
              Database operations require direct access to the local filesystem and Python environment. These operations are disabled in this static web version.
            </p>
          </div>
        </div>
      )}

      <DatabaseOperations />
    </div>
  );
}
