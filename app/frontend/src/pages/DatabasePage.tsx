import { Database } from "lucide-react";
import DatabaseOperations from "@/components/DatabaseOperations";

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

      <DatabaseOperations />
    </div>
  );
}
