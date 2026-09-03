import { useState, useEffect, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AI_PROVIDERS } from "@/lib/aiClient";
import {
  getModels,
  generateModelsCSV,
  saveFileToDisk,
  clearCache,
  MODEL_PROVIDERS,
  PROVIDER_DISPLAY_NAMES,
  type AIModel,
  type ModelProvider,
} from "@/lib/dataService";
import {
  Cpu,
  CheckCircle2,
  XCircle,
  Eye,
  EyeOff,
  Trash2,
  ExternalLink,
  Shield,
  Save,
  Plus,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SearchInput } from "@/components/ui/SearchInput";
import { Label } from "@/components/ui/label";
import { PanelTitle } from "@/components/ui/PanelTitle";
import { usePageMeta, pageTitle } from "@/hooks/usePageMeta";
import { ROUTES } from "@/lib/routes";
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

  const [activeTab, setActiveTab] = useState<"keys" | "models">("keys");

  return (
    <div className="space-y-6 max-w-screen-2xl">
      <div>
        <h1 className="page-title">
          <Cpu className="h-5 w-5 text-muted-foreground" aria-hidden="true" /> AI Settings
        </h1>
        <p className="text-sm text-muted-foreground mt-1.5">
          Manage API keys and AI models configuration.
        </p>
      </div>

      {/* Underline tabs: active gets the primary rule and the text colour. */}
      <div role="tablist" className="flex items-stretch gap-1 border-b border-border">
        {(
          [
            ["keys", "API Keys"],
            ["models", "AI Models"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={activeTab === id}
            onClick={() => setActiveTab(id)}
            className={`h-9 px-3 -mb-px border-b-2 text-[13px] transition-colors duration-[120ms] cursor-pointer focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring ${
              activeTab === id
                ? "border-primary text-foreground font-medium"
                : "border-transparent text-muted-foreground font-normal hover:text-foreground"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {activeTab === "keys" ? <APIKeysTab /> : <ModelsTab />}
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
  HuggingFace: "huggingface",
  OpenRouter: "openrouter",
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

  const saveToEnv = async (updates: Record<string, string>) => {
    const newEnv = { ...envKeys, ...updates };
    // Remove empty values
    for (const k of Object.keys(newEnv)) {
      if (!newEnv[k]) delete newEnv[k];
    }
    await fetch(`${API_BASE}/api/settings/env`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(newEnv),
    });
    setEnvKeys(newEnv);
  };

  const handleSave = async (providerId: string) => {
    const provider = AI_PROVIDERS.find((p) => p.id === providerId)!;
    const key = drafts[providerId]?.trim() || "";
    try {
      await saveToEnv({ [provider.envKey]: key });
      toast.success(key ? `API key saved for ${provider.name}` : "API key removed");
    } catch {
      toast.error("Failed to save key");
    }
  };

  const handleDeleteRequest = (providerId: string) => {
    const provider = AI_PROVIDERS.find((p) => p.id === providerId)!;
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
      <div className="text-xs text-muted-foreground space-y-1">
        <p>
          Source: <code className="font-mono bg-muted px-1 py-0.5">.env</code>. Keys are read from
          and written directly to the configuration file on disk.{" "}
          <span className="text-foreground">This file is not tracked by Git.</span>
        </p>
        <p>
          <Shield className="inline h-3.5 w-3.5 mr-1 text-muted-foreground" aria-hidden="true" />
          Keys are stored locally and never sent to any server except the AI provider's API.
        </p>
      </div>

      {IS_GH_PAGES_MODE && (
        <div className="frame text-sm" role="note">
          <div className="frame-title">
            <PanelTitle>Read-only mode</PanelTitle>
          </div>
          <p className="p-3 text-muted-foreground">
            Configuration is disabled in this web demo. To manage API keys and models, run the
            application in your local environment.
          </p>
        </div>
      )}

      {/* Provider status overview */}
      <div className="frame">
        <div className="frame-title">
          <h2>Configured providers</h2>
        </div>
        <div className="p-3 space-y-4">
          <div className="status-line">
            <span className="k">Available:</span> {configuredCount} / {AI_PROVIDERS.length}
          </div>

          <div className="space-y-1.5">
            {configuredProviders.map(({ provider, hasKey }) => {
              const models = allModels.filter(
                (m) => CLIENT_TO_PROVIDER_ID[m.client] === provider.id,
              );
              return (
                <div key={provider.id} className="flex items-center gap-2 text-sm">
                  {hasKey ? (
                    <CheckCircle2 className="h-3.5 w-3.5 text-positive shrink-0" />
                  ) : (
                    <XCircle className="h-3.5 w-3.5 icon-faint shrink-0" />
                  )}
                  <span className={hasKey ? "text-foreground" : "text-muted-foreground"}>
                    {provider.name}
                  </span>
                  {hasKey && models.length > 0 && (
                    <span className="text-xs text-muted-foreground ml-auto">
                      {models.length} model{models.length > 1 ? "s" : ""}
                    </span>
                  )}
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
      </div>

      {/* Delete API Key Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="sm:max-w-md">
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

        {AI_PROVIDERS.map((provider) => {
          const { hasKey } = configuredProviders.find((cp) => cp.provider.id === provider.id)!;
          const isVisible = visible[provider.id] || false;
          const draft = drafts[provider.id] || "";

          return (
            <div key={provider.id} className="frame">
              <div className="frame-title">
                <PanelTitle level={3} className="flex items-center gap-2">
                  {hasKey ? (
                    <CheckCircle2 className="h-4 w-4 text-positive" aria-hidden="true" />
                  ) : (
                    <XCircle className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                  )}
                  {provider.name}
                </PanelTitle>
                <a
                  href={provider.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs font-normal text-primary-text hover:underline flex items-center gap-1"
                >
                  Get key <ExternalLink className="h-3 w-3" aria-hidden="true" />
                </a>
              </div>
              <div className="p-3 space-y-3">
                <code className="inline-block text-xs font-mono text-muted-foreground bg-muted px-1.5 py-0.5">
                  {provider.envKey}
                </code>

                <div className="flex gap-2">
                  <div className="relative flex-1">
                    <Input
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
                          : (e) => setDrafts((prev) => ({ ...prev, [provider.id]: e.target.value }))
                      }
                      placeholder={hasKey ? "" : provider.hint}
                      aria-label={`${provider.name} API key`}
                      className="pr-10 font-mono text-xs"
                      autoComplete="off"
                      spellCheck={false}
                      readOnly={hasKey}
                    />
                    <button
                      type="button"
                      onClick={() => toggleVisibility(provider.id)}
                      aria-label={isVisible ? "Hide API key" : "Show API key"}
                      className="absolute right-0.5 top-1/2 -translate-y-1/2 h-7 w-7 inline-flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {isVisible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>

                  {hasKey ? (
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={() => handleDeleteRequest(provider.id)}
                      title="Remove key"
                      aria-label={`Remove ${provider.name} key`}
                      className="shrink-0 text-negative hover:text-negative"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  ) : (
                    <Button
                      variant={draft.trim() ? "default" : "outline"}
                      size="icon"
                      onClick={() => handleSave(provider.id)}
                      title="Save key"
                      aria-label={`Save ${provider.name} key`}
                      className="shrink-0"
                      disabled={!draft.trim()}
                    >
                      <Save className="h-4 w-4" />
                    </Button>
                  )}
                </div>

                {hasKey && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    <span className="text-xs text-muted-foreground mr-1">Models:</span>
                    {allModels
                      .filter((m) => CLIENT_TO_PROVIDER_ID[m.client] === provider.id)
                      .map((m) => (
                        <Badge key={m.id} variant="secondary">
                          {m.description}
                        </Badge>
                      ))}
                  </div>
                )}
              </div>
            </div>
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
    if (!modelSearch) return models;
    const q = modelSearch.toLowerCase();
    return models.filter(
      (m) =>
        m.id.toLowerCase().includes(q) ||
        m.description.toLowerCase().includes(q) ||
        m.client.toLowerCase().includes(q),
    );
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
      <div className="flex items-center gap-3">
        <SearchInput
          label="Search model, provider"
          size="sm"
          value={modelSearch}
          onChange={(e) => setModelSearch(e.target.value)}
          wrapperClassName="flex-1 max-w-sm"
        />
        <span className="text-xs text-muted-foreground">
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
        <div className="text-center py-8 text-muted-foreground text-sm">
          No models configured. Add one to get started.
        </div>
      ) : (
        <div className="space-y-4">
          {[...modelsByClient.entries()].map(([client, clientModels]) => (
            <div key={client} className="frame">
              <div className="frame-title">
                <h2>{displayName(client)}</h2>
                <span className="text-xs font-normal text-muted-foreground">
                  {clientModels.length} model{clientModels.length !== 1 ? "s" : ""}
                </span>
              </div>
              <div className="divide-y divide-border/60">
                {clientModels.map((m) => (
                  <div key={m.id} className="px-4 py-2 flex items-center justify-between group">
                    <div className="min-w-0">
                      <span className="text-sm font-medium">{m.description}</span>
                      <span className="text-xs text-muted-foreground font-mono ml-2">{m.id}</span>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 group-focus-within:opacity-100 transition-opacity text-negative hover:text-negative hover:bg-negative/10 shrink-0"
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
            </div>
          ))}
        </div>
      )}

      {/* Add Model Dialog */}
      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Plus className="h-5 w-5" aria-hidden="true" /> Add AI Model
            </DialogTitle>
            <DialogDescription>Add a new model to the configuration.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="model-provider">Provider</Label>
              <Select
                value={newModelProvider}
                onValueChange={(v) => setNewModelProvider(v as ModelProvider)}
              >
                <SelectTrigger id="model-provider" className="bg-card">
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
            </div>
            <div className="space-y-2">
              <Label htmlFor="model-id">Model ID</Label>
              <Input
                id="model-id"
                placeholder="e.g. xai/grok-3-mini"
                value={newModelId}
                onChange={(e) => setNewModelId(e.target.value)}
                className="font-mono text-sm"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="model-desc">Description</Label>
              <Input
                id="model-desc"
                placeholder="e.g. Grok-3 Mini (best)"
                value={newModelDesc}
                onChange={(e) => setNewModelDesc(e.target.value)}
              />
            </div>
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
        <DialogContent className="sm:max-w-md">
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
                <span className="font-mono text-xs">{modelToDelete?.id}</span>
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
