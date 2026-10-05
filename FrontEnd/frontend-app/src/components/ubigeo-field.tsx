import { useEffect, useState } from "react";

import { SearchableSelect } from "@/components/searchable-select";
import { Label } from "@/components/ui/label";
import { getDepartments, getDistricts, getProvinces, type CatalogOption } from "@/lib/smart-forms-api";

export function UbigeoField({ optionSlug, value, onValueChange, disabled }: { optionSlug: string; value: string; onValueChange: (ubigeo: string) => void; disabled?: boolean }) {
  const [department, setDepartment] = useState(value.slice(0, 2));
  const [province, setProvince] = useState(value.slice(0, 4));
  const [departments, setDepartments] = useState<CatalogOption[]>([]);
  const [provinces, setProvinces] = useState<CatalogOption[]>([]);
  const [districts, setDistricts] = useState<CatalogOption[]>([]);

  useEffect(() => { void getDepartments(optionSlug).then(setDepartments); }, [optionSlug]);
  useEffect(() => { setProvinces([]); setDistricts([]); if (department) void getProvinces(optionSlug, department).then(setProvinces); }, [optionSlug, department]);
  useEffect(() => { setDistricts([]); if (province) void getDistricts(optionSlug, province).then(setDistricts); }, [optionSlug, province]);

  return <div className="space-y-2">
    <Label>Ubicación</Label>
    <div className="grid gap-2 md:grid-cols-3">
      <SearchableSelect value={department} onValueChange={(next) => { setDepartment(next); setProvince(""); onValueChange(""); }} options={departments} placeholder="Departamento" searchPlaceholder="Buscar departamento..." disabled={disabled} />
      <SearchableSelect value={province} onValueChange={(next) => { setProvince(next); onValueChange(""); }} options={provinces} placeholder="Provincia" searchPlaceholder="Buscar provincia..." disabled={disabled || !department} />
      <SearchableSelect value={value} onValueChange={onValueChange} options={districts} placeholder="Distrito" searchPlaceholder="Buscar distrito..." disabled={disabled || !province} />
    </div>
    <p className="text-xs text-muted-foreground">Se guarda el código UBIGEO de 6 dígitos; los nombres se resuelven desde el catálogo interno.</p>
  </div>;
}
