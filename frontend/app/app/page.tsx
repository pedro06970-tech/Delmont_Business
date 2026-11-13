"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

import { useActiveStore } from "@/components/app-shell";
import { apiFetch, CommercialDashboard } from "@/lib/api";

const fortalezaDate = (date: Date) => {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Fortaleza",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const value = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${value.year}-${value.month}-${value.day}`;
};

const INITIAL_TODAY = fortalezaDate(new Date());
const INITIAL_START = fortalezaDate(new Date(new Date().getTime() - 29 * 86_400_000));

export default function AppHomePage() {
  const { activeStore, stores } = useActiveStore();
  const [dateFrom, setDateFrom] = useState(INITIAL_START);
  const [dateTo, setDateTo] = useState(INITIAL_TODAY);
  const [collaborator, setCollaborator] = useState("");
  const [collaborators, setCollaborators] = useState<{ id: string; name: string }[]>([]);
  const [dashboard, setDashboard] = useState<CommercialDashboard | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const store = stores.find((item) => item.id === activeStore);

  const load = useCallback(async (userId: string) => {
    if (!activeStore) return;
    setLoading(true);
    setError("");
    const params = new URLSearchParams({ store_id: activeStore, date_from: dateFrom, date_to: dateTo });
    if (userId) params.set("created_by_user_id", userId);
    try {
      const result = await apiFetch<CommercialDashboard>(`/commercial/dashboard?${params}`);
      setDashboard(result);
      if (!userId) {
        setCollaborators(result.collaborator_performance.map((item) => ({ id: item.user_id, name: item.user_name })));
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Falha ao carregar o dashboard.");
    } finally {
      setLoading(false);
    }
  }, [activeStore, dateFrom, dateTo]);

  useEffect(() => {
    if (!activeStore) return;
    const params = new URLSearchParams({ store_id: activeStore, date_from: dateFrom, date_to: dateTo });
    apiFetch<CommercialDashboard>(`/commercial/dashboard?${params}`)
      .then((result) => {
        setDashboard(result);
        setCollaborators(result.collaborator_performance.map((item) => ({ id: item.user_id, name: item.user_name })));
        setError("");
      })
      .catch((requestError) => setError(requestError instanceof Error ? requestError.message : "Falha ao carregar o dashboard."))
      .finally(() => setLoading(false));
  }, [activeStore, dateFrom, dateTo]);

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void load(collaborator);
  }

  if (!activeStore) return <EmptyState text="Selecione uma loja ativa para visualizar o acompanhamento comercial." />;

  const metrics = dashboard?.metrics;
  const metricCards = metrics ? [
    ["Leads cadastrados", metrics.distinct_leads, "Clientes distintos no período"],
    ["Oportunidades abertas", metrics.open_opportunities, "Estoque na data final"],
    ["Lembretes agendados", metrics.scheduled_reminders, "Criados no período"],
    ["Mensagens aceitas", metrics.accepted_messages, "Aceitas pela WhatsMiau; não significa entrega"],
    ["Vendas concluídas", metrics.won_opportunities, "Encerradas como ganhas"],
    ["Vendas perdidas", metrics.lost_opportunities, "Encerradas como perdidas"],
    ["Taxa de conversão", `${metrics.conversion_rate.toLocaleString("pt-BR")}%`, metrics.conversion_has_basis ? "Com base nas oportunidades encerradas" : "Sem oportunidades encerradas no período"],
  ] : [];
  const maxEvolution = Math.max(...(dashboard?.reminder_evolution.map((item) => item.reminders) ?? [1]), 1);

  return (
    <div className="space-y-7">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div><p className="text-sm font-medium uppercase tracking-[0.2em] text-emerald-600">Dashboard comercial</p><h1 className="mt-2 text-3xl font-bold">Acompanhamento de oportunidades</h1><p className="mt-2 text-sm text-slate-500">{store?.name} · períodos interpretados em America/Fortaleza</p></div>
        <form onSubmit={applyFilters} className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 sm:grid-cols-4 dark:border-slate-800 dark:bg-slate-900">
          <label className="text-xs font-medium text-slate-500">De<input className="field mt-1" type="date" value={dateFrom} max={dateTo} onChange={(event) => setDateFrom(event.target.value)} required /></label>
          <label className="text-xs font-medium text-slate-500">Até<input className="field mt-1" type="date" value={dateTo} min={dateFrom} onChange={(event) => setDateTo(event.target.value)} required /></label>
          <label className="text-xs font-medium text-slate-500">Colaboradora<select className="field mt-1" value={collaborator} onChange={(event) => setCollaborator(event.target.value)}><option value="">Todas</option>{collaborators.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <button className="primary-button self-end" disabled={loading}>{loading ? "Atualizando…" : "Aplicar"}</button>
        </form>
      </div>
      {error && <p role="alert" className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700 dark:bg-rose-950/50 dark:text-rose-200">{error}</p>}
      {!dashboard && loading ? <EmptyState text="Carregando indicadores reais…" /> : null}

      {dashboard && <>
        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {metricCards.map(([label, value, hint]) => <article key={String(label)} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900"><p className="text-sm text-slate-500">{label}</p><p className="mt-3 text-3xl font-bold">{value}</p><p className="mt-2 text-xs leading-5 text-slate-500">{hint}</p></article>)}
        </section>
        <section className="grid gap-5 xl:grid-cols-[1.5fr_1fr]">
          <article className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
            <div><p className="text-sm font-semibold">Evolução dos lembretes</p><p className="mt-1 text-xs text-slate-500">Quantidade criada por dia no período</p></div>
            {dashboard.reminder_evolution.length ? <div className="mt-6 flex min-h-52 items-end gap-2 overflow-x-auto pb-2" aria-label="Gráfico de lembretes por dia">{dashboard.reminder_evolution.map((item) => <div key={item.date} className="flex min-w-12 flex-1 flex-col items-center gap-2"><span className="text-xs font-semibold">{item.reminders}</span><div className="w-full rounded-t-lg bg-emerald-500" style={{ height: `${Math.max(12, (item.reminders / maxEvolution) * 150)}px` }} /><time className="text-[10px] text-slate-500">{new Date(`${item.date}T12:00:00`).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })}</time></div>)}</div> : <p className="mt-12 text-center text-sm text-slate-500">Nenhum lembrete criado no período.</p>}
          </article>
          <article className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"><p className="text-sm font-semibold">Resumo de oportunidades</p><dl className="mt-5 space-y-4"><SummaryRow label="Em aberto na data final" value={metrics?.open_opportunities ?? 0} color="bg-amber-500" /><SummaryRow label="Ganhas no período" value={metrics?.won_opportunities ?? 0} color="bg-emerald-500" /><SummaryRow label="Perdidas no período" value={metrics?.lost_opportunities ?? 0} color="bg-rose-500" /></dl><p className="mt-6 border-t border-slate-200 pt-4 text-xs leading-5 text-slate-500 dark:border-slate-800">{metrics?.conversion_definition}</p></article>
        </section>
        <section className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
          <div><p className="text-sm font-semibold">Desempenho por colaboradora</p><p className="mt-1 text-xs text-slate-500">Criações no período e vendas encerradas como ganhas</p></div>
          <div className="mt-5 overflow-x-auto"><table className="w-full min-w-[560px] text-left text-sm"><thead className="text-xs uppercase tracking-wide text-slate-500"><tr><th className="pb-3">Colaboradora</th><th className="pb-3">Oportunidades</th><th className="pb-3">Ganhas</th><th className="pb-3">Lembretes</th></tr></thead><tbody>{dashboard.collaborator_performance.map((item) => <tr key={item.user_id} className="border-t border-slate-100 dark:border-slate-800"><td className="py-4 font-medium">{item.user_name}</td><td className="py-4">{item.opportunities_created}</td><td className="py-4 text-emerald-600">{item.opportunities_won}</td><td className="py-4">{item.reminders_created}</td></tr>)}</tbody></table>{!dashboard.collaborator_performance.length && <p className="py-8 text-center text-sm text-slate-500">Sem atividade no período.</p>}</div>
        </section>
      </>}
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="rounded-2xl border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500 dark:border-slate-700">{text}</div>;
}

function SummaryRow({ label, value, color }: { label: string; value: number; color: string }) {
  return <div className="flex items-center justify-between gap-4"><dt className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300"><span className={`h-2.5 w-2.5 rounded-full ${color}`} />{label}</dt><dd className="text-xl font-bold">{value}</dd></div>;
}
