"use client";

import { FormEvent, useEffect, useState } from "react";

import { apiFetch, Customer, CustomerDetail, CustomerPage } from "@/lib/api";

export default function CustomerWorkspace({ storeId }: { storeId: string }) {
  const [customers, setCustomers] = useState<CustomerPage>({ items: [], total: 0, page: 1, page_size: 20, pages: 0 });
  const [selected, setSelected] = useState<CustomerDetail | null>(null);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [formMode, setFormMode] = useState<"new" | "edit" | null>(null);
  const [mobileDetail, setMobileDetail] = useState(false);
  const [consentSource, setConsentSource] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function loadCustomers(nextPage = page) {
    const params = new URLSearchParams({ store_id: storeId, page: String(nextPage), page_size: "20" });
    if (query) params.set("search", query);
    const result = await apiFetch<CustomerPage>(`/customers?${params}`);
    setCustomers(result);
    if (selected) {
      const stillVisible = result.items.some((customer) => customer.id === selected.id);
      if (!stillVisible) setSelected(null);
    }
  }

  useEffect(() => {
    const params = new URLSearchParams({ store_id: storeId, page: String(page), page_size: "20" });
    if (query) params.set("search", query);
    apiFetch<CustomerPage>(`/customers?${params}`)
      .then((result) => {
        setCustomers(result);
        setSelected(null);
        setMobileDetail(false);
      })
      .catch((requestError) => setError(requestError.message))
      .finally(() => setLoading(false));
  }, [storeId, query, page]);

  async function selectCustomer(customer: Customer) {
    setError("");
    try {
      const detail = await apiFetch<CustomerDetail>(`/customers/${customer.id}`);
      setSelected(detail);
      setMobileDetail(true);
      setFormMode(null);
      setConsentSource("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Falha ao abrir cliente.");
    }
  }

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage(1);
    setQuery(search.trim());
  }

  async function saveCustomer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const body = {
      name: form.get("name"),
      phone: form.get("phone"),
      notes: form.get("notes") || null,
      ...(formMode === "new" ? { store_id: storeId } : { is_active: form.get("is_active") === "on" }),
    };
    setError("");
    try {
      const saved = await apiFetch<Customer>(formMode === "new" ? "/customers" : `/customers/${selected?.id}`, {
        method: formMode === "new" ? "POST" : "PATCH",
        body: JSON.stringify(body),
      });
      await loadCustomers(1);
      const detail = await apiFetch<CustomerDetail>(`/customers/${saved.id}`);
      setSelected(detail);
      setPage(1);
      setFormMode(null);
      setMobileDetail(true);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Falha ao salvar cliente.");
    }
  }

  async function updateConsent(action: "grant" | "revoke") {
    if (!selected) return;
    if (action === "grant" && !consentSource.trim()) {
      setError("Informe como o consentimento foi obtido.");
      return;
    }
    setError("");
    try {
      const detail = await apiFetch<CustomerDetail>(
        action === "grant" ? `/customers/${selected.id}/consent` : `/customers/${selected.id}/revoke-consent`,
        {
          method: "POST",
          body: action === "grant" ? JSON.stringify({ source: consentSource.trim() }) : undefined,
        },
      );
      setSelected(detail);
      setConsentSource("");
      await loadCustomers();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Falha ao atualizar consentimento.");
    }
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900 lg:grid lg:min-h-[680px] lg:grid-cols-[340px_1fr]">
      <section className={`${mobileDetail ? "hidden lg:flex" : "flex"} min-h-[620px] flex-col border-r border-slate-200 dark:border-slate-800`}>
        <div className="border-b border-slate-200 p-4 dark:border-slate-800">
          <div className="flex items-center justify-between gap-3">
            <div><h2 className="font-semibold">Clientes</h2><p className="text-xs text-slate-500">{customers.total} cadastrados</p></div>
            <button onClick={() => { setFormMode("new"); setSelected(null); setMobileDetail(true); }} className="rounded-xl bg-emerald-600 px-4 py-3 text-sm font-semibold text-white">+ Cliente</button>
          </div>
          <form onSubmit={submitSearch} className="mt-4 flex gap-2">
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar nome ou telefone" className="field" />
            <button className="rounded-xl border border-slate-300 px-3 text-sm dark:border-slate-700">Buscar</button>
          </form>
        </div>
        <div className="flex-1 overflow-y-auto">
          {loading && <p className="p-5 text-sm text-slate-500">Carregando clientes…</p>}
          {!loading && customers.items.length === 0 && <p className="p-5 text-sm text-slate-500">Nenhum cliente encontrado.</p>}
          {customers.items.map((customer) => (
            <button key={customer.id} onClick={() => selectCustomer(customer)} className={`flex w-full items-center gap-3 border-b border-slate-100 p-4 text-left transition hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800 ${selected?.id === customer.id ? "bg-emerald-50 dark:bg-emerald-950/40" : ""}`}>
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-emerald-100 font-semibold text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">{customer.name.slice(0, 1).toUpperCase()}</span>
              <span className="min-w-0 flex-1"><span className="block truncate font-medium">{customer.name}</span><span className="block text-sm text-slate-500">{customer.phone_e164}</span></span>
              <span className={`h-2.5 w-2.5 rounded-full ${customer.has_consent ? "bg-emerald-500" : "bg-slate-300 dark:bg-slate-600"}`} title={customer.has_consent ? "Consentimento ativo" : "Sem consentimento"} />
            </button>
          ))}
        </div>
        {customers.pages > 1 && <div className="flex items-center justify-between border-t border-slate-200 p-3 text-sm dark:border-slate-800"><button disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>Anterior</button><span>{page} / {customers.pages}</span><button disabled={page >= customers.pages} onClick={() => setPage((current) => current + 1)}>Próxima</button></div>}
      </section>

      <section className={`${mobileDetail ? "block" : "hidden lg:block"} min-h-[620px] bg-slate-50/70 dark:bg-slate-950/40`}>
        <div className="flex items-center justify-between border-b border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900 lg:hidden">
          <button onClick={() => setMobileDetail(false)} className="rounded-xl border border-slate-300 px-4 py-3 text-sm dark:border-slate-700">← Clientes</button>
          {selected && <button onClick={() => setFormMode("edit")} className="text-sm font-medium text-emerald-600">Editar</button>}
        </div>
        {error && <p role="alert" className="m-5 rounded-xl bg-rose-50 p-3 text-sm text-rose-700 dark:bg-rose-950/50 dark:text-rose-200">{error}</p>}
        {formMode ? (
          <CustomerForm mode={formMode} customer={selected} onSubmit={saveCustomer} onCancel={() => { setFormMode(null); if (!selected) setMobileDetail(false); }} />
        ) : selected ? (
          <CustomerCard customer={selected} consentSource={consentSource} onConsentSource={setConsentSource} onConsent={updateConsent} onEdit={() => setFormMode("edit")} />
        ) : (
          <div className="hidden h-full min-h-[620px] items-center justify-center p-8 text-center lg:flex"><div><span className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 text-2xl text-emerald-700 dark:bg-emerald-950">D</span><h2 className="mt-4 text-xl font-semibold">Selecione um cliente</h2><p className="mt-2 max-w-sm text-sm text-slate-500">Consulte dados, consentimento e histórico comercial sem iniciar conversas em tempo real.</p></div></div>
        )}
      </section>
    </div>
  );
}

