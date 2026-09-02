import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE } from '../api.js';

export default function DirectToolRunner({ onToolExecuted }) {
  const [tools, setTools] = useState([]);
  const [loadingTools, setLoadingTools] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedToolName, setSelectedToolName] = useState('');
  const [formArgs, setFormArgs] = useState({});
  const [rawJsonMode, setRawJsonMode] = useState(false);
  const [rawJsonText, setRawJsonText] = useState('{}');
  const [jsonError, setJsonError] = useState(null);

  const [executing, setExecuting] = useState(false);
  const [result, setResult] = useState(null);
  const [copied, setCopied] = useState(false);

  // Fetch available tools from backend
  useEffect(() => {
    setLoadingTools(true);
    axios.get(`${API_BASE}/tools`)
      .then(res => {
        const list = res.data?.tools || [];
        setTools(list);
        if (list.length > 0 && !selectedToolName) {
          selectTool(list[0]);
        }
      })
      .catch(err => {
        console.error("Impossible de charger les outils:", err);
      })
      .finally(() => setLoadingTools(false));
  }, []);

  const selectTool = (tool, presetArgs = null) => {
    if (!tool) return;
    setSelectedToolName(tool.name);

    // Build initial form arguments based on properties
    const props = tool.parameters?.properties || {};
    const initialArgs = {};

    for (const key of Object.keys(props)) {
      if (presetArgs && presetArgs[key] !== undefined) {
        initialArgs[key] = presetArgs[key];
      } else if (props[key].default !== undefined) {
        initialArgs[key] = props[key].default;
      } else if (props[key].type === 'array') {
        initialArgs[key] = [];
      } else if (props[key].type === 'boolean') {
        initialArgs[key] = false;
      } else if (props[key].type === 'integer' || props[key].type === 'number') {
        initialArgs[key] = '';
      } else {
        initialArgs[key] = '';
      }
    }

    if (presetArgs) {
      Object.assign(initialArgs, presetArgs);
    }

    setFormArgs(initialArgs);
    setRawJsonText(JSON.stringify(initialArgs, null, 2));
    setJsonError(null);
    setResult(null);
  };

  const handleToolChange = (toolName) => {
    const found = tools.find(t => t.name === toolName);
    if (found) selectTool(found);
  };

  const handleFieldChange = (key, value, type) => {
    let parsedValue = value;
    if (type === 'integer') {
      parsedValue = value === '' ? '' : parseInt(value, 10);
    } else if (type === 'number') {
      parsedValue = value === '' ? '' : parseFloat(value);
    } else if (type === 'boolean') {
      parsedValue = Boolean(value);
    } else if (type === 'array') {
      if (typeof value === 'string') {
        parsedValue = value.split(/[,\n]/).map(s => s.trim()).filter(Boolean);
      }
    }

    const updated = { ...formArgs, [key]: parsedValue };
    setFormArgs(updated);
    setRawJsonText(JSON.stringify(updated, null, 2));
  };

  const handleRawJsonChange = (text) => {
    setRawJsonText(text);
    try {
      const parsed = JSON.parse(text);
      setFormArgs(parsed);
      setJsonError(null);
    } catch (e) {
      setJsonError("Format JSON invalide : " + e.message);
    }
  };

  const runSelectedTool = async (e) => {
    if (e) e.preventDefault();
    if (!selectedToolName || executing) return;

    let finalArgs = formArgs;
    if (rawJsonMode) {
      try {
        finalArgs = JSON.parse(rawJsonText);
      } catch (err) {
        setJsonError("Erreur JSON : impossible d'exécuter");
        return;
      }
    }

    // Clean empty strings for optional numbers
    const cleanedArgs = {};
    for (const [k, v] of Object.entries(finalArgs)) {
      if (v !== '' && v !== null && v !== undefined) {
        cleanedArgs[k] = v;
      }
    }

    setExecuting(true);
    setResult(null);

    try {
      const response = await axios.post(`${API_BASE}/tool`, {
        tool: selectedToolName,
        args: cleanedArgs,
      });

      setResult({
        success: response.data.success,
        duration: response.data.duration,
        data: response.data.result,
        timestamp: new Date().toLocaleTimeString(),
      });

      if (onToolExecuted) {
        onToolExecuted(response.data);
      }
    } catch (err) {
      setResult({
        success: false,
        duration: 0,
        data: err.response?.data?.detail || err.message || "Erreur d'exécution de l'outil",
        timestamp: new Date().toLocaleTimeString(),
      });
    } finally {
      setExecuting(false);
    }
  };

  const copyResult = () => {
    if (!result?.data) return;
    const textToCopy = typeof result.data === 'object'
      ? JSON.stringify(result.data, null, 2)
      : String(result.data);
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const currentTool = tools.find(t => t.name === selectedToolName) || {
    name: selectedToolName,
    description: '',
    parameters: { properties: {}, required: [] },
    danger: 'safe'
  };

  const filteredTools = tools.filter(t =>
    t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (t.description && t.description.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  const properties = currentTool.parameters?.properties || {};
  const requiredFields = currentTool.parameters?.required || [];

  return (
    <div className="space-y-4">
      {/* Sélecteur d'outil & Recherche */}
      <div className="space-y-2">
        <div className="grid grid-cols-[1fr_auto] gap-2 items-center">
          <select
            value={selectedToolName}
            onChange={(e) => handleToolChange(e.target.value)}
            disabled={executing || loadingTools}
            className="w-full rounded-[10px] border border-line bg-wash px-3 py-2 text-[12.5px] font-mono text-ink focus:outline-none focus:border-volt focus:bg-paper transition-colors cursor-pointer"
          >
            {tools.length === 0 && <option>Chargement de l'arsenal...</option>}
            {filteredTools.map(t => (
              <option key={t.name} value={t.name}>
                {t.name} [{t.danger || 'safe'}]
              </option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Filtrer..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-24 rounded-[10px] border border-line bg-wash px-2.5 py-2 text-[11.5px] font-mono text-ink focus:outline-none focus:border-volt focus:bg-paper transition-colors"
          />
        </div>

        {/* Description de l'outil sélectionné */}
        {currentTool.description && (
          <div className="rounded-lg border border-line border-l-2 border-l-volt/50 bg-wash px-3 py-2 text-[11.5px] text-slate leading-relaxed">
            <div className="flex items-center gap-2 mb-0.5">
              <span className="font-mono font-bold text-volt">{currentTool.name}</span>
              <span className={`text-[9px] uppercase px-1.5 py-0.5 rounded-full border font-semibold ${
                currentTool.danger === 'destructive' ? 'border-danger/30 text-danger bg-dangertint' :
                currentTool.danger === 'active' ? 'border-warn/30 text-warn bg-warntint' :
                'border-ok/30 text-ok bg-oktint'
              }`}>
                {currentTool.danger || 'safe'}
              </span>
            </div>
            <p className="text-mut">{currentTool.description}</p>
          </div>
        )}
      </div>

      {/* Paramètres de l'outil */}
      <div className="pt-1">
        <div className="flex items-center justify-between mb-2">
          <span className="eyebrow">Paramètres de frappe</span>
          <button
            type="button"
            onClick={() => setRawJsonMode(!rawJsonMode)}
            className="text-[10px] text-mut hover:text-volt hover:underline uppercase tracking-wider font-semibold"
          >
            {rawJsonMode ? 'Mode Formulaire' : 'Mode JSON Brut'}
          </button>
        </div>

        {rawJsonMode ? (
          <div>
            <textarea
              value={rawJsonText}
              onChange={(e) => handleRawJsonChange(e.target.value)}
              rows={5}
              placeholder={'{\n  "param": "valeur"\n}'}
              className="w-full rounded-[10px] border border-line bg-wash text-ink font-mono text-[11px] p-2.5 resize-y focus:outline-none focus:border-volt focus:bg-paper transition-colors"
            />
            {jsonError && <p className="text-danger text-[10px] mt-1">{jsonError}</p>}
          </div>
        ) : (
          <div className="space-y-2.5 max-h-56 overflow-y-auto pr-1">
            {Object.keys(properties).length === 0 ? (
              <p className="text-[11px] text-mut italic py-1">Cet outil ne requiert aucun paramètre.</p>
            ) : (
              Object.entries(properties).map(([propName, schema]) => {
                const isRequired = requiredFields.includes(propName);
                const val = formArgs[propName] !== undefined ? formArgs[propName] : '';

                if (schema.type === 'boolean') {
                  return (
                    <label key={propName} className="flex items-center gap-2 text-[11.5px] font-mono cursor-pointer">
                      <input
                        type="checkbox"
                        checked={Boolean(val)}
                        onChange={(e) => handleFieldChange(propName, e.target.checked, 'boolean')}
                        className="accent-volt"
                      />
                      <span className="text-slate">{propName} {isRequired && <span className="text-danger">*</span>}</span>
                      {schema.description && <span className="text-[10px] text-faint">({schema.description})</span>}
                    </label>
                  );
                }

                if (schema.type === 'array') {
                  return (
                    <div key={propName} className="space-y-1">
                      <label className="flex items-center justify-between text-[11px] font-mono uppercase tracking-wider">
                        <span className="text-slate">{propName} {isRequired && <span className="text-danger">*</span>}</span>
                        <span className="text-[9px] text-faint lowercase">{schema.description || 'séparer par des virgules'}</span>
                      </label>
                      <input
                        type="text"
                        value={Array.isArray(val) ? val.join(', ') : val}
                        onChange={(e) => handleFieldChange(propName, e.target.value, 'array')}
                        placeholder="ex: val1, val2, val3"
                        className="w-full rounded-[10px] border border-line bg-wash px-2.5 py-1.5 text-[12px] font-mono text-ink focus:outline-none focus:border-volt focus:bg-paper transition-colors"
                      />
                    </div>
                  );
                }

                return (
                  <div key={propName} className="space-y-1">
                    <label className="flex items-center justify-between text-[11px] font-mono uppercase tracking-wider">
                      <span className="text-slate">{propName} {isRequired && <span className="text-danger">*</span>}</span>
                      {schema.description && <span className="text-[9px] text-faint lowercase truncate max-w-[200px]" title={schema.description}>{schema.description}</span>}
                    </label>
                    <input
                      type={schema.type === 'integer' || schema.type === 'number' ? 'number' : 'text'}
                      value={val}
                      onChange={(e) => handleFieldChange(propName, e.target.value, schema.type)}
                      placeholder={schema.description || `Entrez ${propName}...`}
                      className="w-full rounded-[10px] border border-line bg-wash px-2.5 py-1.5 text-[12px] font-mono text-ink focus:outline-none focus:border-volt focus:bg-paper transition-colors"
                    />
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>

      {/* BOUTON D'EXÉCUTION DIRECTE */}
      <div className="pt-3 border-t border-line flex items-center justify-between gap-3">
        <span className="text-[10px] text-mut">
          {executing ? 'Traitement en cours...' : 'Prêt pour frappe ciblée'}
        </span>
        <button
          type="button"
          onClick={runSelectedTool}
          disabled={executing || !selectedToolName}
          className="btn-strike rounded-full bg-snow text-[#0A0A0A] font-disp font-semibold uppercase tracking-[.14em] text-[12.5px] px-5 py-2 flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none cursor-pointer"
        >
          {executing ? (
            <>
              <svg className="animate-spin h-4 w-4 text-[#0A0A0A]" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
              </svg>
              <span>Exécution en cours...</span>
            </>
          ) : (
            <>
              <span>LANCER L'OUTIL DIRECTEMENT</span>
            </>
          )}
        </button>
      </div>

      {/* RÉSULTAT DU LANCEMENT DIRECT */}
      {result && (
        <div className="mt-3 rounded-xl border border-line bg-wash p-3 space-y-2 animate-fadeIn">
          <div className="flex items-center justify-between border-b border-line pb-2">
            <div className="flex items-center gap-2">
              <span className={`inline-block w-2.5 h-2.5 rounded-full ${result.success ? 'bg-ok' : 'bg-danger animate-pulse'}`} />
              <span className="text-[11px] uppercase font-bold tracking-wider text-ink">
                {result.success ? 'RÉSULTAT OBTENU' : 'ÉCHEC / ALERTE'}
              </span>
              <span className="font-mono text-[10px] text-faint">({result.duration}s · {result.timestamp})</span>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={copyResult}
                className="text-[10px] text-mut hover:text-volt hover:underline uppercase font-semibold"
              >
                {copied ? '✓ Copié !' : 'Copier'}
              </button>
              <button
                type="button"
                onClick={() => setResult(null)}
                className="text-[10px] text-mut hover:text-ink uppercase"
              >
                Fermer
              </button>
            </div>
          </div>

          <pre className="max-h-60 overflow-y-auto rounded-lg bg-paper border border-line text-ink p-2.5 font-mono text-[11px] leading-relaxed whitespace-pre-wrap break-words">
            {typeof result.data === 'object' ? JSON.stringify(result.data, null, 2) : String(result.data)}
          </pre>
        </div>
      )}
    </div>
  );
}
