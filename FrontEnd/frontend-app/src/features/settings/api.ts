import api, { sessionClient } from "@/lib/api";
import type { AviChatMessage, AviChatResponse, AviConfiguration, AviContextResult, AviInterpretation, AviPublicSettings, AviSettings, AviThread, MessageTemplateSettings, MessageTemplateSettingsWrite, PlatformSettings, PlatformSettingsWrite, SmtpSettings, SmtpSettingsWrite, WhatsappSettings, WhatsappSettingsWrite } from "./types";

export const settingsAPI = {
  askAgent: async (question: string, history: AviChatMessage[], contextResults: AviContextResult[]) =>
    (await api.post<{message: string; source: string; capability: string | null; results: AviContextResult[]; tools: string[]; warnings: string[]; truncated: boolean; navigate_to: string | null}>("/avi/agente", { question, history, context_results: contextResults }, {timeout: 65_000})).data,
  get: async () => (await sessionClient.get<PlatformSettings>("/ui-settings")).data,
  update: async (payload: PlatformSettingsWrite) => (await api.put<PlatformSettings>("/ui-settings", payload)).data,
  uploadBranding: async (files: { logo_light?: File; logo_dark?: File; favicon?: File }) => {
    const data = new FormData();
    Object.entries(files).forEach(([key, file]) => { if (file) data.append(key, file); });
    return (await api.post<PlatformSettings>("/ui-settings/branding", data)).data;
  },
  getSmtp: async () => (await api.get<SmtpSettings>("/smtp-settings")).data,
  updateSmtp: async (payload: SmtpSettingsWrite) => (await api.put<SmtpSettings>("/smtp-settings", payload)).data,
  testSmtp: async (recipient: string) => (await api.post<{ message: string }>("/smtp-settings/test", { recipient })).data,
  getWhatsapp: async () => (await api.get<WhatsappSettings>("/whatsapp-settings")).data,
  updateWhatsapp: async (payload: WhatsappSettingsWrite) => (await api.put<WhatsappSettings>("/whatsapp-settings", payload)).data,
  testWhatsapp: async (phone: string, message: string) => (await api.post<{ message: string }>("/whatsapp-settings/test", { phone, message })).data,
  getMessageTemplates: async () => (await api.get<MessageTemplateSettings>("/message-templates")).data,
  updateMessageTemplates: async (payload: MessageTemplateSettingsWrite) => (await api.put<MessageTemplateSettings>("/message-templates", payload)).data,
  getAvi: async () => (await api.get<AviSettings>("/avi-settings")).data,
  updateAvi: async (revision: number, settings: AviConfiguration) => (await api.put<AviSettings>("/avi-settings", { revision, settings })).data,
  getAviContext: async () => (await api.get<AviPublicSettings>("/avi/contexto")).data,
  askAvi: async (question: string, history: AviChatMessage[], internalResultsFound = false) =>
    (await api.post<AviChatResponse>("/avi/consulta", { question, history, internal_results_found: internalResultsFound }, { timeout: 65_000 })).data,
  interpretAvi: async (question: string, history: AviChatMessage[], contextResults: AviContextResult[]) =>
    (await api.post<AviInterpretation>("/avi/interpretar", { question, history, context_results: contextResults })).data,
  /** Recupera el hilo de conversación persistido del usuario autenticado. */
  getAviThread: async () => (await api.get<AviThread>("/avi/hilo")).data,
  /** Guarda el hilo completo (reemplaza el anterior). */
  saveAviThread: async (messages: AviThread["messages"]) =>
    (await api.put<AviThread>("/avi/hilo", { messages })).data,
  /** Borra el hilo del usuario. */
  clearAviThread: async () => { await api.delete("/avi/hilo"); },
};