function CustomerForm({ mode, customer, onSubmit, onCancel }: { mode: "new" | "edit"; customer: CustomerDetail | null; onSubmit: (event: FormEvent<HTMLFormElement>) => void; onCancel: () => void }) {
  return <form onSubmit={onSubmit} className="mx-auto max-w-2xl space-y-5 p-5 sm:p-8"><div><p className="text-sm uppercase tracking-[0.18em] text-emerald-600">{mode === "new" ? "Cadastro" : "Edição"}</p><h2 className="mt-2 text-2xl font-bold">{mode === "new" ? "Novo cliente" : customer?.name}</h2></div><label className="block text-sm font-medium">Nome<input name="name" required minLength={2} defaultValue={customer?.name ?? ""} className="field mt-2" /></label><label className="block text-sm font-medium">WhatsApp<input name="phone" required defaultValue={customer?.phone_e164 ?? ""} placeholder="(11) 91234-5678" className="field mt-2" /></label><label className="block text-sm font-medium">Observações<textarea name="notes" maxLength={2000} rows={5} defaultValue={customer?.notes ?? ""} className="field mt-2 resize-y" /></label>{mode === "edit" && <label className="flex items-center gap-3 text-sm"><input name="is_active" type="checkbox" defaultChecked={customer?.is_active} className="h-5 w-5 accent-emerald-600" /> Cliente ativo</label>}<p className="rounded-xl bg-amber-50 p-3 text-xs text-amber-800 dark:bg-amber-950/40 dark:text-amber-200">O cadastro não concede consentimento automaticamente. Registre a autorização separadamente na ficha do cliente.</p><div className="flex gap-3"><button type="submit" className="primary-button">Salvar</button><button type="button" onClick={onCancel} className="rounded-xl border border-slate-300 px-4 py-3 text-sm dark:border-slate-700">Cancelar</button></div></form>;
}

