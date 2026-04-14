import { useState, useEffect } from 'react';
import { getConfig, saveConfig, testConfig } from '../api/config';
import type { ConfigData } from '../api/config';
import { Loader2, CheckCircle2, AlertCircle } from 'lucide-react';

export default function SettingsPage() {
  const [config, setConfig] = useState<ConfigData>({
    llm_provider: 'openai',
    api_key_configured: false,
    api_key: '',
    model_name: 'gpt-4o',
    embedding_model: 'BAAI/bge-m3'
  });
  
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [notification, setNotification] = useState<{type: 'success' | 'error', message: string} | null>(null);

  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    try {
      const data = await getConfig();
      setConfig(data);
    } catch (err) {
      console.error(err);
      showNotification('error', 'Failed to load configuration');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const updated = await saveConfig({
        llm_provider: config.llm_provider,
        api_key: config.api_key,
        model_name: config.model_name,
        embedding_model: config.embedding_model
      });
      // Do not overwrite api key input with empty string if not changed
      setConfig(prev => ({
        ...updated,
        api_key: prev.api_key && !updated.api_key ? prev.api_key : updated.api_key
      }));
      showNotification('success', 'Configuration saved successfully!');
    } catch (err) {
      console.error(err);
      showNotification('error', 'Failed to save configuration');
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      const result = await testConfig({
        llm_provider: config.llm_provider,
        api_key: config.api_key,
        model_name: config.model_name,
        embedding_model: config.embedding_model
      });
      if (result.success) {
        showNotification('success', `Connection successful. AI says: "${result.response}"`);
      }
    } catch (err: any) {
      console.error(err);
      showNotification('error', err.response?.data?.detail || 'Test failed. Please check your API key and provider.');
    } finally {
      setTesting(false);
    }
  };

  const showNotification = (type: 'success' | 'error', message: string) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background p-6 md:p-12 text-foreground transition-colors duration-300">
      <div className="mx-auto max-w-3xl space-y-8 animate-in fade-in slide-in-from-bottom-6 duration-700">
        <div className="space-y-2">
          <h1 className="text-4xl font-extrabold tracking-tight bg-gradient-to-r from-primary to-primary/60 bg-clip-text text-transparent">Settings</h1>
          <p className="text-lg text-muted-foreground">
            Configure your AI providers, models, and system preferences.
          </p>
        </div>

        {notification && (
          <div className={`p-4 rounded-xl flex items-center gap-3 transition-all animate-in fade-in slide-in-from-top-2 ${notification.type === 'success' ? 'bg-emerald-500/10 text-emerald-600 border border-emerald-500/20' : 'bg-red-500/10 text-red-600 border border-red-500/20'}`}>
            {notification.type === 'success' ? <CheckCircle2 className="h-5 w-5" /> : <AlertCircle className="h-5 w-5" />}
            <p className="text-sm font-medium">{notification.message}</p>
          </div>
        )}

        <div className="rounded-2xl border bg-card/50 backdrop-blur-sm text-card-foreground shadow-sm overflow-hidden border-primary/10">
          <div className="p-6 md:p-8 space-y-8">
            
            <div className="space-y-6">
              <div className="space-y-3">
                <label className="text-sm font-semibold leading-none flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary inline-block"></span>
                  LLM Provider
                </label>
                <p className="text-sm text-muted-foreground">Select the artificial intelligence platform to power your agents.</p>
                <select 
                  className="flex h-11 w-full rounded-md border border-input bg-background/50 backdrop-blur-md px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 transition-all hover:bg-background"
                  value={config.llm_provider || 'openai'}
                  onChange={(e) => setConfig({...config, llm_provider: e.target.value})}
                >
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="ollama">Ollama (Local)</option>
                  <option value="deepseek">DeepSeek (深度求索)</option>
                  <option value="kimi">Kimi (月之暗面)</option>
                  <option value="qwen">Qwen (通义千问)</option>
                  <option value="glm">GLM (智谱清言)</option>
                  <option value="minimax">MiniMax</option>
                </select>
              </div>

              <div className="space-y-3">
                <label className="text-sm font-semibold leading-none flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary inline-block"></span>
                  API Key
                </label>
                <p className="text-sm text-muted-foreground">Your secure access token. Stored locally.</p>
                <input 
                  type="password" 
                  placeholder={config.api_key_configured ? "•••••••••••••••• (Configured)" : "sk-..."}
                  value={config.api_key || ''}
                  onChange={(e) => setConfig({...config, api_key: e.target.value})}
                  className="flex h-11 w-full rounded-md border border-input bg-background/50 backdrop-blur-md px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 transition-all hover:bg-background"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
                <div className="space-y-3">
                  <label className="text-sm font-semibold leading-none flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-primary/60 inline-block"></span>
                    Model Name
                  </label>
                  <input 
                    type="text" 
                    value={config.model_name || ''}
                    onChange={(e) => setConfig({...config, model_name: e.target.value})}
                    placeholder="e.g. gpt-4o"
                    className="flex h-11 w-full rounded-md border border-input bg-background/50 backdrop-blur-md px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 transition-all hover:bg-background"
                  />
                </div>
                <div className="space-y-3">
                  <label className="text-sm font-semibold leading-none flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-primary/60 inline-block"></span>
                    Embedding Model
                  </label>
                  <input 
                    type="text" 
                    value={config.embedding_model || ''}
                    onChange={(e) => setConfig({...config, embedding_model: e.target.value})}
                    placeholder="e.g. BAAI/bge-m3"
                    className="flex h-11 w-full rounded-md border border-input bg-background/50 backdrop-blur-md px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 transition-all hover:bg-background"
                  />
                </div>
              </div>
            </div>

            <div className="flex items-center gap-4 pt-6 mt-6 border-t border-border/50">
              <button 
                onClick={handleSave}
                disabled={saving || testing}
                className="inline-flex h-11 items-center justify-center rounded-md bg-primary px-8 text-sm font-semibold text-primary-foreground ring-offset-background transition-all hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 shadow-[0_4px_14px_0_rgba(0,0,0,0.1)] hover:shadow-[0_6px_20px_rgba(0,0,0,0.15)]"
              >
                {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Save Configuration
              </button>
              <button 
                onClick={handleTest}
                disabled={saving || testing}
                className="inline-flex h-11 items-center justify-center rounded-md border border-input bg-background/50 backdrop-blur-md px-8 text-sm font-semibold ring-offset-background transition-all hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50"
              >
                {testing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Test Connection
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
