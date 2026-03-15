import { Brain, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function FeatureNotAvailable({ feature }: { feature: string }) {
  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="max-w-md text-center space-y-4">
        <div className="rounded-full bg-muted p-4 w-16 h-16 mx-auto flex items-center justify-center">
          <Brain className="h-8 w-8 text-muted-foreground" />
        </div>
        <h2 className="text-xl font-bold">{feature}</h2>
        <p className="text-muted-foreground">
          Questa funzione richiede un backend AI locale e non è disponibile nella versione web.
        </p>
        <div className="rounded-lg border border-border bg-card p-4 text-left text-sm space-y-2">
          <p className="font-semibold">Per utilizzare le funzioni AI:</p>
          <ol className="list-decimal list-inside space-y-1 text-muted-foreground">
            <li>Clona il repository</li>
            <li>Configura il file <code className="bg-muted px-1 rounded text-xs">.env</code> con le tue API key</li>
            <li>Esegui <code className="bg-muted px-1 rounded text-xs">python -m app.main</code></li>
          </ol>
        </div>
        <Button variant="outline" asChild>
          <a
            href="https://github.com/nicholasgaspar/hedge-fund-tracker"
            target="_blank"
            rel="noopener noreferrer"
          >
            <ExternalLink className="h-4 w-4 mr-2" />
            Vedi su GitHub
          </a>
        </Button>
      </div>
    </div>
  );
}
