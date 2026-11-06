"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { apiFetch, User } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      await apiFetch<User>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      router.replace("/app");
      router.refresh();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Não foi possível entrar.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="grid min-h-screen bg-slate-950 text-white lg:grid-cols-2">
      <section className="hidden bg-gradient-to-br from-emerald-500 via-emerald-700 to-teal-950 p-12 lg:flex lg:flex-col lg:justify-between">
        <div className="flex items-center gap-3">
          <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/15 text-xl font-bold">D</span>
          <span className="text-lg font-semibold">Delmont Business</span>
        </div>
        <div className="max-w-lg">
          <p className="text-sm uppercase tracking-[0.25em] text-emerald-100">Ambiente seguro</p>
          <h1 className="mt-4 text-5xl font-bold leading-tight">Sua operação, organizada por loja.</h1>
          <p className="mt-5 text-emerald-50/80">Acesse somente as unidades autorizadas e mantenha a gestão centralizada.</p>
        </div>
      </section>
      <section className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-md">
          <div className="mb-10 lg:hidden">
            <p className="text-xl font-semibold text-emerald-400">Delmont Business</p>
          </div>
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-emerald-400">Acesso</p>
          <h2 className="mt-3 text-3xl font-bold">Entre na sua conta</h2>
          <p className="mt-2 text-sm text-slate-400">Use as credenciais fornecidas pelo administrador.</p>
          <form onSubmit={submit} className="mt-8 space-y-5">
            <label className="block text-sm font-medium">
              E-mail
              <input
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 outline-none transition focus:border-emerald-500"
              />
            </label>
            <label className="block text-sm font-medium">
              Senha
              <input
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="mt-2 w-full rounded-xl border border-slate-700 bg-slate-900 px-4 py-3 outline-none transition focus:border-emerald-500"
              />
            </label>
            {error && <p role="alert" className="rounded-xl bg-rose-950/60 p-3 text-sm text-rose-200">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-xl bg-emerald-600 px-4 py-3 font-semibold transition hover:bg-emerald-500 disabled:cursor-wait disabled:opacity-60"
            >
              {loading ? "Entrando…" : "Entrar"}
            </button>
          </form>
        </div>
      </section>
    </main>
  );
}
