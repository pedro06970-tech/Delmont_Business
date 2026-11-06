"use client";

import { FormEvent, useEffect, useState } from "react";

import { apiFetch, MessageTemplate } from "@/lib/api";

export default function TemplateManager({ storeId }: { storeId: string }) {
  const [templates, setTemplates] = useState<MessageTemplate[]>([]);
  const [selected, setSelected] = useState<MessageTemplate | null>(null);
  const [formMode, setFormMode] = useState<"new" | "edit" | null>(null);
  const [preview, setPreview] = useState("");
  const [previewName, setPreviewName] = useState("Maria");
  const [previewProduct, setPreviewProduct] = useState("produto escolhido");
  const [error, setError] = useState("");

  async function loadTemplates() {
    const result = await apiFetch<MessageTemplate[]>(`/message-templates?store_id=${storeId}`);
    setTemplates(result);
    if (selected) {
      setSelected(result.find((template) => template.id === selected.id) ?? null);
    }
  }

  useEffect(() => {
    apiFetch<MessageTemplate[]>(`/message-templates?store_id=${storeId}`)
      .then((result) => {
        setTemplates(result);
        setSelected(null);
        setFormMode(null);
        setPreview("");
      })
      .catch((requestError) => setError(requestError.message));
  }, [storeId]);

  async function saveTemplate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const body = {
      name: form.get("name"),
      content: form.get("content"),
      is_active: form.get("is_active") === "on",
      ...(formMode === "new" ? { store_id: storeId } : {}),
    };
    setError("");
    try {
      const saved = await apiFetch<MessageTemplate>(formMode === "new" ? "/message-templates" : `/message-templates/${selected?.id}`, {
        method: formMode === "new" ? "POST" : "PATCH",
        body: JSON.stringify(body),
      });
      await loadTemplates();
      setSelected(saved);
      setFormMode(null);
      setPreview("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Falha ao salvar modelo.");
    }
  }

  async function generatePreview() {
    if (!selected) return;
    setError("");
    try {
      const result = await apiFetch<{ rendered_content: string }>(`/message-templates/${selected.id}/preview`, {
        method: "POST",
        body: JSON.stringify({ customer_name: previewName, product: previewProduct }),
      });
      setPreview(result.rendered_content);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Falha ao gerar prévia.");
    }
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[300px_1fr]">
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <div className="flex items-center justify-between border-b border-slate-200 p-4 dark:border-slate-800"><div><h2 className="font-semibold">Modelos</h2><p className="text-xs text-slate-500">{templates.length} cadastrados</p></div><button onClick={() => { setSelected(null); setFormMode("new"); setPreview(""); }} className="rounded-xl bg-emerald-600 px-3 py-2 text-sm font-semibold text-white">+ Modelo</button></div>
        <div className="divide-y divide-slate-100 dark:divide-slate-800">{templates.length === 0 && <p className="p-5 text-sm text-slate-500">Nenhum modelo cadastrado.</p>}{templates.map((template) => <button key={template.id} onClick={() => { setSelected(template); setFormMode(null); setPreview(""); }} className={`w-full p-4 text-left hover:bg-slate-50 dark:hover:bg-slate-800 ${selected?.id === template.id ? "bg-emerald-50 dark:bg-emerald-950/40" : ""}`}><span className="block font-medium">{template.name}</span><span className={`mt-1 block text-xs ${template.is_active ? "text-emerald-600" : "text-slate-500"}`}>{template.is_active ? "Ativo" : "Inativo"}</span></button>)}</div>
      </section>

      <section className="min-h-[560px] rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900 sm:p-7">
        {error && <p role="alert" className="mb-5 rounded-xl bg-rose-50 p-3 text-sm text-rose-700 dark:bg-rose-950/50 dark:text-rose-200">{error}</p>}
        {formMode ? <TemplateForm mode={formMode} template={selected} onSubmit={saveTemplate} onCancel={() => setFormMode(null)} /> : selected ? <div><div className="flex items-start justify-between gap-4"><div><p className="text-sm uppercase tracking-[0.18em] text-emerald-600">Modelo de mensagem</p><h2 className="mt-2 text-2xl font-bold">{selected.name}</h2></div><button onClick={() => setFormMode("edit")} className="rounded-xl border border-slate-300 px-4 py-2 text-sm dark:border-slate-700">Editar</button></div><div className="mt-6 rounded-2xl bg-slate-50 p-5 dark:bg-slate-950"><p className="whitespace-pre-wrap text-sm leading-6">{selected.content}</p></div><div className="mt-6"><h3 className="font-semibold">Prévia controlada</h3><div className="mt-3 grid gap-3 sm:grid-cols-2"><input value={previewName} onChange={(event) => setPreviewName(event.target.value)} className="field" placeholder="Nome do cliente" /><input value={previewProduct} onChange={(event) => setPreviewProduct(event.target.value)} className="field" placeholder="Produto" /></div><button onClick={generatePreview} disabled={!selected.is_active} className="primary-button mt-3">Gerar prévia</button>{!selected.is_active && <p className="mt-2 text-xs text-amber-600">Ative o modelo para utilizá-lo operacionalmente.</p>}{preview && <div className="mt-5 max-w-xl rounded-2xl rounded-tl-sm bg-emerald-100 p-4 text-slate-900 shadow-sm dark:bg-emerald-900 dark:text-white"><p className="whitespace-pre-wrap text-sm leading-6">{preview}</p></div>}</div></div> : <div className="flex min-h-[500px] items-center justify-center text-center"><div><h2 className="text-xl font-semibold">Gerencie mensagens reutilizáveis</h2><p className="mt-2 max-w-md text-sm text-slate-500">Use somente as variáveis controladas. Nenhuma mensagem será agendada ou enviada nesta etapa.</p><div className="mt-5 flex flex-wrap justify-center gap-2">{["{{nome}}", "{{produto}}", "{{loja}}"].map((variable) => <code key={variable} className="rounded-lg bg-slate-100 px-3 py-2 text-xs dark:bg-slate-800">{variable}</code>)}</div></div></div>}
      </section>
    </div>
  );
}

