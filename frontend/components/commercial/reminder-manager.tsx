"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  apiFetch,
  Customer,
  CustomerPage,
  MessageTemplate,
  Reminder,
  ReminderDeliveryAttempt,
  ReminderPage,
  WhatsMiauReadiness,
} from "@/lib/api";

type ReminderViewStatus = "pending" | "accepted" | "delivered" | "read" | "failed" | "uncertain" | "cancelled";

const viewStatusLabels: Record<ReminderViewStatus, string> = {
  pending: "Pendente",
  accepted: "Aceito pela WhatsMiau",
  delivered: "Entregue",
  read: "Lido",
  failed: "Falhou",
  uncertain: "Resultado incerto",
  cancelled: "Cancelado",
};

function viewStatus(reminder: Reminder): ReminderViewStatus {
  if (reminder.status === "cancelled") return "cancelled";
  if (reminder.provider_status === "read") return "read";
  if (reminder.provider_status === "delivered") return "delivered";
  if (reminder.execution_status === "sent") return "accepted";
  if (reminder.execution_status === "uncertain") return "uncertain";
  if (reminder.execution_status === "failed" || reminder.status === "failed") return "failed";
  return "pending";
}

function toLocalInput(value: string): string {
  const date = new Date(value);
  const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return shifted.toISOString().slice(0, 16);
}

function defaultSchedule(): string {
  return toLocalInput(new Date(Date.now() + 86_400_000).toISOString());
}

