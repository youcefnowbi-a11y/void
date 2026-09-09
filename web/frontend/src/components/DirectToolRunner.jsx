import React, { useState, useEffect } from 'react';
import { t as _t } from '../i18n.js';
import axios from 'axios';
import { API_BASE } from '../api.js';

/* FRAPPE DIRECTE — l'arsenal à la main. Verre dépoli, inputs 10px,
   la white pill comme seule arme pleine. */

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
        initialArgs[key] = Array.isArray(props[key].default) ? props[key].default.join(', ') : '';
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
    if (type === 'boolean') {
      parsedValue = Boolean(value);
    }
    // Pour integer, number et array, on conserve la valeur saisie comme chaîne
    // durant la frappe afin de ne pas casser le curseur ni supprimer virgules/espaces.
    const updated = { ...formArgs, [key]: parsedValue };
    setFormArgs(updated);
    try {
      setRawJsonText(JSON.stringify(updated, null, 2));
    } catch { /* ignore */ }
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

    const selectedTool = tools.find(t => t.name === selectedToolName);
    const props = selectedTool?.parameters?.properties || {};

    let finalArgs = formArgs;
    if (rawJsonMode) {
      try {
        finalArgs = JSON.parse(rawJsonText);
      } catch (err) {
        setJsonError(_t('strike_json_error'));
        return;
      }
    }

    // Normalisation stricte pour éviter les 422 Pydantic et gérer tableaux / nombres
    const cleanedArgs = {};
    for (const [k, v] of Object.entries(finalArgs)) {
      if (v === '' || v === null || v === undefined) {
        continue;
      }
      const schemaType = props[k]?.type;
      if (schemaType === 'integer') {
        const num = parseInt(v, 10);
        if (!Number.isNaN(num)) cleanedArgs[k] = num;
      } else if (schemaType === 'number') {
        const num = parseFloat(v);
        if (!Number.isNaN(num)) cleanedArgs[k] = num;
      } else if (schemaType === 'boolean') {
        cleanedArgs[k] = Boolean(v);
      } else if (schemaType === 'array') {
        if (Array.isArray(v)) {
          cleanedArgs[k] = v;
        } else if (typeof v === 'string') {
          const trimmed = v.trim();
          if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
            try {
              cleanedArgs[k] = JSON.parse(trimmed);
            } catch {
              cleanedArgs[k] = trimmed.slice(1, -1).split(',').map(s => s.trim().replace(/^["']|["']$/g, '')).filter(Boolean);
            }
          } else {
            cleanedArgs[k] = trimmed ? trimmed.split(/[,\n]/).map(s => s.trim()).filter(Boolean) : [];
          }
        } else {
          cleanedArgs[k] = [v];
        }
      } else {
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
        data: err.response?.data?.detail || err.message || _t('strike_exec_error'),
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

  const inputCls = "w-full rounded-ui border border-line bg-inset px-3 py-2 text-[12px] font-mono text-ink focus:outline-none focus:border-volt/60 transition-colors placeholder:text-faint";

  return (
    <div className="space-y-4">
      {/* Sélecteur d'outil & Recherche */}
      <div className="space-y-2">
        <div className="grid grid-cols-[1fr_auto] gap-2 items-center">
          <select
            value={selectedToolName}
            onChange={(e) => handleToolChange(e.target.value)}
            disabled={executing || loadingTools}
            className={`${inputCls} cursor-pointer`}
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
            className="w-24 rounded-ui border border-line bg-inset px-2.5 py-2 text-[12px] font-mono text-ink focus:outline-none focus:border-volt/60 transition-colors placeholder:text-faint"
          />
        </div>

        {/* Description de l'outil sélectionné */}
        {currentTool.description && (
          <div className="rounded-ui border border-line bg-wash/60 px-3 py-2.5 text-[12px] text-ash leading-relaxed">
            <div className="flex items-center gap-2 mb-1">
              <span className="font-mono font-medium text-cyan">{currentTool.name}</span>
              <span className={`text-[10px] uppercase font-mono px-2 py-0.5 rounded-full border font-medium ${
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
          <span className="eyebrow">{_t('strike_params')}</span>
          <button
            type="button"
            onClick={() => setRawJsonMode(!rawJsonMode)}
            className="text-[10px] text-mut hover:text-ink uppercase tracking-[.1em] font-medium transition-colors"
          >
            {rawJsonMode ? 'mode formulaire' : 'mode JSON brut'}
          </button>
        </div>

        {rawJsonMode ? (
          <div>
            <textarea
              value={rawJsonText}
              onChange={(e) => handleRawJsonChange(e.target.value)}
              rows={5}
              placeholder={'{\n  "param": "value"\n}'}
              className="w-full rounded-ui border border-line bg-inset text-ink font-mono text-[11px] p-2.5 resize-y focus:outline-none focus:border-volt/60 transition-colors placeholder:text-faint"
            />
            {jsonError && <p className="text-danger text-[10.5px] mt-1">{jsonError}</p>}
          </div>
        ) : (
          <div className="space-y-2.5 max-h-56 overflow-y-auto pr-1">
            {Object.keys(properties).length === 0 ? (
              <p className="text-[12px] text-mut italic py-1">This tool requires no parameters.</p>
            ) : (
              Object.entries(properties).map(([propName, schema]) => {
                const isRequired = requiredFields.includes(propName);
                const val = formArgs[propName] !== undefined ? formArgs[propName] : '';

                if (schema.type === 'boolean') {
                  return (
                    <label key={propName} className="flex items-center gap-2 text-[12px] font-mono cursor-pointer">
                      <input
                        type="checkbox"
                        checked={Boolean(val)}
                        onChange={(e) => handleFieldChange(propName, e.target.checked, 'boolean')}
                        className="accent-volt"
                      />
                      <span className="text-ash">{propName} {isRequired && <span className="text-danger">*</span>}</span>
                      {schema.description && <span className="text-[10px] text-faint">({schema.description})</span>}
                    </label>
                  );
                }

                if (schema.type === 'array') {
                  return (
                    <div key={propName} className="space-y-1">
                      <label className="flex items-center justify-between text-[10.5px] font-mono uppercase tracking-[.08em]">
                        <span className="text-ash">{propName} {isRequired && <span className="text-danger">*</span>}</span>
                        <span className="text-[9px] text-faint lowercase normal-case">{schema.description || 'comma-separated or [json] format'}</span>
                      </label>
                      <input
                        type="text"
                        value={Array.isArray(val) ? val.join(', ') : (val ?? '')}
                        onChange={(e) => handleFieldChange(propName, e.target.value, 'text')}
                        placeholder='ex : val1, val2 ou ["val1", "val2"]'
                        className={inputCls}
                      />
                    </div>
                  );
                }

                return (
                  <div key={propName} className="space-y-1">
                    <label className="flex items-center justify-between text-[10.5px] font-mono uppercase tracking-[.08em]">
                      <span className="text-ash">{propName} {isRequired && <span className="text-danger">*</span>}</span>
                      {schema.description && <span className="text-[9px] text-faint lowercase normal-case truncate max-w-[200px]" title={schema.description}>{schema.description}</span>}
                    </label>
                    <input
                      type={schema.type === 'integer' || schema.type === 'number' ? 'number' : 'text'}
                      value={val}
                      onChange={(e) => handleFieldChange(propName, e.target.value, schema.type)}
                      placeholder={schema.description || `Entrez ${propName}...`}
                      className={inputCls}
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
        <span className="text-[11px] text-mut">
          {executing ? _t('strike_processing') : _t('strike_ready')}
        </span>
        <button
          type="button"
          onClick={runSelectedTool}
          disabled={executing || !selectedToolName}
          className="pill-cta btn-strike px-5 py-2 text-[12px] uppercase tracking-[.1em]"
        >
          {executing ? (
            <>
              <svg className="animate-spin h-3.5 w-3.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
              </svg>
              <span>{_t('strike_running')}</span>
            </>
          ) : (
            <span>launch tool</span>
          )}
        </button>
      </div>

      {/* RÉSULTAT DU LANCEMENT DIRECT */}
      {result && (
        <div className="rounded-card border border-line bg-wash/50 p-3.5 space-y-2.5 animate-fadeIn">
          <div className="flex items-center justify-between border-b border-line pb-2.5">
            <div className="flex items-center gap-2">
              <span className={`inline-block w-2 h-2 rounded-full ${result.success ? 'bg-ok' : 'bg-danger animate-pulse'}`} />
              <span className="text-[10px] uppercase font-mono font-medium tracking-[.14em] text-ink">
                {result.success ? _t('strike_result_ok') : _t('strike_result_fail')}
              </span>
              <span className="font-mono text-[10px] text-faint">({result.duration}s · {result.timestamp})</span>
            </div>
            <div className="flex gap-2.5">
              <button
                type="button"
                onClick={copyResult}
                className="text-[10px] text-mut hover:text-ink uppercase tracking-[.1em] font-medium transition-colors"
              >
                {copied ? _t('copied') : _t('copy')}
              </button>
              <button
                type="button"
                onClick={() => setResult(null)}
                className="text-[10px] text-mut hover:text-ink uppercase tracking-[.1em] font-medium transition-colors"
              >
                fermer
              </button>
            </div>
          </div>

          <pre className="max-h-60 overflow-y-auto rounded-ui terminal-bg border border-line p-2.5 whitespace-pre-wrap break-words">
            {typeof result.data === 'object' ? JSON.stringify(result.data, null, 2) : String(result.data)}
          </pre>
        </div>
      )}
    </div>
  );
}
