import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props { children: ReactNode }
interface State { failed: boolean }

export class AppErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ABISSOL no pudo renderizar la pantalla", error, info);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-950 p-6 text-white">
        <section className="max-w-md rounded-2xl border border-white/10 bg-slate-900 p-7 text-center shadow-2xl">
          <h1 className="text-xl font-semibold">No se pudo mostrar esta pantalla</h1>
          <p className="mt-3 text-sm leading-6 text-slate-300">
            Recarga la aplicación. Si el problema continúa, el identificador de la petición permitirá revisarlo.
          </p>
          <button
            className="mt-6 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-medium hover:bg-blue-500"
            onClick={() => window.location.reload()}
          >
            Recargar ABISSOL
          </button>
        </section>
      </main>
    );
  }
}
