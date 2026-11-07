"use client";

import { FormEvent, useEffect, useState } from "react";

import {
  ApiError,
  apiFetch,
  ReminderDeliveryAttempt,
  Store,
  WhatsMiauConfiguration,
} from "@/lib/api";

export default function WhatsMiauManager({ stores }: { stores: Store[] }) {
  const [storeId, setStoreId] = useState(stores[0]?.id ?? "");
  const [configuration, setConfiguration] = useState<WhatsMiauConfiguration | null>(null);
  const [attempts, setAttempts] = useState<ReminderDeliveryAttempt[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  async function load(selectedStore = storeId) {
    if (!selectedStore) return;
    setError("");
    const attemptRequest = apiFetch<ReminderDeliveryAttempt[]>(
      `/whatsmiau/attempts?store_id=${selectedStore}&limit=20`,
    );
    try {
      const [config, history] = await Promise.all([
        apiFetch<WhatsMiauConfiguration>(`/whatsmiau/configurations/${selectedStore}`),
        attemptRequest,
      ]);
      setConfiguration(config);
      setAttempts(history);
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.code === "whatsmiau_not_configured") {
        setConfiguration(null);
        setAttempts(await attemptRequest);
      } else {
        setError(requestError instanceof Error ? requestError.message : "Falha ao carregar integração.");
      }
    }
  }

  useEffect(() => {
    if (!storeId) return;
    Promise.all([
      apiFetch<WhatsMiauConfiguration>(`/whatsmiau/configurations/${storeId}`).catch(
        (requestError) => {
          if (requestError instanceof ApiError && requestError.code === "whatsmiau_not_configured") return null;
          throw requestError;
        },
      ),
      apiFetch<ReminderDeliveryAttempt[]>(`/whatsmiau/attempts?store_id=${storeId}&limit=20`),
    ])
      .then(([config, history]) => {
        setConfiguration(config);
        setAttempts(history);
      })
      .catch((requestError) => setError(requestError.message));
  }, [storeId]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    await run(
      () => apiFetch(`/whatsmiau/configurations/${storeId}`, {
        method: "PUT",
        body: JSON.stringify({
          instance_name: data.get("instance_name"),
          credential_env_var: data.get("credential_env_var"),
          webhook_secret_env_var: data.get("webhook_secret_env_var") || null,
          is_enabled: data.get("is_enabled") === "on",
        }),
      }),
      "Configuração salva. A chave continua somente no ambiente do backend.",
    );
  }

  async function authorizeHomologation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    if (!window.confirm("Confirma que este número pertence a um teste autorizado?")) return;
    await run(
      () => apiFetch(`/whatsmiau/configurations/${storeId}/homologation-number`, {
        method: "PUT",
        body: JSON.stringify({ phone: data.get("phone"), confirm_authorized: true }),
      }),
      "Número de homologação autorizado. Nenhuma mensagem foi enviada.",
    );
  }

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      setNotice(success);
      await load();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Falha na integração.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-5 rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
      <div>
        <p className="text-sm font-medium uppercase tracking-[0.18em] text-emerald-600">Integração</p>
        <h2 className="mt-2 text-xl font-bold">WhatsMiau por loja</h2>
        <p className="mt-1 text-sm text-slate-500">A credencial nunca é armazenada ou retornada pelo painel.</p>
      </div>
      {(error || notice) && <p role={error ? "alert" : "status"} className={`rounded-xl p-3 text-sm ${error ? "bg-rose-50 text-rose-700 dark:bg-rose-950/50 dark:text-rose-200" : "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-200"}`}>{error || notice}</p>}
      {attempts.some((attempt) => attempt.status === "uncertain") && <div role="alert" className="rounded-xl border border-violet-300 bg-violet-50 p-4 text-sm text-violet-900 dark:border-violet-800 dark:bg-violet-950/50 dark:text-violet-100"><p className="font-semibold">Há mensagens com resultado incerto</p><p className="mt-1">Não faça reenvio manual sem confirmar o resultado no provedor.</p></div>}
      <label className="block text-sm font-medium">Loja<select value={storeId} onChange={(event) => setStoreId(event.target.value)} className="field mt-2">{stores.map((store) => <option key={store.id} value={store.id}>{store.name}</option>)}</select></label>
      <form key={configuration?.id ?? storeId} onSubmit={save} className="grid gap-4 sm:grid-cols-2">
        <label className="text-sm font-medium">Instância<input name="instance_name" required maxLength={40} defaultValue={configuration?.instance_name ?? ""} key={configuration?.id ?? storeId} placeholder="LojaCentro" className="field mt-2" /></label>
        <label className="text-sm font-medium">Variável da credencial<input name="credential_env_var" required maxLength={128} placeholder="WHATS_MIAU_LOJA_CENTRO_KEY" autoComplete="off" className="field mt-2" /><span className="mt-1 block text-xs text-slate-500">Informe o nome da variável, nunca a chave.</span></label>
        <label className="text-sm font-medium sm:col-span-2">Variável do segredo do webhook<input name="webhook_secret_env_var" maxLength={128} placeholder="WHATS_MIAU_LOJA_CENTRO_WEBHOOK_SECRET" autoComplete="off" className="field mt-2" /><span className="mt-1 block text-xs text-slate-500">Configure o mesmo valor no header X-Delmont-Webhook-Secret da WhatsMiau.</span></label>
        <label className="flex items-center gap-3 text-sm"><input name="is_enabled" type="checkbox" defaultChecked={configuration?.is_enabled ?? true} className="h-5 w-5 accent-emerald-600" /> Integração ativa</label>
        <div className="flex flex-wrap gap-2 sm:justify-end"><button disabled={busy} className="primary-button" type="submit">Salvar</button>{configuration && <button disabled={busy} type="button" onClick={() => run(() => apiFetch(`/whatsmiau/configurations/${storeId}/check`, { method: "POST" }), "Conexão verificada.")} className="rounded-xl border border-slate-300 px-4 py-3 text-sm dark:border-slate-700">Verificar conexão</button>}</div>
      </form>
      {configuration && <div className="grid gap-3 rounded-xl bg-slate-50 p-4 text-sm dark:bg-slate-950 sm:grid-cols-3"><div><span className="text-slate-500">Conexão</span><p className="mt-1 font-semibold">{configuration.connection_state}</p></div><div><span className="text-slate-500">Credencial no ambiente</span><p className="mt-1 font-semibold">{configuration.credential_configured ? "Configurada" : "Ausente"}</p></div><div><span className="text-slate-500">Webhook seguro</span><p className="mt-1 font-semibold">{configuration.webhook_secret_configured ? "Configurado" : "Ausente"}</p></div><div><span className="text-slate-500">Disparos</span><p className="mt-1 font-semibold">{configuration.dispatch_paused ? "Pausados" : "Ativos"}</p></div><div><span className="text-slate-500">Número de homologação</span><p className="mt-1 font-semibold">{configuration.homologation_phone_masked ?? "Não autorizado"}</p></div><div className="sm:col-span-3"><button disabled={busy} onClick={() => run(() => apiFetch(`/whatsmiau/configurations/${storeId}/${configuration.dispatch_paused ? "resume" : "pause"}`, { method: "POST" }), configuration.dispatch_paused ? "Disparos reativados." : "Disparos pausados.")} className="rounded-xl border border-amber-300 px-4 py-2 text-sm text-amber-800 dark:border-amber-800 dark:text-amber-200">{configuration.dispatch_paused ? "Reativar disparos" : "Pausar disparos"}</button></div></div>}
      {configuration && <form onSubmit={authorizeHomologation} className="rounded-xl border border-slate-200 p-4 dark:border-slate-800"><h3 className="font-semibold">Número de teste autorizado</h3><p className="mt-1 text-xs text-slate-500">Esta ação apenas registra a autorização; não dispara mensagem.</p><div className="mt-3 flex flex-col gap-2 sm:flex-row"><input name="phone" required placeholder="+55 11 99999-9999" className="field" /><button disabled={busy} className="primary-button whitespace-nowrap" type="submit">Autorizar número</button></div></form>}
      <div><h3 className="font-semibold">Tentativas recentes</h3><div className="mt-3 space-y-2">{attempts.map((attempt) => <div key={attempt.id} className="rounded-xl border border-slate-200 p-3 text-sm dark:border-slate-800"><div className="flex justify-between gap-3"><span className="font-medium">{attempt.status}</span><time className="text-slate-500">{new Date(attempt.started_at).toLocaleString("pt-BR")}</time></div><p className="mt-1 text-xs text-slate-500">Tentativa {attempt.attempt_number}{attempt.provider_message_id ? ` · ID ${attempt.provider_message_id}` : ""}</p>{attempt.sanitized_error && <p className="mt-2 text-xs text-rose-600">{attempt.sanitized_error}</p>}</div>)}{!attempts.length && <p className="text-sm text-slate-500">Nenhuma tentativa registrada para esta loja.</p>}</div></div>
    </section>
  );
}
