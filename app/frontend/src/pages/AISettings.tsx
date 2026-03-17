import { useState, useEffect, useCallback, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AI_PROVIDERS,
} from "@/lib/aiClient";
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
  Cpu, CheckCircle2, XCircle, Eye, EyeOff,
  Trash2, ExternalLink, Shield, Save, Search, Plus, KeyRound, Brain,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2 } from "lucide-react";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { IS_GH_PAGES_MODE, API_BASE } from "@/lib/config";

export default function AISettingsPage() {
  const [activeTab, setActiveTab] = useState<"keys" | "models">("keys");

  return (
    <div className="space-y-5 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
          <Cpu className="h-6 w-6" /> AI Settings
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Manage API keys and AI models configuration.
        </p>
      </div>

      {/* Tab navigation */}
      <div className="flex gap-1 border-b border-border">
        <button
          onClick={() => setActiveTab("keys")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === "keys"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <KeyRound className="h-3.5 w-3.5" /> API Keys
        </button>
        <button
          onClick={() => setActiveTab("models")}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === "models"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          <Brain className="h-3.5 w-3.5" /> AI Models
        </button>
      </div>

      {activeTab === "keys" ? <APIKeysTab /> : <ModelsTab />}
    </div>
  );
}

/* ═══════════════════════════════════════════
    API Keys Tab
    ═══════════════════════════════════════════ */

const CLIENT_TO_PROVIDER_ID: Record<string, string> = {
  "GitHub": "github", "Google": "google", "Groq": "groq",
  "HuggingFace": "huggingface", "OpenRouter": "openrouter",
  "Custom": "custom",
};

function APIKeysTab() {
  const [envKeys, setEnvKeys] = useState<Record<string, string>>({});
  const [visible, setVisible] = useState<Record<string, boolean>>({});
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [providerToDelete, setProviderToDelete] = useState<typeof AI_PROVIDERS[number] | null>(null);
  const { data: allModels = [] } = useQuery({ queryKey: ["models"], queryFn: getModels });

  useEffect(() => {
    fetch(`${API_BASE}/api/settings/env`)
      .then((r) => r.json())
      .then((data: Record<string, string>) => {
        setEnvKeys(data);
        const init: Record<string, string> = {};
        for (const p of AI_PROVIDERS) init[p.id] = data[p.envKey] || "";
        setDrafts(init);
      })
      .catch(() => {});
  }, []);

  const configuredProviders = AI_PROVIDERS.map((provider) => ({
    provider,
    hasKey: Boolean(envKeys[provider.envKey]),
  }));

  const toggleVisibility = (id: string) =>
    setVisible((prev) => ({ ...prev, [id]: !prev[id] }));

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
      {/* Source info */}
      <div className="flex items-start gap-2 rounded-md border border-border bg-muted/40 p-3 text-xs text-muted-foreground">
        📄 Source: <code className="font-mono bg-muted px-1 py-0.5 rounded">.env</code> — API keys are read from and written directly to the configuration file on disk.{" "}
        <span className="font-semibold text-foreground">This file is not tracked by Git.</span>
      </div>

      {/* Security notice */}
      <div className="flex items-start gap-2 rounded-md border border-border bg-muted/40 p-3 text-sm text-muted-foreground">
        <Shield className="h-4 w-4 mt-0.5 shrink-0 text-primary" />
        <span>API keys are stored locally and never sent to any server except the AI provider's API.</span>
      </div>

      {IS_GH_PAGES_MODE && (
        <div className="rounded-lg border border-primary/20 bg-primary/5 p-4 flex gap-3 items-start">
          <Brain className="h-5 w-5 text-primary shrink-0 mt-0.5" />
          <div className="text-sm">
            <p className="font-semibold text-primary">Read-Only Mode</p>
            <p className="text-muted-foreground mt-0.5">
              Configuration is disabled in this web demo. To manage API keys and models, please run the application in your local environment.
            </p>
          </div>
        </div>
      )}

      {/* Provider status overview */}
      <div className="rounded-lg border border-border bg-card p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">Configured Providers</h2>
          <Badge variant="outline" className={configuredCount > 0 ? "text-green-600 border-green-600/30" : "text-muted-foreground"}>
            {configuredCount} / {AI_PROVIDERS.length} available
          </Badge>
        </div>

        <div className="space-y-1.5">
          {configuredProviders.map(({ provider, hasKey }) => {
            const models = allModels.filter((m) => CLIENT_TO_PROVIDER_ID[m.client] === provider.id);
            return (
              <div key={provider.id} className="flex items-center gap-2 text-sm">
                {hasKey ? (
                  <CheckCircle2 className="h-3.5 w-3.5 text-green-500 shrink-0" />
                ) : (
                  <XCircle className="h-3.5 w-3.5 text-muted-foreground/40 shrink-0" />
                )}
                <span className={hasKey ? "text-foreground" : "text-muted-foreground"}>{provider.name}</span>
                {hasKey && models.length > 0 && (
                  <span className="text-[10px] text-muted-foreground ml-auto">{models.length} model{models.length > 1 ? "s" : ""}</span>
                )}
              </div>
            );
          })}
        </div>

        {configuredCount === 0 && (
          <p className="text-xs text-destructive">No API key configured. Add at least one key below to enable AI features.</p>
        )}

        <p className="text-xs text-muted-foreground">Each AI page lets you select which model to use from the available providers.</p>
      </div>

      {/* Delete API Key Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <Trash2 className="h-5 w-5" /> Remove API Key
            </DialogTitle>
            <DialogDescription>
              You are about to remove the API key for <strong>{providerToDelete?.name}</strong>.
            </DialogDescription>
          </DialogHeader>
          <div className="py-2 text-sm text-muted-foreground space-y-2">
            <p>
              This will permanently delete the key from the <code className="font-mono bg-muted px-1 py-0.5 rounded text-xs">.env</code> file on disk.
              Since <code className="font-mono bg-muted px-1 py-0.5 rounded text-xs">.env</code> is not tracked by Git,{" "}
              <strong className="text-foreground">this operation cannot be undone</strong> — the key cannot be recovered from version history.
            </p>
            <p>Make sure you have a copy of the key before proceeding.</p>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
            <Button variant="destructive" onClick={handleConfirmDelete}>Remove Key</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* API Keys management */}
       <div className="space-y-3">
         <h2 className="text-sm font-semibold">API Keys</h2>

         {AI_PROVIDERS.map((provider) => {
           const { hasKey } = configuredProviders.find((cp) => cp.provider.id === provider.id)!;
           const isVisible = visible[provider.id] || false;
           const draft = drafts[provider.id] || "";
           const isCustom = provider.id === "custom";

if (isCustom) {
              return (
                <div key={provider.id} className="rounded-lg border border-border bg-card p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      {hasKey ? <CheckCircle2 className="h-4 w-4 text-green-500" /> : <XCircle className="h-4 w-4 text-muted-foreground" />}
                      <span className="text-sm font-medium">{provider.name}</span>
                      <code className="text-[10px] font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded">{provider.envKey}</code>
                    </div>
                    <a href={provider.link} target="_blank" rel="noopener noreferrer" className="text-xs text-primary hover:underline flex items-center gap-1">
                      Docs <ExternalLink className="h-3 w-3" />
                    </a>
                  </div>

                  <div className="flex gap-2">
                    <div className="relative flex-1">
                      <Input
                        type={isVisible ? "text" : "password"}
                        value={hasKey ? (isVisible ? (envKeys[provider.envKey] || "") : "••••••••••••") : draft}
                        onChange={hasKey ? undefined : (e) => setDrafts((prev) => ({ ...prev, [provider.id]: e.target.value }))}
                        placeholder={hasKey ? "" : provider.hint}
                        className="pr-10 bg-background border-border font-mono text-xs"
                        autoComplete="off"
                        spellCheck={false}
                        readOnly={hasKey}
                      />
                      <button
                        type="button"
                        onClick={() => toggleVisibility(provider.id)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors p-1"
                      >
                        {isVisible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>

                    {hasKey ? (
                      <Button variant="outline" size="icon" onClick={() => handleDeleteRequest(provider.id)} title="Remove key" className="shrink-0 text-destructive hover:text-destructive">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    ) : (
                      <Button 
                        variant={draft.trim() ? "default" : "outline"}
                        size="icon" 
                        onClick={() => handleSave(provider.id)} 
                        title="Save key" 
                        className="shrink-0"
                        disabled={!draft.trim()}
                      >
                        <Save className="h-4 w-4" />
                      </Button>
                    )}
                  </div>

                  {hasKey && (
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      <span className="text-[10px] text-muted-foreground mr-1">Models:</span>
                      {allModels.filter((m) => CLIENT_TO_PROVIDER_ID[m.client] === provider.id).map((m) => (
                        <Badge key={m.id} variant="secondary" className="text-[10px] font-mono">{m.description}</Badge>
                      ))}
                    </div>
                  )}
                </div>
              );
           }

           return (
             <div key={provider.id} className="rounded-lg border border-border bg-card p-4 space-y-3">
               <div className="flex items-center justify-between">
                 <div className="flex items-center gap-2">
                   {hasKey ? <CheckCircle2 className="h-4 w-4 text-green-500" /> : <XCircle className="h-4 w-4 text-muted-foreground" />}
                   <span className="text-sm font-medium">{provider.name}</span>
                   <code className="text-[10px] font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded">{provider.envKey}</code>
                 </div>
                 <a href={provider.link} target="_blank" rel="noopener noreferrer" className="text-xs text-primary hover:underline flex items-center gap-1">
                   Get key <ExternalLink className="h-3 w-3" />
                 </a>
               </div>

               <div className="flex gap-2">
                 <div className="relative flex-1">
                   <Input
                     type={isVisible ? "text" : "password"}
                     value={hasKey ? (isVisible ? (envKeys[provider.envKey] || "") : "••••••••••••") : draft}
                     onChange={hasKey ? undefined : (e) => setDrafts((prev) => ({ ...prev, [provider.id]: e.target.value }))}
                     placeholder={hasKey ? "" : provider.hint}
                     className="pr-10 bg-background border-border font-mono text-xs"
                     autoComplete="off"
                     spellCheck={false}
                     readOnly={hasKey}
                   />
                   <button
                     type="button"
                     onClick={() => toggleVisibility(provider.id)}
                     className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors p-1"
                   >
                     {isVisible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                   </button>
                 </div>
                 
                 {hasKey ? (
                   <Button variant="outline" size="icon" onClick={() => handleDeleteRequest(provider.id)} title="Remove key" className="shrink-0 text-destructive hover:text-destructive">
                     <Trash2 className="h-4 w-4" />
                   </Button>
                 ) : (
                   <Button 
                     variant={draft.trim() ? "default" : "outline"}
                     size="icon" 
                     onClick={() => handleSave(provider.id)} 
                     title="Save key" 
                     className="shrink-0"
                     disabled={!draft.trim()}
                   >
                     <Save className="h-4 w-4" />
                   </Button>
                 )}
               </div>

               {hasKey && (
                 <div className="flex flex-wrap gap-1.5 pt-1">
                   <span className="text-[10px] text-muted-foreground mr-1">Models:</span>
                   {allModels.filter((m) => CLIENT_TO_PROVIDER_ID[m.client] === provider.id).map((m) => (
                     <Badge key={m.id} variant="secondary" className="text-[10px] font-mono">{m.description}</Badge>
                   ))}
                 </div>
               )}
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
  const [newModelProvider, setNewModelProvider] = useState<ModelProvider>("GitHub");

  const queryClient = useQueryClient();

  const { data: models = [], isLoading: modelsLoading } = useQuery({
    queryKey: ["aiModels"],
    queryFn: getModels,
  });

  const filteredModels = useMemo(() => {
    if (!modelSearch) return models;
    const q = modelSearch.toLowerCase();
    return models.filter(
      (m) => m.id.toLowerCase().includes(q) || m.description.toLowerCase().includes(q) || m.client.toLowerCase().includes(q)
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
    queryClient.invalidateQueries({ queryKey: ["aiModels"] });
  };

  const handleAddModel = async () => {
    if (!newModelId.trim() || !newModelDesc.trim()) return;
    const updatedModels: AIModel[] = [...models, { id: newModelId.trim(), description: newModelDesc.trim(), client: newModelProvider }];
    const csv = generateModelsCSV(updatedModels);
    try {
      await saveFileToDisk(csv, "models.csv");
      toast.success(`Model "${newModelDesc.trim()}" added`);
      invalidateModels();
    } catch (e: any) {
      toast.error(e.message);
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
    } catch (e: any) {
      toast.error(e.message);
    }
    setDeleteDialogOpen(false);
    setModelToDelete(null);
  };

  const resetAddForm = () => {
    setNewModelId("");
    setNewModelDesc("");
    setNewModelProvider("GitHub");
  };

  const providerColor: Record<string, string> = {
    GitHub: "bg-[hsl(var(--primary))]/10 text-[hsl(var(--primary))]",
    Groq: "bg-orange-500/10 text-orange-500",
    Google: "bg-blue-500/10 text-blue-500",
    HuggingFace: "bg-yellow-500/10 text-yellow-600",
    OpenRouter: "bg-purple-500/10 text-purple-500",
    Custom: "bg-emerald-500/10 text-emerald-500",
  };

  const displayName = (client: string) => PROVIDER_DISPLAY_NAMES[client] || client;

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input placeholder="Search model, provider…" value={modelSearch} onChange={(e) => setModelSearch(e.target.value)} className="pl-8 bg-card border-border" />
        </div>
        <span className="text-xs text-muted-foreground">{filteredModels.length} / {models.length} models</span>
        <Button size="sm" className="gap-1.5 ml-auto" onClick={() => { resetAddForm(); setAddDialogOpen(true); }}>
          <Plus className="h-3.5 w-3.5" /> Add Model
        </Button>
      </div>

      <div className="flex items-start gap-2 rounded-md border border-border bg-muted/40 p-3 text-xs text-muted-foreground">
        📄 Source: <code className="font-mono bg-muted px-1 py-0.5 rounded">database/models.csv</code> — Providers: {MODEL_PROVIDERS.map(p => PROVIDER_DISPLAY_NAMES[p] || p).join(", ")}
      </div>

      {modelsLoading ? (
        <div className="flex items-center gap-2 text-muted-foreground py-8 justify-center">
          <Loader2 className="h-4 w-4 animate-spin" /> Loading models…
        </div>
      ) : models.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground text-sm">No models configured. Add one to get started.</div>
      ) : (
        <div className="space-y-4">
          {[...modelsByClient.entries()].map(([client, clientModels]) => (
            <div key={client} className="rounded-lg border border-border bg-card overflow-hidden">
              <div className="px-4 py-2.5 border-b border-border bg-muted/30 flex items-center justify-between">
                <h3 className="text-sm font-semibold">{displayName(client)}</h3>
                <Badge className={`text-[10px] border-0 ${providerColor[client] || ""}`}>{clientModels.length} model{clientModels.length !== 1 ? "s" : ""}</Badge>
              </div>
              <div className="divide-y divide-border">
                {clientModels.map((m) => (
                  <div key={m.id} className="px-4 py-3 flex items-center justify-between group">
                    <div className="min-w-0">
                      <span className="text-sm font-medium">{m.description}</span>
                      <span className="text-xs text-muted-foreground font-mono ml-2">{m.id}</span>
                    </div>
                    <Button variant="ghost" size="icon" className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity text-destructive hover:text-destructive hover:bg-destructive/10 shrink-0"
                      onClick={() => { setModelToDelete(m); setDeleteDialogOpen(true); }} title="Remove model">
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
            <DialogTitle className="flex items-center gap-2"><Plus className="h-5 w-5" /> Add AI Model</DialogTitle>
            <DialogDescription>Add a new model to the configuration.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="model-provider">Provider</Label>
              <Select value={newModelProvider} onValueChange={(v) => setNewModelProvider(v as ModelProvider)}>
                <SelectTrigger className="bg-card border-border"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {MODEL_PROVIDERS.map((p) => (<SelectItem key={p} value={p}>{PROVIDER_DISPLAY_NAMES[p] || p}</SelectItem>))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="model-id">Model ID</Label>
              <Input id="model-id" placeholder="e.g. xai/grok-3-mini" value={newModelId} onChange={(e) => setNewModelId(e.target.value)} className="bg-card border-border font-mono text-sm" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="model-desc">Description</Label>
              <Input id="model-desc" placeholder="e.g. Grok-3 Mini (best)" value={newModelDesc} onChange={(e) => setNewModelDesc(e.target.value)} className="bg-card border-border" />
            </div>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setAddDialogOpen(false)}>Cancel</Button>
            <Button disabled={!newModelId.trim() || !newModelDesc.trim()} onClick={handleAddModel}>Add Model</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Model Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive"><Trash2 className="h-5 w-5" /> Remove AI Model</DialogTitle>
            <DialogDescription>Remove <strong>{modelToDelete?.description}</strong> ({modelToDelete ? displayName(modelToDelete.client) : ""}) from the configuration.</DialogDescription>
          </DialogHeader>
          <div className="py-2">
            <div className="rounded-md border border-border bg-muted/30 p-3 space-y-1 text-sm">
              <div><span className="text-muted-foreground">Model:</span> {modelToDelete?.description}</div>
              <div><span className="text-muted-foreground">ID:</span> <span className="font-mono text-xs">{modelToDelete?.id}</span></div>
              <div><span className="text-muted-foreground">Provider:</span> {modelToDelete ? displayName(modelToDelete.client) : ""}</div>
            </div>
          </div>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setDeleteDialogOpen(false)}>Cancel</Button>
            <Button variant="destructive" onClick={handleConfirmDelete}>Confirm Remove</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
