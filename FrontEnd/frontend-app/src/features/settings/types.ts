export interface PlatformSettings {
  id: number;
  app_title: string;
  organization_name: string;
  footer_text: string;
  primary_color: string;
  ui_scale: number;
  logo_light_url: string | null;
  logo_dark_url: string | null;
  favicon_url: string | null;
}

export type PlatformSettingsWrite = Pick<PlatformSettings, "app_title" | "organization_name" | "footer_text" | "primary_color">;

export interface SmtpSettings {
  id: number;
  host: string | null;
  port: number;
  username: string | null;
  from_email: string | null;
  from_name: string;
  use_tls: boolean;
  use_ssl: boolean;
  is_active: boolean;
  password_configured: boolean;
}

export type SmtpSettingsWrite = Omit<SmtpSettings, "id" | "password_configured"> & { password?: string | null };

export interface WhatsappSettings {
  id: number;
  provider: string;
  endpoint: string;
  country_code: string;
  otp_enabled: boolean;
  otp_expiration_seconds: number;
  otp_resend_seconds: number;
  otp_code_length: number;
  otp_message: string;
  is_active: boolean;
  token_configured: boolean;
  secret_key_configured: boolean;
}

export type WhatsappSettingsWrite = Omit<WhatsappSettings, "id" | "provider" | "token_configured" | "secret_key_configured"> & {
  token?: string | null;
  secret_key?: string | null;
};

export interface MessageTemplateSettings {
  id: number;
  user_created_email_subject: string;
  user_created_email_body: string;
  user_created_whatsapp_body: string;
  password_reset_email_subject: string;
  password_reset_email_body: string;
  password_reset_whatsapp_body: string;
}

export type MessageTemplateSettingsWrite = Omit<MessageTemplateSettings, "id">;

export interface AviCapabilities {
  navigation: boolean;
  notifications: boolean;
  documentation: boolean;
  document_management: boolean;
  document_analysis: boolean;
}

export interface AviInitiative {
  enabled: boolean;
  daily_summary: boolean;
  daily_summary_time: string;
  quiet_hours_enabled: boolean;
  quiet_hours_start: string;
  quiet_hours_end: string;
  minimum_severity: "info" | "warning" | "critical";
  cooldown_minutes: number;
}

export interface AviAISettings {
  enabled: boolean;
  providers: Array<"gemini" | "groq" | "mistral">;
  gemini_model: string;
  groq_model: string;
  mistral_model: string;
  /** Reemplaza al antiguo allow_internal_data: indica consentimiento para enviar la conversación a IA externa. */
  external_ai_consent: boolean;
  external_document_consent: boolean;
  max_output_tokens: number;
  timeout_seconds: number;
  max_history_messages: number;
}

export interface AviProviderStatus {
  provider: "gemini" | "groq" | "mistral";
  configured: boolean;
  model: string;
}

/** Botón de acceso rápido administrable desde Configuración > AVI. */
export interface AviQuickPrompt {
  label: string;
  prompt: string;
  capability: keyof AviCapabilities | null;
  wolverine_slug: string | null;
}

export interface AviConfiguration {
  schema_version: number;
  enabled: boolean;
  assistant_name: string;
  welcome_message: string;
  max_results: number;
  capabilities: AviCapabilities;
  initiative: AviInitiative;
  ai: AviAISettings;
  quick_prompts: AviQuickPrompt[];
}

export interface AviSettings {
  id: number;
  revision: number;
  settings: AviConfiguration;
  updated_at: string;
  provider_status: AviProviderStatus[];
}

export interface AviPublicSettings extends Omit<AviConfiguration, "schema_version" | "ai"> {
  ai_enabled: boolean;
  quick_prompts: AviQuickPrompt[];
}

export interface AviChatMessage {
  role: "user" | "assistant";
  content: string;
  capability?: string | null;
  fallback_reason?: string | null;
}

export interface AviContextResult {
  id: string;
  source: string;
  kind: "option" | "record";
  title: string;
  subtitle: string;
  url: string;
}

export type AviFallbackReason =
  | "MISSING_ENTITY"
  | "MISSING_PARAMETER"
  | "MULTIPLE_MATCHES"
  | "LOW_CONFIDENCE"
  | "UNSUPPORTED_CAPABILITY"
  | "PERMISSION_DENIED"
  | "NO_RESULTS"
  | "PROVIDER_FAILURE"
  | "CONTEXT_CONFLICT";

export interface AviInterpretation {
  capability: string | null;
  source: "context" | "exact" | "semantic" | "llm" | "fallback";
  routing_confidence: number;
  entity_confidence: number;
  parameter_confidence: number;
  context_confidence: number;
  parameters: Record<string, unknown>;
  candidates: Array<{ capability: string; display_name: string; score: number }>;
  requires_clarification: boolean;
  fallback_reason: AviFallbackReason | null;
  message: string | null;
  no_results_message: string | null;
  selected_result: AviContextResult | null;
}

export interface AviChatResponse {
  answered: boolean;
  message: string | null;
  source: string;
  provider: "gemini" | "groq" | "mistral" | null;
  model: string | null;
  provider_error: boolean;
  privacy_blocked: boolean;
  attempted_providers: string[];
  document_sources: Array<{ document_id: number; title: string; version: number }>;
}

export interface AviThread {
  messages: Array<AviChatMessage & {
    results?: AviContextResult[];
  }>;
}
