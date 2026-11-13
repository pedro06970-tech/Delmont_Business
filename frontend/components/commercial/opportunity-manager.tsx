"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  apiFetch,
  Customer,
  CustomerPage,
  OpportunityStatus,
  SalesOpportunity,
  SalesOpportunityDetail,
  SalesOpportunityPage,
} from "@/lib/api";

const statusLabels: Record<OpportunityStatus, string> = {
  open: "Em aberto",
  won: "Venda concluída",
  lost: "Venda perdida",
};

export default function OpportunityManager({ storeId }: { storeId: string }) {
  const [opportunities, setOpportunities] = useState<SalesOpportunity[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [history, setHistory] = useState<Record<string, SalesOpportunityDetail | undefined>>({});
  const [status, setStatus] = useState<"all" | OpportunityStatus>("all");
  const [formOpen, setFormOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    const [opportunityResult, customerResult] = await Promise.all([
      apiFetch<SalesOpportunityPage>(`/sales-opportunities?store_id=${storeId}&page_size=100`),
      apiFetch<CustomerPage>(`/customers?store_id=${storeId}&page_size=100`),
    ]);
    setOpportunities(opportunityResult.items);
    setCustomers(customerResult.items);
  }, [storeId]);

  useEffect(() => {
    Promise.all([
      apiFetch<SalesOpportunityPage>(`/sales-opportunities?store_id=${storeId}&page_size=100`),
      apiFetch<CustomerPage>(`/customers?store_id=${storeId}&page_size=100`),
    ])
      .then(([opportunityResult, customerResult]) => {
        setOpportunities(opportunityResult.items);
        setCustomers(customerResult.items);
      })
      .catch((requestError) => setError(requestError instanceof Error ? requestError.message : "Falha ao carregar oportunidades."));
  }, [storeId]);

  const visible = useMemo(
    () => opportunities.filter((item) => status === "all" || item.status === status),
    [opportunities, status],
  );
  const activeCustomers = customers.filter((customer) => customer.is_active);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await apiFetch("/sales-opportunities", {
        method: "POST",
        body: JSON.stringify({
          store_id: storeId,
          customer_id: data.get("customer_id"),
          product_name: data.get("product_name"),
        }),
      });
      form.reset();
      setFormOpen(false);
      setNotice("Oportunidade criada.");
      await load();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Falha ao criar oportunidade.");
    } finally {
      setBusy(false);
    }
  }

  async function close(opportunity: SalesOpportunity, result: "won" | "lost") {
    const lostReason = result === "lost" ? window.prompt("Motivo da desistência (opcional):") : null;
    if (result === "lost" && lostReason === null) return;
    if (result === "won" && !window.confirm("Confirmar a venda e cancelar os lembretes vinculados pendentes?")) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await apiFetch(`/sales-opportunities/${opportunity.id}/close`, {
        method: "POST",
        body: JSON.stringify({ status: result, lost_reason: lostReason || null }),
      });
      setNotice(result === "won" ? "Venda concluída e pendências vinculadas canceladas." : "Desistência registrada e pendências vinculadas canceladas.");
      setHistory((current) => ({ ...current, [opportunity.id]: undefined }));
      await load();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Falha ao encerrar oportunidade.");
    } finally {
      setBusy(false);
    }
  }

  async function toggleHistory(opportunityId: string) {
    if (history[opportunityId]) {
      setHistory((current) => ({ ...current, [opportunityId]: undefined }));
      return;
    }
    try {
      const detail = await apiFetch<SalesOpportunityDetail>(`/sales-opportunities/${opportunityId}`);
      setHistory((current) => ({ ...current, [opportunityId]: detail }));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Falha ao carregar histórico.");
    }
  }

  return (
    <div className="space-y-5">
      {error && <p role="alert" className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700 dark:bg-rose-950/50 dark:text-rose-200">{error}</p>}
      {notice && <p role="status" className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-200">{notice}</p>}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-2 overflow-x-auto pb-1">{(["all", "open", "won", "lost"] as const).map((item) => <button key={item} onClick={() => setStatus(item)} className={`whitespace-nowrap rounded-xl px-3 py-2 text-sm ${status === item ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900" : "border border-slate-300 dark:border-slate-700"}`}>{item === "all" ? "Todas" : statusLabels[item]}</button>)}</div>
        <button onClick={() => setFormOpen((current) => !current)} disabled={!activeCustomers.length} className="primary-button">+ Nova oportunidade</button>
      </div>
      {formOpen && <form onSubmit={create} className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"><h2 className="text-xl font-bold">Nova oportunidade</h2><div className="mt-5 grid gap-4 sm:grid-cols-2"><label className="text-sm font-medium">Cliente<select name="customer_id" className="field mt-2" required defaultValue=""><option value="" disabled>Selecione</option>{activeCustomers.map((customer) => <option key={customer.id} value={customer.id}>{customer.name}</option>)}</select></label><label className="text-sm font-medium">Produto de interesse<input name="product_name" className="field mt-2" maxLength={200} required /></label></div><div className="mt-5 flex gap-3"><button className="primary-button" disabled={busy}>{busy ? "Salvando…" : "Criar oportunidade"}</button><button type="button" onClick={() => setFormOpen(false)} className="rounded-xl border border-slate-300 px-4 py-3 text-sm dark:border-slate-700">Fechar</button></div></form>}
      {!activeCustomers.length && <p className="text-sm text-amber-700 dark:text-amber-300">Cadastre um cliente ativo antes de criar uma oportunidade.</p>}
      <div className="grid gap-4 lg:grid-cols-2">
        {visible.map((item) => <article key={item.id} className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"><div className="flex items-start justify-between gap-4"><div><p className="font-semibold">{item.customer_name}</p><p className="mt-1 text-sm text-slate-500">{item.product_name}</p></div><span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${item.status === "open" ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200" : item.status === "won" ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200" : "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-200"}`}>{statusLabels[item.status]}</span></div><dl className="mt-4 grid grid-cols-2 gap-3 text-xs"><div><dt className="text-slate-500">Responsável</dt><dd className="mt-1 font-semibold">{item.created_by_name}</dd></div><div><dt className="text-slate-500">Lembretes associados</dt><dd className="mt-1 font-semibold">{item.reminder_count}</dd></div><div><dt className="text-slate-500">Criada em</dt><dd className="mt-1 font-semibold">{new Date(item.created_at).toLocaleString("pt-BR")}</dd></div><div><dt className="text-slate-500">Encerrada em</dt><dd className="mt-1 font-semibold">{item.closed_at ? new Date(item.closed_at).toLocaleString("pt-BR") : "—"}</dd></div></dl>{item.lost_reason && <p className="mt-3 rounded-lg bg-rose-50 p-3 text-xs text-rose-700 dark:bg-rose-950/40 dark:text-rose-200">Motivo: {item.lost_reason}</p>}<div className="mt-4 flex flex-wrap gap-2">{item.status === "open" && <><button disabled={busy} onClick={() => close(item, "won")} className="rounded-xl bg-emerald-600 px-3 py-2 text-sm font-semibold text-white">Marcar venda</button><button disabled={busy} onClick={() => close(item, "lost")} className="rounded-xl border border-rose-200 px-3 py-2 text-sm text-rose-700 dark:border-rose-900 dark:text-rose-300">Registrar desistência</button></>}<button onClick={() => toggleHistory(item.id)} className="rounded-xl border border-slate-300 px-3 py-2 text-sm dark:border-slate-700">{history[item.id] ? "Ocultar histórico" : "Ver histórico"}</button></div>{history[item.id] && <div className="mt-4 space-y-2 border-t border-slate-200 pt-4 dark:border-slate-800">{history[item.id]?.events.map((event) => <div key={event.id} className="rounded-lg bg-slate-50 p-3 text-xs dark:bg-slate-950"><div className="flex justify-between gap-3"><span className="font-semibold">{event.previous_status ? `${statusLabels[event.previous_status]} → ${statusLabels[event.new_status]}` : "Oportunidade criada"}</span><time className="text-slate-500">{new Date(event.occurred_at).toLocaleString("pt-BR")}</time></div><p className="mt-1 text-slate-500">Por {event.performed_by_name}</p>{event.lost_reason && <p className="mt-1 text-rose-600">{event.lost_reason}</p>}</div>)}</div>}</article>)}
      </div>
      {!visible.length && <div className="rounded-2xl border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500 dark:border-slate-700">Nenhuma oportunidade encontrada neste filtro.</div>}
    </div>
  );
}