export default function ReminderManager({ storeId }: { storeId: string }) {
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [templates, setTemplates] = useState<MessageTemplate[]>([]);
  const [readiness, setReadiness] = useState<WhatsMiauReadiness | null>(null);
  const [attemptHistory, setAttemptHistory] = useState<Record<string, ReminderDeliveryAttempt[]>>({});
  const [selected, setSelected] = useState<Reminder | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [status, setStatus] = useState<"all" | ReminderViewStatus>("all");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const [reminderResult, customerResult, templateResult, readinessResult] = await Promise.all([
      apiFetch<ReminderPage>(`/reminders?store_id=${storeId}&page_size=100`),
      apiFetch<CustomerPage>(`/customers?store_id=${storeId}&page_size=100`),
      apiFetch<MessageTemplate[]>(`/message-templates?store_id=${storeId}`),
      apiFetch<WhatsMiauReadiness>(`/whatsmiau/readiness/${storeId}`),
    ]);
    setReminders(reminderResult.items);
    setCustomers(customerResult.items);
    setTemplates(templateResult);
    setReadiness(readinessResult);
    setSelected((current) =>
      current ? reminderResult.items.find((item) => item.id === current.id) ?? null : null,
    );
  }, [storeId]);

  useEffect(() => {
    Promise.all([
      apiFetch<ReminderPage>(`/reminders?store_id=${storeId}&page_size=100`),
      apiFetch<CustomerPage>(`/customers?store_id=${storeId}&page_size=100`),
      apiFetch<MessageTemplate[]>(`/message-templates?store_id=${storeId}`),
      apiFetch<WhatsMiauReadiness>(`/whatsmiau/readiness/${storeId}`),
    ])
      .then(([reminderResult, customerResult, templateResult, readinessResult]) => {
        setReminders(reminderResult.items);
        setCustomers(customerResult.items);
        setTemplates(templateResult);
        setReadiness(readinessResult);
      })
      .catch((requestError) =>
        setError(requestError instanceof Error ? requestError.message : "Falha ao carregar lembretes."),
      );
  }, [storeId]);

  const eligibleCustomers = useMemo(
    () => customers.filter((customer) => customer.is_active && customer.has_consent),
    [customers],
  );
  const activeTemplates = useMemo(
    () => templates.filter((template) => template.is_active),
    [templates],
  );
  const visibleReminders = useMemo(
    () => reminders.filter((reminder) => status === "all" || viewStatus(reminder) === status),
    [reminders, status],
  );

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const editing = selected?.status === "pending" && formOpen;
    const common = {
      message_template_id: data.get("message_template_id"),
      product_interest: data.get("product_interest"),
      scheduled_for: new Date(String(data.get("scheduled_for"))).toISOString(),
    };
    const body = editing
      ? common
      : { ...common, store_id: storeId, customer_id: data.get("customer_id") };
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await apiFetch(editing ? `/reminders/${selected.id}` : "/reminders", {
        method: editing ? "PATCH" : "POST",
        body: JSON.stringify(body),
      });
      setNotice(editing ? "Lembrete atualizado." : "Lembrete programado.");
      setFormOpen(false);
      setSelected(null);
      await load();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Falha ao salvar lembrete.");
    } finally {
      setBusy(false);
    }
  }

  async function runAction(action: () => Promise<unknown>, success: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      setNotice(success);
      setSelected(null);
      await load();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Falha ao atualizar lembrete.");
    } finally {
      setBusy(false);
    }
  }

  async function checkConnection() {
    await runAction(
      () => apiFetch(`/whatsmiau/readiness/${storeId}/check`, { method: "POST" }),
      "Conexão WhatsMiau verificada.",
    );
  }

  async function toggleHistory(reminderId: string) {
    if (attemptHistory[reminderId]) {
      setAttemptHistory((current) => {
        const next = { ...current };
        delete next[reminderId];
        return next;
      });
      return;
    }
    try {
      const attempts = await apiFetch<ReminderDeliveryAttempt[]>(`/reminders/${reminderId}/attempts`);
      setAttemptHistory((current) => ({ ...current, [reminderId]: attempts }));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Falha ao carregar tentativas.");
    }
  }

  async function cancel(reminder: Reminder) {
    if (!window.confirm("Cancelar este lembrete?")) return;
    await runAction(
      () => apiFetch(`/reminders/${reminder.id}/cancel`, { method: "POST" }),
      "Lembrete cancelado.",
    );
  }

  async function completeSale(reminder: Reminder) {
    if (!window.confirm("Confirmar a venda e cancelar os lembretes pendentes deste produto?")) return;
    await runAction(
      () => apiFetch("/reminders/cancel-product", {
        method: "POST",
        body: JSON.stringify({
          store_id: storeId,
          customer_id: reminder.customer_id,
          product_interest: reminder.product_interest,
        }),
      }),
      "Venda concluída; as pendências deste produto foram canceladas.",
    );
  }

  const customerName = (id: string) => customers.find((item) => item.id === id)?.name ?? "Cliente";

  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100">
        O worker processa automaticamente os horários vencidos. “Aceito” confirma a recepção pela WhatsMiau, não a entrega ao destinatário.
      </div>
      <div className={`flex flex-col gap-3 rounded-2xl border p-4 text-sm sm:flex-row sm:items-center sm:justify-between ${readiness?.ready_to_schedule ? "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-100" : "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100"}`}><div><p className="font-semibold">WhatsMiau: {readiness?.connection_state ?? "verificando"}</p><p className="mt-1 text-xs">{readiness?.ready_to_schedule ? "Integração pronta para os lembretes desta loja." : "Verifique configuração, credencial, pausa e conexão antes de agendar."}{readiness?.homologation_only ? " Modo de homologação restrita ativo." : ""}</p></div><button onClick={checkConnection} disabled={busy || !readiness?.configured} className="rounded-xl border border-current px-3 py-2 font-medium disabled:opacity-50">Verificar conexão</button></div>
      {error && <p role="alert" className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700 dark:bg-rose-950/50 dark:text-rose-200">{error}</p>}
      {notice && <p role="status" className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-200">{notice}</p>}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-2 overflow-x-auto pb-1">
          {(["all", "pending", "accepted", "delivered", "read", "failed", "uncertain", "cancelled"] as const).map((item) => (
            <button key={item} onClick={() => setStatus(item)} className={`whitespace-nowrap rounded-xl px-3 py-2 text-sm ${status === item ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900" : "border border-slate-300 dark:border-slate-700"}`}>
              {item === "all" ? "Todos" : viewStatusLabels[item]}
            </button>
          ))}
        </div>
        <button onClick={() => { setSelected(null); setFormOpen(true); }} disabled={!eligibleCustomers.length || !activeTemplates.length} className="primary-button disabled:cursor-not-allowed disabled:opacity-50">+ Programar lembrete</button>
      </div>

      {formOpen && <ReminderForm reminder={selected} customers={eligibleCustomers} templates={activeTemplates} busy={busy} onSubmit={save} onCancel={() => { setFormOpen(false); setSelected(null); }} />}

      {!eligibleCustomers.length || !activeTemplates.length ? <p className="text-sm text-amber-700 dark:text-amber-300">Para programar, é necessário ter cliente ativo com consentimento e modelo de mensagem ativo.</p> : null}

      <div className="grid gap-4 lg:grid-cols-2">
        {visibleReminders.map((reminder) => (
          <article key={reminder.id} className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-start justify-between gap-4">
              <div><p className="font-semibold">{customerName(reminder.customer_id)}</p><p className="mt-1 text-sm text-slate-500">{reminder.product_interest}</p></div>
              <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${viewStatus(reminder) === "pending" ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200" : viewStatus(reminder) === "uncertain" ? "bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-200" : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"}`}>{viewStatusLabels[viewStatus(reminder)]}</span>
            </div>
            <p className="mt-4 text-sm font-medium">{new Intl.DateTimeFormat("pt-BR", { dateStyle: "medium", timeStyle: "short" }).format(new Date(reminder.scheduled_for))}</p>
            <div className="mt-4 rounded-xl bg-slate-50 p-4 dark:bg-slate-950"><p className="whitespace-pre-wrap text-sm leading-6">{reminder.rendered_message}</p></div>
            <dl className="mt-4 grid grid-cols-2 gap-3 text-xs"><div><dt className="text-slate-500">Tentativas</dt><dd className="mt-1 font-semibold">{reminder.attempt_count}</dd></div><div><dt className="text-slate-500">Última tentativa</dt><dd className="mt-1 font-semibold">{reminder.last_attempt_at ? new Date(reminder.last_attempt_at).toLocaleString("pt-BR") : "—"}</dd></div><div><dt className="text-slate-500">Resultado do provedor</dt><dd className="mt-1 font-semibold">{reminder.provider_status ?? "—"}</dd></div><div><dt className="text-slate-500">ID externo</dt><dd className="mt-1 truncate font-semibold">{reminder.provider_message_id ?? "—"}</dd></div></dl>
            {reminder.last_transport_error && <p className="mt-3 rounded-lg bg-rose-50 p-2 text-xs text-rose-700 dark:bg-rose-950/40 dark:text-rose-200">{reminder.last_transport_error}</p>}
            <button onClick={() => toggleHistory(reminder.id)} className="mt-3 text-xs font-semibold text-emerald-700 dark:text-emerald-300">{attemptHistory[reminder.id] ? "Ocultar tentativas" : "Ver tentativas"}</button>
            {attemptHistory[reminder.id] && <div className="mt-3 space-y-2 border-t border-slate-200 pt-3 dark:border-slate-800">{attemptHistory[reminder.id].map((attempt) => <div key={attempt.id} className="rounded-lg bg-slate-50 p-3 text-xs dark:bg-slate-950"><div className="flex justify-between gap-2"><span className="font-semibold">Tentativa {attempt.attempt_number}: {attempt.provider_status ?? attempt.status}</span><time className="text-slate-500">{new Date(attempt.started_at).toLocaleString("pt-BR")}</time></div>{attempt.delivered_at && <p className="mt-1 text-emerald-600">Entregue: {new Date(attempt.delivered_at).toLocaleString("pt-BR")}</p>}{attempt.read_at && <p className="mt-1 text-emerald-600">Lido: {new Date(attempt.read_at).toLocaleString("pt-BR")}</p>}{attempt.sanitized_error && <p className="mt-1 text-rose-600">{attempt.sanitized_error}</p>}</div>)}{!attemptHistory[reminder.id].length && <p className="text-xs text-slate-500">Nenhuma tentativa registrada.</p>}</div>}
            {reminder.failure_reason && <p className="mt-3 text-sm text-rose-600">{reminder.failure_reason}</p>}
            {reminder.status === "pending" && !["sending", "uncertain", "sent"].includes(reminder.execution_status) && <div className="mt-4 flex flex-wrap gap-2">{["pending", "retry_wait"].includes(reminder.execution_status) && <button disabled={busy} onClick={() => { setSelected(reminder); setFormOpen(true); }} className="rounded-xl border border-slate-300 px-3 py-2 text-sm dark:border-slate-700">Editar</button>}<button disabled={busy} onClick={() => cancel(reminder)} className="rounded-xl border border-rose-200 px-3 py-2 text-sm text-rose-700 dark:border-rose-900 dark:text-rose-300">Cancelar</button><button disabled={busy} onClick={() => completeSale(reminder)} className="rounded-xl bg-emerald-600 px-3 py-2 text-sm font-semibold text-white">Venda concluída</button></div>}
          </article>
        ))}
      </div>
      {!visibleReminders.length && <div className="rounded-2xl border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500 dark:border-slate-700">Nenhum lembrete encontrado neste filtro.</div>}
    </div>
  );
}

function ReminderForm({ reminder, customers, templates, busy, onSubmit, onCancel }: { reminder: Reminder | null; customers: Customer[]; templates: MessageTemplate[]; busy: boolean; onSubmit: (event: FormEvent<HTMLFormElement>) => void; onCancel: () => void }) {
  return (
    <form onSubmit={onSubmit} className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900 sm:p-6">
      <h2 className="text-xl font-bold">{reminder ? "Editar lembrete" : "Novo lembrete"}</h2>
      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <label className="text-sm font-medium">Cliente<select name="customer_id" required disabled={Boolean(reminder)} defaultValue={reminder?.customer_id ?? ""} className="field mt-2 disabled:opacity-60"><option value="" disabled>Selecione</option>{customers.map((customer) => <option key={customer.id} value={customer.id}>{customer.name}</option>)}</select></label>
        <label className="text-sm font-medium">Modelo<select name="message_template_id" required defaultValue={reminder?.message_template_id ?? ""} className="field mt-2"><option value="" disabled>Selecione</option>{templates.map((template) => <option key={template.id} value={template.id}>{template.name}</option>)}</select></label>
        <label className="text-sm font-medium">Produto de interesse<input name="product_interest" required maxLength={200} defaultValue={reminder?.product_interest ?? ""} className="field mt-2" /></label>
        <label className="text-sm font-medium">Data e horário<input name="scheduled_for" type="datetime-local" required min={toLocalInput(new Date().toISOString())} defaultValue={reminder ? toLocalInput(reminder.scheduled_for) : defaultSchedule()} className="field mt-2" /></label>
      </div>
      <div className="mt-5 flex gap-3"><button disabled={busy} className="primary-button disabled:opacity-50" type="submit">{busy ? "Salvando…" : "Salvar lembrete"}</button><button type="button" onClick={onCancel} className="rounded-xl border border-slate-300 px-4 py-3 text-sm dark:border-slate-700">Fechar</button></div>
    </form>
  );
}
