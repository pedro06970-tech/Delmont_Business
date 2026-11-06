"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { apiFetch } from "@/lib/api";

export default function AccountPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const newPassword = String(form.get("new_password"));
    if (newPassword !== String(form.get("confirm_password"))) {
      setError("A confirmação da nova senha não confere.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      await apiFetch("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({
          current_password: form.get("current_password"),
          new_password: newPassword,
        }),
      });
      router.replace("/login");
      router.refresh();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Falha ao alterar senha.");
      setLoading(false);
    }
  }

  return (
    <div className="max-w-xl">
      <p className="text-sm font-medium uppercase tracking-[0.2em] text-emerald-600">Minha conta</p>
      <h1 className="mt-3 text-3xl font-bold">Alterar senha</h1>
      <p className="mt-2 text-sm text-slate-500">Após a alteração, todas as sessões serão encerradas.</p>
      <form onSubmit={changePassword} className="mt-8 space-y-4 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
        <input name="current_password" type="password" autoComplete="current-password" required placeholder="Senha atual" className="field" />
        <input name="new_password" type="password" autoComplete="new-password" required minLength={12} placeholder="Nova senha (mín. 12 caracteres)" className="field" />
        <input name="confirm_password" type="password" autoComplete="new-password" required minLength={12} placeholder="Confirme a nova senha" className="field" />
        {error && <p role="alert" className="text-sm text-rose-600">{error}</p>}
        <button type="submit" disabled={loading} className="primary-button">{loading ? "Alterando…" : "Alterar senha"}</button>
      </form>
    </div>
  );
}
