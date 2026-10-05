import { Circle, icons, type LucideProps } from "lucide-react";

function exportName(name: string) {
  return name.split("-").map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join("");
}

export default function AllLucideIcon({ name, ...props }: LucideProps & { name: string }) {
  const Icon = icons[exportName(name) as keyof typeof icons] ?? Circle;
  return <Icon {...props} />;
}