function TemplateForm({ mode, template, onSubmit, onCancel }: { mode: "new" | "edit"; template: MessageTemplate | null; onSubmit: (event: FormEvent<HTMLFormElement>) => void; onCancel: () => void }) {
  return <form onSubmit={onSubmit} className="space-y-5"><div><p className="text-sm uppercase tracking-[0.18em] text-emerald-600">{mode === "new" ? "Cadastro" : "Edição"}</p><h2 className="mt-2 text-2xl font-bold">{mode === "new" ? "Novo modelo" : template?.name}</h2></div><label className="block text-sm font-medium">Nome interno<input name="name" required minLength={2} defaultValue={template?.name ?? ""} className="field mt-2" /></label><label className="block text-sm font-medium">Mensagem<textarea name="content" required maxLength={4000} rows={8} defaultValue={template?.content ?? "Olá, {{nome}}! Passando para lembrar daquele(a) {{produto}} que você gostou. A equipe da {{loja}} pode te ajudar."} className="field mt-2 resize-y" /></label><div className="flex flex-wrap gap-2">{["{{nome}}", "{{produto}}", "{{loja}}"].map((variable) => <code key={variable} className="rounded-lg bg-slate-100 px-3 py-2 text-xs dark:bg-slate-800">{variable}</code>)}</div><label className="flex items-center gap-3 text-sm"><input name="is_active" type="checkbox" defaultChecked={template?.is_active ?? true} className="h-5 w-5 accent-emerald-600" /> Modelo ativo</label><div className="flex gap-3"><button className="primary-button" type="submit">Salvar modelo</button><button type="button" onClick={onCancel} className="rounded-xl border border-slate-300 px-4 py-3 text-sm dark:border-slate-700">Cancelar</button></div></form>;
}
