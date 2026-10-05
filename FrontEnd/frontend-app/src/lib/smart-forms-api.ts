import api from "@/lib/api";

export type CatalogOption = { value: string; label: string };
export type DocumentType = "dni" | "ruc";
export type DocumentLookup = {
  document_type: DocumentType;
  document_number: string;
  full_name?: string | null;
  business_name?: string | null;
  first_names?: string | null;
  paternal_surname?: string | null;
  maternal_surname?: string | null;
  status?: string | null;
  condition?: string | null;
  address?: string | null;
  ubigeo?: string | null;
};

export async function lookupDocument(optionSlug: string, documentType: DocumentType, documentNumber: string) {
  const { data } = await api.post<DocumentLookup>("/smart-forms/documents/lookup", {
    option_slug: optionSlug,
    document_type: documentType,
    document_number: documentNumber,
  });
  return data;
}

export async function getDepartments(optionSlug: string) {
  const { data } = await api.get<CatalogOption[]>("/smart-forms/ubigeos/departments", { params: { option_slug: optionSlug } });
  return data;
}

export async function getProvinces(optionSlug: string, departmentCode: string) {
  const { data } = await api.get<CatalogOption[]>("/smart-forms/ubigeos/provinces", { params: { option_slug: optionSlug, department_code: departmentCode } });
  return data;
}

export async function getDistricts(optionSlug: string, provinceCode: string) {
  const { data } = await api.get<CatalogOption[]>("/smart-forms/ubigeos/districts", { params: { option_slug: optionSlug, province_code: provinceCode } });
  return data;
}
