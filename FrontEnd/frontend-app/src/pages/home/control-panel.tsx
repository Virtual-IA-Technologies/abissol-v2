import { useAuth } from "@/context/AuthContext";
export default function ControlPanel() {
  const { user } = useAuth();
  return <main className="p-6 space-y-3"><h1 className="text-2xl font-semibold">ABISSOL V2</h1>
    <p>Bienvenido{user?.nombre ? `, ${user.nombre}` : ""}.</p>
    <p className="text-muted-foreground">La plataforma está lista. Utiliza el menú para administrar usuarios, accesos, documentos y configuración.</p>
  </main>;
}