function CustomerCard({ customer, consentSource, onConsentSource, onConsent, onEdit }: { customer: CustomerDetail; consentSource: string; onConsentSource: (value: string) => void; onConsent: (action: "grant" | "revoke") => void; onEdit: () => void }) {
  return <div className="mx-auto max-w-3xl p-5 sm:p-8"><div className="flex items-start gap-4"><span className="flex h-16 w-16 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-2xl font-bold text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">{customer.name.slice(0, 1).toUpperCase()}</span><div className="min-w-0 flex-1"><h2 className="truncate text-2xl font-bold">{customer.name}</h2><p className="text-slate-500">{customer.phone_e164}</p></div><button onClick={onEdit} className="hidden rounded-xl border border-slate-300 px-4 py-2 text-sm lg:block dark:border-slate-700">Editar</button></div><div className="mt-8 grid gap-4 sm:grid-cols-2"><div className="rounded-2xl bg-white p-5 dark:bg-slate-900"><p className="text-xs uppercase tracking-wider text-slate-500">Status</p><p className="mt-2 font-semibold">{customer.is_active ? "Cliente ativo" : "Cliente inativo"}</p></div><div className={`rounded-2xl p-5 ${customer.has_consent ? "bg-emerald-50 dark:bg-emerald-950/50" : "bg-amber-50 dark:bg-amber-950/40"}`}><p className="text-xs uppercase tracking-wider text-slate-500">Lembretes comerciais</p><p className="mt-2 font-semibold">{customer.has_consent ? "Consentimento ativo" : "Sem consentimento"}</p></div></div>{customer.notes && <div className="mt-4 rounded-2xl bg-white p-5 dark:bg-slate-900"><p className="text-xs uppercase tracking-wider text-slate-500">Observações</p><p className="mt-2 whitespace-pre-wrap text-sm">{customer.notes}</p></div>}<div className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900"><h3 className="font-semibold">Consentimento</h3>{customer.has_consent ? <div className="mt-3"><p className="text-sm text-slate-600 dark:text-slate-300">Origem: {customer.consent_source}</p><button onClick={() => onConsent("revoke")} className="mt-4 min-h-11 rounded-xl border border-rose-300 px-4 py-2 text-sm font-medium text-rose-700 dark:border-rose-900 dark:text-rose-300">Revogar consentimento</button></div> : <div className="mt-3"><label className="text-sm">Origem da autorização<input value={consentSource} onChange={(event) => onConsentSource(event.target.value)} placeholder="Ex.: formulário assinado na loja" className="field mt-2" /></label><button onClick={() => onConsent("grant")} className="primary-button mt-3 min-h-11">Registrar consentimento</button></div>}<div className="mt-5 border-t border-slate-200 pt-4 dark:border-slate-800"><p className="text-xs font-medium uppercase tracking-wider text-slate-500">Histórico</p>{customer.consent_history.length === 0 ? <p className="mt-2 text-sm text-slate-500">Nenhuma alteração registrada.</p> : <ul className="mt-2 space-y-2">{customer.consent_history.map((event) => <li key={event.id} className="text-sm"><span className={event.action === "granted" ? "text-emerald-600" : "text-rose-600"}>{event.action === "granted" ? "Concedido" : "Revogado"}</span> · {new Date(event.occurred_at).toLocaleString("pt-BR")}{event.source && ` · ${event.source}`}</li>)}</ul>}</div></div></div>;
}
