import { useMemo, useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { getModels } from "@/lib/dataService";
import { AI_PROVIDERS, getConfiguredProviders } from "@/lib/aiClient";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

// Maps models.csv "Client" column to provider IDs used in aiClient.ts
const CLIENT_TO_PROVIDER_ID: Record<string, string> = {
  "GitHub":      "github",
  "Google":      "google",
  "Groq":        "groq",
  "HuggingFace": "huggingface",
  "OpenRouter":  "openrouter",
};

interface ModelSelectorProps {
  value: string;
  onChange: (modelId: string) => void;
  onProviderChange?: (providerId: string) => void;
  className?: string;
}

export default function ModelSelector({ value, onChange, onProviderChange, className }: ModelSelectorProps) {
  const { data: allModels = [] } = useQuery({ queryKey: ["models"], queryFn: getModels });
  const [configuredProviderIds, setConfiguredProviderIds] = useState<string[] | null>(null);

  useEffect(() => {
    getConfiguredProviders().then((providers) => {
      setConfiguredProviderIds(
        providers.filter(({ hasKey }) => hasKey).map(({ provider }) => provider.id)
      );
    });
  }, []);

  const availableModels = useMemo(() => {
    if (configuredProviderIds === null) return allModels;
    return allModels.filter((m) => {
      const pid = CLIENT_TO_PROVIDER_ID[m.client];
      return pid && configuredProviderIds.includes(pid);
    });
  }, [allModels, configuredProviderIds]);

  // Group by provider
  const groupedModels = useMemo(() => {
    const groups: { providerName: string; models: typeof availableModels }[] = [];
    for (const provider of AI_PROVIDERS) {
      const models = availableModels.filter(
        (m) => CLIENT_TO_PROVIDER_ID[m.client] === provider.id
      );
      if (models.length > 0) groups.push({ providerName: provider.name, models });
    }
    return groups;
  }, [availableModels]);

  const effectiveValue = availableModels.find((m) => m.id === value)
    ? value
    : availableModels[0]?.id || "";

  const handleChange = (modelId: string) => {
    onChange(modelId);
    const model = availableModels.find((m) => m.id === modelId);
    if (model && onProviderChange) {
      onProviderChange(CLIENT_TO_PROVIDER_ID[model.client] ?? "");
    }
  };

  if (availableModels.length === 0) {
    return (
      <div className="text-xs text-muted-foreground italic">
        No API keys configured — see AI Settings
      </div>
    );
  }

  return (
    <Select value={effectiveValue} onValueChange={handleChange}>
      <SelectTrigger className={`bg-card border-border ${className || "w-64"}`}>
        <SelectValue placeholder="Select model…" />
      </SelectTrigger>
      <SelectContent>
        {groupedModels.map(({ providerName, models }) => (
          <div key={providerName}>
            <div className="px-2 py-1.5 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
              {providerName}
            </div>
            {models.map((m) => (
              <SelectItem key={m.id} value={m.id}>
                <span className="text-sm">{m.description}</span>
              </SelectItem>
            ))}
          </div>
        ))}
      </SelectContent>
    </Select>
  );
}
