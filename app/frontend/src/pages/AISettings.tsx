import { useState, useEffect, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AI_PROVIDERS } from "@/lib/aiClient";
import {
  getModels,
  generateModelsCSV,
  saveFileToDisk,
  clearCache,
  isModelProvider,
  MODEL_PROVIDERS,
  PROVIDER_DISPLAY_NAMES,
  type AIModel,
  type ModelProvider,
} from "@/lib/dataService";
import { Cpu, Eye, EyeOff, Trash2, Save, Plus } from "lucide-react";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SearchInput } from "@/components/ui/SearchInput";
import { Field } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel } from "@/components/ui/Panel";
import { StatusChip } from "@/components/ui/StatusChip";
import { TextLink } from "@/components/ui/TextLink";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { usePageMeta, pageTitle } from "@/hooks/usePageMeta";
import { ROUTES } from "@/lib/routes";
import { matchesQuery } from "@/lib/utils";
import { canonicalUrl } from "@/lib/seo";
import { Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { IS_GH_PAGES_MODE } from "@/lib/config";

export default function AISettingsPage() {
  usePageMeta({
    title: pageTitle("AI Settings"),
    description:
      "Local configuration for the AI features: provider API keys and the model catalogue used by ranking and due diligence.",
    canonical: canonicalUrl(ROUTES.aiSettings),
  });

  return (
    <div className="min-w-0 space-y-6 max-w-screen-2xl [&_button]:min-h-10 md:[&_button]:min-h-0 [&_input]:min-h-10 md:[&_input]:min-h-0">
      <PageHeader
        title="AI Settings"
        icon={Cpu}
        description="Configure provider access and the models available for ranking and due diligence."
      />

      <Tabs defaultValue="keys">
        <TabsList>
          <TabsTrigger value="keys">API Keys</TabsTrigger>
          <TabsTrigger value="models">AI Models</TabsTrigger>
        </TabsList>
        <TabsContent value="keys" className="mt-6">
          <APIKeysTab />
        </TabsContent>
        <TabsContent value="models" className="mt-6">
          <ModelsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

/* ═══════════════════════════════════════════
   API Keys Tab
   ═══════════════════════════════════════════ */
const API_BASE = window.location.origin;

const CLIENT_TO_PROVIDER_ID: Record<string, string> = {
  Google: "google",
  Groq: "groq",
  Ollama: "ollama",
  OpenRouter: "openrouter",
  ZAI: "zai",
};

function APIKeysTab() {
  const [envKeys, setEnvKeys] = useState<Record<string, string>>({});
  const [visible, setVisible] = useState<Record<string, boolean>>({});
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [providerToDelete, setProviderToDelete] = useState<(typeof AI_PROVIDERS)[number] | null>(
    null,
  );
  const { data: allModels = [] } = useQuery({ queryKey: ["models"], queryFn: getModels });

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_BASE}/api/settings/env`, { signal: controller.signal })
      .then((r) => r.json())
      .then((data: Record<string, string>) => {
        setEnvKeys(data);
        const init: Record<string, string> = {};
        for (const p of AI_PROVIDERS) init[p.id] = data[p.envKey] || "";
        setDrafts(init);
      })
      .catch(() => {});
    return () => controller.abort();
  }, []);

  const configuredProviders = AI_PROVIDERS.map((provider) => ({
    provider,
    hasKey: Boolean(envKeys[provider.envKey]),
  }));

  const toggleVisibility = (id: string) => setVisible((prev) => ({ ...prev, [id]: !prev[id] }));

  // Send only what changed: the server merges into .env and owns every key it
  // does not expose, so the deployment secrets never round-trip through here.
  const saveToEnv = async (updates: Record<string, string>) => {
    await fetch(`${API_BASE}/api/settings/env`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    });
    setEnvKeys((prev) => {
      const next = { ...prev, ...updates };
      for (const [key, value] of Object.entries(updates)) {
        if (!value) delete next[key];
      }
      return next;
    });
  };

  const handleSave = async (provider: (typeof AI_PROVIDERS)[number]) => {
    const key = drafts[provider.id]?.trim() || "";
    try {
      await saveToEnv({ [provider.envKey]: key });
      toast.success(key ? `API key saved for ${provider.name}` : "API key removed");
    } catch {
      toast.error("Failed to save key");
    }
  };

  const handleDeleteRequest = (provider: (typeof AI_PROVIDERS)[number]) => {
    setProviderToDelete(provider);
    setDeleteDialogOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!providerToDelete) return;
    setDrafts((prev) => ({ ...prev, [providerToDelete.id]: "" }));
    try {
      await saveToEnv({ [providerToDelete.envKey]: "" });
      toast.success("API key removed");
    } catch {
      toast.error("Failed to remove key");
    }
    setDeleteDialogOpen(false);
    setProviderToDelete(null);
  };

  const configuredCount = configuredProviders.filter(({ hasKey }) => hasKey).length;

  return (
    <div className="space-y-5">
      <p className="text-sm text-muted-foreground">
        Keys are saved to your local <code className="font-mono text-xs">.env</code> file, which is
        not tracked by Git.
      </p>

      {IS_GH_PAGES_MODE && (
        <Panel title="Read-only mode" className="text-sm">
          <p className="p-3 text-muted-foreground" role="note">
            Configuration is disabled in this web demo. To manage API keys and models, run the
            application in your local environment.
          </p>
        </Panel>
      )}

      {/* Provider status overview */}
      <Panel title="Provider access">
        <div className="p-3 space-y-4">
          <p className="text-sm tabular-nums">
            <span className="metric-label mr-2">Configured</span>
            {configuredCount} / {AI_PROVIDERS.length}
          </p>
          <div className="divide-y divide-border">
            {configuredProviders.map(({ provider, hasKey }) => {
              const models = allModels.filter(
                (m) => CLIENT_TO_PROVIDER_ID[m.client] === provider.id,
              );
              return (
                <div key={provider.id} className="flex flex-wrap items-center gap-2 py-2 text-sm">
                  <span className="min-w-0 flex-1">{provider.name}</span>
                  {hasKey && models.length > 0 && (
                    <span className="text-xs text-muted-foreground tabular-nums">
                      {models.length} model{models.length > 1 ? "s" : ""}
                    </span>
                  )}
                  <StatusChip tone={hasKey ? "positive" : "warning"}>
                    {hasKey ? "Configured" : "Missing key"}
                  </StatusChip>
                </div>
              );
            })}
          </div>

          {configuredCount === 0 && (
            <p className="text-xs text-negative">
              No API key configured. Add at least one key below to enable AI features.
            </p>
          )}

          <p className="text-xs text-muted-foreground">
            Each AI page lets you select which model to use from the available providers.
          </p>
        </div>
      </Panel>

      {/* Delete API Key Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="max-h-[90dvh] w-[calc(100%_-_2rem)] overflow-y-auto break-words sm:max-w-md [&_button]:min-h-10">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <Trash2 className="h-5 w-5" aria-hidden="true" /> Remove API Key
            </DialogTitle>
            <DialogDescription>
              You are about to remove the API key for <strong>{providerToDelete?.name}</strong>.
            </DialogDescription>
          </DialogHeader>
          <div className="py-2 text-sm text-muted-foreground space-y-2">
            <p>
              This will permanently delete the key from the{" "}
              <code className="font-mono bg-muted px-1 py-0.5 text-xs">.env</code> file on disk.
              Since <code className="font-mono bg-muted px-1 py-0.5 text-xs">.env</code> is not
              tracked by Git,{" "}
              <strong className="text-foreground">this operation cannot be undone</strong>: the key
              cannot be recovered from version history.
            </p>
            <p>Make sure you have a copy of the key before proceeding.</p>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleConfirmDelete}>
              Remove Key
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* API Keys management */}
      <div className="space-y-3">
        <h2 className="section-title">API Keys</h2>

        {configuredProviders.map(({ provider, hasKey }) => {
          const isVisible = visible[provider.id] || false;
          const draft = drafts[provider.id] || "";

          return (
            <Panel
              key={provider.id}
              title={provider.name}
              level={3}
              headerClassName="h-auto min-h-11 flex-wrap py-2"
              aside={
                <>
                  <StatusChip tone={hasKey ? "positive" : "warning"}>
                    {hasKey ? "Configured" : "Missing key"}
                  </StatusChip>
                  <TextLink
                    href={provider.link}
                    arrow
                    className="min-h-10 text-xs font-normal md:min-h-0"
                  >
                    Get key
                  </TextLink>
                </>
              }
            >
              <div className="p-3 space-y-3">
                <Field label={`${provider.name} API key`} htmlFor={`api-key-${provider.id}`}>
                  <code className="break-all text-xs font-mono text-muted-foreground">
                    {provider.envKey}
                  </code>
                  <div className="flex gap-2">
                    <div className="relative min-w-0 flex-1">
                      <Input
                        id={`api-key-${provider.id}`}
                        type={isVisible ? "text" : "password"}
                        value={
                          hasKey
                            ? isVisible
                              ? envKeys[provider.envKey] || ""
                              : "••••••••••••"
                            : draft
                        }
                        onChange={
                          hasKey
                            ? undefined
                            : (e) =>
                                setDrafts((prev) => ({ ...prev, [provider.id]: e.target.value }))
                        }
                        placeholder={hasKey ? "" : provider.hint}
                        aria-label={`${provider.name} API key`}
                        className="h-10 pr-11 font-mono text-xs"
                        autoComplete="off"
                        spellCheck={false}
                        readOnly={hasKey}
                      />
                      <button
                        type="button"
                        onClick={() => toggleVisibility(provider.id)}
                        aria-label={isVisible ? "Hide API key" : "Show API key"}
                        className="absolute right-0 top-0 h-10 w-10 inline-flex items-center justify-center rounded-md text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        {isVisible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>

                    {hasKey ? (
                      <Button
                        variant="outline"
                        size="icon"
                        onClick={() => handleDeleteRequest(provider)}
                        title="Remove key"
                        aria-label={`Remove ${provider.name} key`}
                        className="h-10 w-10 shrink-0 text-negative hover:text-negative"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    ) : (
                      <Button
                        variant={draft.trim() ? "default" : "outline"}
                        size="icon"
                        onClick={() => handleSave(provider)}
                        title="Save key"
                        aria-label={`Save ${provider.name} key`}
                        className="h-10 w-10 shrink-0"
                        disabled={!draft.trim()}
                      >
                        <Save className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                </Field>

                {hasKey && (
                  <div className="space-y-1 pt-1">
                    <p className="metric-label">Available models</p>
                    {allModels
                      .filter((m) => CLIENT_TO_PROVIDER_ID[m.client] === provider.id)
                      .map((m) => (
                        <p key={m.id} className="break-words text-xs text-muted-foreground">
                          {m.description}
                        </p>
                      ))}
                  </div>
                )}
              </div>
            </Panel>
          );
        })}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════
   Models Tab
   ═══════════════════════════════════════════ */
function ModelsTab() {
  const [modelSearch, setModelSearch] = useState("");
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [modelToDelete, setModelToDelete] = useState<AIModel | null>(null);

  const [newModelId, setNewModelId] = useState("");
  const [newModelDesc, setNewModelDesc] = useState("");
  const [newModelProvider, setNewModelProvider] = useState<ModelProvider>("Google");

  const queryClient = useQueryClient();

  const { data: models = [], isLoading: modelsLoading } = useQuery({
    queryKey: ["aiModels"],
    queryFn: getModels,
  });

  const filteredModels = useMemo(() => {
    return models.filter((m) => matchesQuery(modelSearch, m.id, m.description, m.client));
  }, [models, modelSearch]);

  const modelsByClient = useMemo(() => {
    const groups = new Map<string, AIModel[]>();
    for (const m of filteredModels) {
      const arr = groups.get(m.client) || [];
      arr.push(m);
      groups.set(m.client, arr);
    }
    return groups;
  }, [filteredModels]);

  const invalidateModels = () => {
    clearCache("models");
    void queryClient.invalidateQueries({ queryKey: ["aiModels"] });
  };

  const handleAddModel = async () => {
    if (!newModelId.trim() || !newModelDesc.trim()) return;
    const updatedModels: AIModel[] = [
      ...models,
      { id: newModelId.trim(), description: newModelDesc.trim(), client: newModelProvider },
    ];
    const csv = generateModelsCSV(updatedModels);
    try {
      await saveFileToDisk(csv, "models.csv");
      toast.success(`Model "${newModelDesc.trim()}" added`);
      invalidateModels();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e));
    }
    setAddDialogOpen(false);
    resetAddForm();
  };

  const handleConfirmDelete = async () => {
    if (!modelToDelete) return;
    const updatedModels = models.filter((m) => m.id !== modelToDelete.id);
    const csv = generateModelsCSV(updatedModels);
    try {
      await saveFileToDisk(csv, "models.csv");
      toast.success(`Model "${modelToDelete.description}" removed`);
      invalidateModels();
    } catch (e: unknown) {
      toast.error(e instanceof Error ? e.message : String(e));
    }
    setDeleteDialogOpen(false);
    setModelToDelete(null);
  };

  const resetAddForm = () => {
    setNewModelId("");
    setNewModelDesc("");
    setNewModelProvider("Google");
  };

  const displayName = (client: string) => PROVIDER_DISPLAY_NAMES[client] || client;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <SearchInput
          label="Search model, provider"
          size="sm"
          value={modelSearch}
          onChange={(e) => setModelSearch(e.target.value)}
          wrapperClassName="min-w-0 flex-1 basis-full sm:basis-auto sm:max-w-sm"
        />
        <span className="text-xs text-muted-foreground tabular-nums">
          {filteredModels.length} / {models.length} models
        </span>
        <Button
          size="sm"
          className="gap-1.5 ml-auto"
          onClick={() => {
            resetAddForm();
            setAddDialogOpen(true);
          }}
        >
          <Plus className="h-3.5 w-3.5" aria-hidden="true" /> Add Model
        </Button>
      </div>

      <p className="text-xs text-muted-foreground">
        Source: <code className="font-mono bg-muted px-1 py-0.5">database/models.csv</code>.
        Providers: {MODEL_PROVIDERS.map((p) => PROVIDER_DISPLAY_NAMES[p] || p).join(", ")}
      </p>

      {modelsLoading ? (
        <div className="flex items-center gap-2 text-muted-foreground py-8 justify-center">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading models…
        </div>
      ) : models.length === 0 ? (
        <EmptyState padding="sm" title="No models configured. Add one to get started." />
      ) : filteredModels.length === 0 ? (
        <EmptyState padding="sm" title="No models match your search." />
      ) : (
        <div className="space-y-4">
          {[...modelsByClient.entries()].map(([client, clientModels]) => (
            <Panel
              key={client}
              title={displayName(client)}
              aside={
                <span className="tabular-nums">
                  {clientModels.length} model{clientModels.length !== 1 ? "s" : ""}
                </span>
              }
            >
              <div className="divide-y divide-border">
                {clientModels.map((m) => (
                  <div key={m.id} className="flex items-start justify-between gap-3 px-3 py-3">
                    <div className="min-w-0 space-y-1">
                      <p className="break-words text-sm font-medium">{m.description}</p>
                      <p className="break-all text-xs text-muted-foreground font-mono">{m.id}</p>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-10 w-10 shrink-0 text-negative hover:text-negative md:h-8 md:w-8"
                      onClick={() => {
                        setModelToDelete(m);
                        setDeleteDialogOpen(true);
                      }}
                      title="Remove model"
                      aria-label={`Remove model ${m.description}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                ))}
              </div>
            </Panel>
          ))}
        </div>
      )}

      {/* Add Model Dialog */}
      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent className="max-h-[90dvh] w-[calc(100%_-_2rem)] overflow-y-auto sm:max-w-md [&_button]:min-h-10 [&_input]:min-h-10">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Plus className="h-5 w-5" aria-hidden="true" /> Add AI Model
            </DialogTitle>
            <DialogDescription>Add a new model to the configuration.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <Field label="Provider" htmlFor="model-provider">
              <Select
                value={newModelProvider}
                onValueChange={(v) => {
                  if (isModelProvider(v)) setNewModelProvider(v);
                }}
              >
                <SelectTrigger id="model-provider" className="min-h-10 bg-card">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {MODEL_PROVIDERS.map((p) => (
                    <SelectItem key={p} value={p}>
                      {PROVIDER_DISPLAY_NAMES[p] || p}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
            <Field label="Model ID" htmlFor="model-id">
              <Input
                id="model-id"
                placeholder="e.g. xai/grok-3-mini"
                value={newModelId}
                onChange={(e) => setNewModelId(e.target.value)}
                className="font-mono text-sm"
              />
            </Field>
            <Field label="Description" htmlFor="model-desc">
              <Input
                id="model-desc"
                placeholder="e.g. Grok-3 Mini (best)"
                value={newModelDesc}
                onChange={(e) => setNewModelDesc(e.target.value)}
              />
            </Field>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setAddDialogOpen(false)}>
              Cancel
            </Button>
            <Button disabled={!newModelId.trim() || !newModelDesc.trim()} onClick={handleAddModel}>
              Add Model
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Model Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="max-h-[90dvh] w-[calc(100%_-_2rem)] overflow-y-auto break-words sm:max-w-md [&_button]:min-h-10">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <Trash2 className="h-5 w-5" aria-hidden="true" /> Remove AI Model
            </DialogTitle>
            <DialogDescription>
              Remove <strong>{modelToDelete?.description}</strong> (
              {modelToDelete ? displayName(modelToDelete.client) : ""}) from the configuration.
            </DialogDescription>
          </DialogHeader>
          <div className="py-2">
            <div className="rounded-md border border-border bg-card p-3 space-y-1 text-sm">
              <div>
                <span className="text-muted-foreground">Model:</span> {modelToDelete?.description}
              </div>
              <div>
                <span className="text-muted-foreground">ID:</span>{" "}
                <span className="break-all font-mono text-xs">{modelToDelete?.id}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Provider:</span>{" "}
                {modelToDelete ? displayName(modelToDelete.client) : ""}
              </div>
            </div>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleConfirmDelete}>
              Confirm Remove
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
