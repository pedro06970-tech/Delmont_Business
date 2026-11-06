"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";

import { apiFetch, Store, User } from "@/lib/api";

type ActiveStoreContextValue = {
  activeStore: string;
  stores: Store[];
};

const ActiveStoreContext = createContext<ActiveStoreContextValue | null>(null);

export function useActiveStore() {
  const context = useContext(ActiveStoreContext);
  if (!context) throw new Error("useActiveStore must be used inside AppShell");
  return context;
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [stores, setStores] = useState<Store[]>([]);
  const [activeStore, setActiveStore] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([apiFetch<User>("/auth/me"), apiFetch<Store[]>("/stores")])
      .then(([currentUser, availableStores]) => {
        if (pathname.startsWith("/app/admin") && currentUser.role !== "admin") {
          router.replace("/app");
          return;
        }
        setUser(currentUser);
        setStores(availableStores);
        const enabled = availableStores.filter((store) => store.is_active);
        const saved = window.localStorage.getItem("delmont_active_store");
        const selected = enabled.some((store) => store.id === saved)
          ? saved!
          : (enabled[0]?.id ?? "");
        setActiveStore(selected);
      })
      .catch(() => router.replace("/login"));
  }, [pathname, router]);

  function selectStore(storeId: string) {
    setActiveStore(storeId);
    window.localStorage.setItem("delmont_active_store", storeId);
  }

  async function logout() {
    setError("");
    try {
      await apiFetch("/auth/logout", { method: "POST" });
      window.localStorage.removeItem("delmont_active_store");
      router.replace("/login");
      router.refresh();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Falha ao sair.");
    }
  }

  if (!user) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-200">
        <p className="animate-pulse text-sm">Carregando ambiente seguro…</p>
      </main>
    );
  }

  const links = [
    { href: "/app", label: "Início" },
    { href: "/app/commercial", label: "Comercial" },
    { href: "/app/account", label: "Minha conta" },
    ...(user.role === "admin" ? [{ href: "/app/admin", label: "Administração" }] : []),
  ];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900 lg:flex lg:flex-col">
        <Link href="/app" className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-600 font-bold text-white">D</span>
          <span className="font-semibold">Delmont Business</span>
        </Link>
        <nav className="mt-10 space-y-2">
          {links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={`block rounded-xl px-4 py-3 text-sm font-medium transition ${pathname === link.href ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300" : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"}`}
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <div className="mt-auto border-t border-slate-200 pt-5 dark:border-slate-800">
          <p className="font-medium">{user.name}</p>
          <p className="truncate text-xs text-slate-500">{user.email}</p>
          <button onClick={logout} className="mt-4 text-sm font-medium text-rose-600 hover:text-rose-700">Sair</button>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur dark:border-slate-800 dark:bg-slate-900/90 sm:px-6">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 sm:flex-nowrap sm:gap-4">
            <div className="lg:hidden">
              <p className="font-semibold text-emerald-700 dark:text-emerald-400">Delmont</p>
              <nav className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs">
                {links.map((link) => <Link key={link.href} href={link.href}>{link.label}</Link>)}
              </nav>
            </div>
            <label className="order-3 flex w-full items-center gap-2 text-sm text-slate-600 sm:order-none sm:ml-auto sm:w-auto dark:text-slate-300">
              <span className="hidden sm:inline">Loja ativa</span>
              <select
                value={activeStore}
                onChange={(event) => selectStore(event.target.value)}
                className="min-w-0 flex-1 rounded-xl border border-slate-300 bg-white px-3 py-2 text-slate-900 outline-none focus:border-emerald-500 sm:max-w-48 dark:border-slate-700 dark:bg-slate-800 dark:text-white"
              >
                <option value="">Nenhuma loja disponível</option>
                {stores.filter((store) => store.is_active).map((store) => (
                  <option key={store.id} value={store.id}>{store.name}</option>
                ))}
              </select>
            </label>
            <button onClick={logout} className="rounded-xl border border-slate-200 px-3 py-2 text-sm lg:hidden dark:border-slate-700">Sair</button>
          </div>
          {error && <p className="mx-auto mt-2 max-w-6xl text-xs text-rose-600">{error}</p>}
        </header>
        <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8">
          <ActiveStoreContext.Provider value={{ activeStore, stores }}>
            {children}
          </ActiveStoreContext.Provider>
        </main>
      </div>
    </div>
  );
}
