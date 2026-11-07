"use client";

import { FormEvent, useEffect, useState } from "react";

import { apiFetch, Store, User, UserRole } from "@/lib/api";
import WhatsMiauManager from "@/components/admin/whatsmiau-manager";

type UserStores = { user_id: string; stores: Store[] };

export default function AdminPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [stores, setStores] = useState<Store[]>([]);
  const [selectedUser, setSelectedUser] = useState("");
  const [selectedStores, setSelectedStores] = useState<string[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function loadData() {
    setError("");
    try {
      const [userList, storeList] = await Promise.all([
        apiFetch<User[]>("/users"),
        apiFetch<Store[]>("/stores"),
      ]);
      setUsers(userList);
      setStores(storeList);
      setSelectedUser((current) => current || userList[0]?.id || "");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Falha ao carregar dados.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    Promise.all([apiFetch<User[]>("/users"), apiFetch<Store[]>("/stores")])
      .then(([userList, storeList]) => {
        setUsers(userList);
        setStores(storeList);
        setSelectedUser((current) => current || userList[0]?.id || "");
      })
      .catch((requestError) => setError(requestError.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedUser) {
      return;
    }
    apiFetch<UserStores>(`/users/${selectedUser}/stores`)
      .then((result) => setSelectedStores(result.stores.map((store) => store.id)))
      .catch((requestError) => setError(requestError.message));
  }, [selectedUser]);

  async function createUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError("");
    try {
      await apiFetch<User>("/users", {
        method: "POST",
        body: JSON.stringify({
          name: form.get("name"),
          email: form.get("email"),
          password: form.get("password"),
          role: form.get("role"),
        }),
      });
      event.currentTarget.reset();
      setMessage("Usuário criado com sucesso.");
      await loadData();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Falha ao criar usuário.");
    }
  }

  async function updateUser(user: User, changes: { role?: UserRole; is_active?: boolean }) {
    setError("");
    try {
      await apiFetch(`/users/${user.id}`, { method: "PATCH", body: JSON.stringify(changes) });
      setMessage("Usuário atualizado.");
      await loadData();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Falha ao atualizar usuário.");
    }
  }

  async function createStore(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError("");
    try {
      await apiFetch<Store>("/stores", {
        method: "POST",
        body: JSON.stringify({ name: form.get("name") }),
      });
      event.currentTarget.reset();
      setMessage("Loja criada com sucesso.");
      await loadData();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Falha ao criar loja.");
    }
  }

  async function toggleStore(store: Store) {
    setError("");
    try {
      await apiFetch(`/stores/${store.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: !store.is_active }),
      });
      setMessage("Loja atualizada.");
      await loadData();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Falha ao atualizar loja.");
    }
  }

  async function saveAssociations() {
    if (!selectedUser) return;
    setError("");
    try {
      await apiFetch(`/users/${selectedUser}/stores`, {
        method: "PUT",
        body: JSON.stringify({ store_ids: selectedStores }),
      });
      setMessage("Acesso às lojas atualizado.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Falha ao associar lojas.");
    }
  }

  if (loading) return <p className="text-sm text-slate-500">Carregando administração…</p>;

  return (
    <div className="space-y-10">
      <div>
        <p className="text-sm font-medium uppercase tracking-[0.2em] text-emerald-600">Administração</p>
        <h1 className="mt-3 text-3xl font-bold">Usuários e lojas</h1>
      </div>
      {(error || message) && (
        <div className={`rounded-xl p-4 text-sm ${error ? "bg-rose-50 text-rose-700 dark:bg-rose-950/50 dark:text-rose-200" : "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-200"}`}>
          {error || message}
        </div>
      )}

      <section className="grid gap-6 xl:grid-cols-[1fr_2fr]">
        <form onSubmit={createUser} className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
          <h2 className="text-lg font-semibold">Novo usuário</h2>
          <input name="name" required minLength={2} placeholder="Nome" className="field" />
          <input name="email" required type="email" placeholder="E-mail" className="field" />
          <input name="password" required type="password" minLength={12} placeholder="Senha inicial (mín. 12)" className="field" />
          <select name="role" className="field" defaultValue="collaborator">
            <option value="collaborator">Colaborador</option>
            <option value="admin">Administrador</option>
          </select>
          <button className="primary-button" type="submit">Cadastrar usuário</button>
        </form>

        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
          <div className="border-b border-slate-200 p-5 dark:border-slate-800"><h2 className="text-lg font-semibold">Usuários</h2></div>
          <div className="divide-y divide-slate-100 dark:divide-slate-800">
            {users.map((user) => (
              <div key={user.id} className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center">
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{user.name}</p>
                  <p className="truncate text-sm text-slate-500">{user.email}</p>
                </div>
                <select
                  aria-label={`Perfil de ${user.name}`}
                  value={user.role}
                  onChange={(event) => updateUser(user, { role: event.target.value as UserRole })}
                  className="rounded-lg border border-slate-300 bg-transparent px-3 py-2 text-sm dark:border-slate-700"
                >
                  <option value="collaborator">Colaborador</option>
                  <option value="admin">Administrador</option>
                </select>
                <button onClick={() => updateUser(user, { is_active: !user.is_active })} className={`rounded-lg px-3 py-2 text-sm font-medium ${user.is_active ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950" : "bg-slate-100 text-slate-600 dark:bg-slate-800"}`}>
                  {user.is_active ? "Ativo" : "Inativo"}
                </button>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1fr_2fr]">
        <form onSubmit={createStore} className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
          <h2 className="text-lg font-semibold">Nova loja</h2>
          <input name="name" required minLength={2} placeholder="Nome da unidade" className="field" />
          <button className="primary-button" type="submit">Cadastrar loja</button>
        </form>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
          <h2 className="text-lg font-semibold">Lojas</h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {stores.map((store) => (
              <div key={store.id} className="flex items-center justify-between rounded-xl border border-slate-200 p-4 dark:border-slate-700">
                <span className="font-medium">{store.name}</span>
                <button onClick={() => toggleStore(store)} className="text-sm text-emerald-700 dark:text-emerald-400">{store.is_active ? "Ativa" : "Inativa"}</button>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
        <h2 className="text-lg font-semibold">Associação às lojas</h2>
        <div className="mt-4 grid gap-5 lg:grid-cols-[1fr_2fr_auto] lg:items-end">
          <label className="text-sm font-medium">Usuário
            <select value={selectedUser} onChange={(event) => setSelectedUser(event.target.value)} className="field mt-2">
              {users.map((user) => <option key={user.id} value={user.id}>{user.name}</option>)}
            </select>
          </label>
          <div className="grid gap-2 sm:grid-cols-2">
            {stores.map((store) => (
              <label key={store.id} className="flex items-center gap-3 rounded-xl border border-slate-200 p-3 text-sm dark:border-slate-700">
                <input
                  type="checkbox"
                  checked={selectedStores.includes(store.id)}
                  onChange={(event) => setSelectedStores((current) => event.target.checked ? [...current, store.id] : current.filter((id) => id !== store.id))}
                  className="h-4 w-4 accent-emerald-600"
                />
                {store.name}{!store.is_active && " (inativa)"}
              </label>
            ))}
          </div>
          <button onClick={saveAssociations} className="primary-button">Salvar acessos</button>
        </div>
      </section>

      <WhatsMiauManager stores={stores} />
    </div>
  );
}
