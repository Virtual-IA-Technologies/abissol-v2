# Capa de IA

Todo proveedor debe implementar `AIProvider`. Los módulos del negocio usan
`AIService` y nunca importan directamente el SDK de OpenAI, Anthropic u otro.

Antes de habilitar un proveedor se deben definir: finalidad, datos permitidos,
retención, presupuesto, permisos, auditoría y pruebas de calidad. Las tareas
largas deberán ejecutarse mediante una cola persistente, no dentro de la
petición HTTP.
