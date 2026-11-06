export default function AppHomePage() {
  return (
    <div>
      <p className="text-sm font-medium uppercase tracking-[0.2em] text-emerald-600">Visão geral</p>
      <h1 className="mt-3 text-3xl font-bold">Bem-vindo ao Delmont Business</h1>
      <p className="mt-3 max-w-2xl text-slate-600 dark:text-slate-300">
        A estrutura de acesso por usuário e loja está pronta. Os módulos de lembretes e inteligência financeira serão adicionados nas próximas etapas.
      </p>
      <div className="mt-10 grid gap-4 sm:grid-cols-2">
        {[
          ["Lembretes comerciais", "Ainda não implementado nesta task."],
          ["Inteligência financeira", "Ainda não implementado nesta task."],
        ].map(([title, description]) => (
          <section key={title} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <span className="inline-flex rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">Em breve</span>
            <h2 className="mt-4 text-xl font-semibold">{title}</h2>
            <p className="mt-2 text-sm text-slate-500">{description}</p>
          </section>
        ))}
      </div>
    </div>
  );
}
