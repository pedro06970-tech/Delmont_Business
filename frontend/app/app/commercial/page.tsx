"use client";

import { useState } from "react";

import { useActiveStore } from "@/components/app-shell";
import CustomerWorkspace from "@/components/commercial/customer-workspace";
import ReminderManager from "@/components/commercial/reminder-manager";
import TemplateManager from "@/components/commercial/template-manager";

type CommercialView = "reminders" | "customers" | "templates";

export default function CommercialPage() {
  const { activeStore, stores } = useActiveStore();
  const [view, setView] = useState<CommercialView>("reminders");
  const store = stores.find((item) => item.id === activeStore);
  const tabs: { id: CommercialView; label: string }[] = [
    { id: "reminders", label: "Lembretes" },
    { id: "customers", label: "Clientes" },
    { id: "templates", label: "Modelos" },
  ];

  return (
    <div>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-emerald-600">Comercial</p>
          <h1 className="mt-2 text-3xl font-bold">Clientes e lembretes</h1>
          <p className="mt-2 text-sm text-slate-500">{store ? `Unidade: ${store.name}` : "Selecione uma loja ativa para continuar."}</p>
        </div>
        <div className="grid grid-cols-3 rounded-xl bg-slate-200 p-1 dark:bg-slate-800">
          {tabs.map((tab) => (
            <button key={tab.id} onClick={() => setView(tab.id)} className={`min-h-11 rounded-lg px-3 text-sm font-medium ${view === tab.id ? "bg-white text-emerald-700 shadow-sm dark:bg-slate-900 dark:text-emerald-300" : "text-slate-600 dark:text-slate-300"}`}>
              {tab.label}
            </button>
          ))}
        </div>
      </div>
      {!activeStore ? (
        <div className="rounded-2xl border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500 dark:border-slate-700">Nenhuma loja ativa está disponível para o seu usuário.</div>
      ) : view === "customers" ? (
        <CustomerWorkspace key={activeStore} storeId={activeStore} />
      ) : view === "templates" ? (
        <TemplateManager key={activeStore} storeId={activeStore} />
      ) : (
        <ReminderManager key={activeStore} storeId={activeStore} />
      )}
    </div>
  );
}
