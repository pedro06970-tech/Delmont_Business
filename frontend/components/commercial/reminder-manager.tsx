"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  apiFetch,
  Customer,
  CustomerPage,
  MessageTemplate,
  Reminder,
  ReminderPage,
  ReminderStatus,
} from "@/lib/api";

const statusLabels: Record<ReminderStatus, string> = {
  pending: "Pendente",
  cancelled: "Cancelado",
  completed: "Concluído",
  failed: "Falhou",
};

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
  const [selected, setSelected] = useState<Reminder | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [status, setStatus] = useState<"all" | ReminderStatus>("all");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const statusQuery = status === "all" ? "" : `&status=${status}`;
    const [reminderResult, customerResult, templateResult] = await Promise.all([
      apiFetch<ReminderPage>(`/reminders?store_id=${storeId}&page_size=100${statusQuery}`),
      apiFetch<CustomerPage>(`/customers?store_id=${storeId}&page_size=100`),
      apiFetch<MessageTemplate[]>(`/message-templates?store_id=${storeId}`),
    ]);
    setReminders(reminderResult.items);
    setCustomers(customerResult.items);
    setTemplates(templateResult);
    setSelected((current) =>
      current ? reminderResult.items.find((item) => item.id === current.id) ?? null : null,
    );
  }, [status, storeId]);

  useEffect(() => {
    const statusQuery = status === "all" ? "" : `&status=${status}`;
    Promise.all([
      apiFetch<ReminderPage>(`/reminders?store_id=${storeId}&page_size=100${statusQuery}`),
      apiFetch<CustomerPage>(`/customers?store_id=${storeId}&page_size=100`),
      apiFetch<MessageTemplate[]>(`/message-templates?store_id=${storeId}`),
    ])
      .then(([reminderResult, customerResult, templateResult]) => {
        setReminders(reminderResult.items);
        setCustomers(customerResult.items);
        setTemplates(templateResult);
      })
      .catch((requestError) =>
        setError(requestError instanceof Error ? requestError.message : "Falha ao carregar lembretes."),
      );
  }, [status, storeId]);

  const eligibleCustomers = useMemo(
    () => customers.filter((customer) => customer.is_active && customer.has_consent),
    [customers],
  );
  const activeTemplates = useMemo(
    () => templates.filter((template) => template.is_active),
    [templates],
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
        Este módulo apenas programa e organiza lembretes. Nenhuma mensagem é enviada automaticamente nesta etapa.
      </div>
      {error && <p role="alert" className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700 dark:bg-rose-950/50 dark:text-rose-200">{error}</p>}
      {notice && <p role="status" className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-200">{notice}</p>}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-2 overflow-x-auto pb-1">
          {(["all", "pending", "cancelled", "completed", "failed"] as const).map((item) => (
            <button key={item} onClick={() => setStatus(item)} className={`whitespace-nowrap rounded-xl px-3 py-2 text-sm ${status === item ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900" : "border border-slate-300 dark:border-slate-700"}`}>
              {item === "all" ? "Todos" : statusLabels[item]}
            </button>
          ))}
        </div>
        <button onClick={() => { setSelected(null); setFormOpen(true); }} disabled={!eligibleCustomers.length || !activeTemplates.length} className="primary-button disabled:cursor-not-allowed disabled:opacity-50">+ Programar lembrete</button>
      </div>

      {formOpen && <ReminderForm reminder={selected} customers={eligibleCustomers} templates={activeTemplates} busy={busy} onSubmit={save} onCancel={() => { setFormOpen(false); setSelected(null); }} />}

      {!eligibleCustomers.length || !activeTemplates.length ? <p className="text-sm text-amber-700 dark:text-amber-300">Para programar, é necessário ter cliente ativo com consentimento e modelo de mensagem ativo.</p> : null}

      <div className="grid gap-4 lg:grid-cols-2">
        {reminders.map((reminder) => (
          <article key={reminder.id} className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
            <div className="flex items-start justify-between gap-4">
              <div><p className="font-semibold">{customerName(reminder.customer_id)}</p><p className="mt-1 text-sm text-slate-500">{reminder.product_interest}</p></div>
              <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${reminder.status === "pending" ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200" : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"}`}>{statusLabels[reminder.status]}</span>
            </div>
            <p className="mt-4 text-sm font-medium">{new Intl.DateTimeFormat("pt-BR", { dateStyle: "medium", timeStyle: "short" }).format(new Date(reminder.scheduled_for))}</p>
            <div className="mt-4 rounded-xl bg-slate-50 p-4 dark:bg-slate-950"><p className="whitespace-pre-wrap text-sm leading-6">{reminder.rendered_message}</p></div>
            {reminder.failure_reason && <p className="mt-3 text-sm text-rose-600">{reminder.failure_reason}</p>}
            {reminder.status === "pending" && <div className="mt-4 flex flex-wrap gap-2"><button disabled={busy} onClick={() => { setSelected(reminder); setFormOpen(true); }} className="rounded-xl border border-slate-300 px-3 py-2 text-sm dark:border-slate-700">Editar</button><button disabled={busy} onClick={() => cancel(reminder)} className="rounded-xl border border-rose-200 px-3 py-2 text-sm text-rose-700 dark:border-rose-900 dark:text-rose-300">Cancelar</button><button disabled={busy} onClick={() => completeSale(reminder)} className="rounded-xl bg-emerald-600 px-3 py-2 text-sm font-semibold text-white">Venda concluída</button></div>}
          </article>
        ))}
      </div>
      {!reminders.length && <div className="rounded-2xl border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500 dark:border-slate-700">Nenhum lembrete encontrado neste filtro.</div>}
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
