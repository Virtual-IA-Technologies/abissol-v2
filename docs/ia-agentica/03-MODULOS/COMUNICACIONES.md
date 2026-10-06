# Comunicaciones

## Configuración y acceso

Comunicaciones separa Historial de envíos, Correo · Configuración y WhatsApp ·
Configuración. Solo Programador ve las dos últimas; GET/PUT y envío de pruebas
SMTP/Wablas verifican ese rol en backend, incluso si un administrador tiene
permisos de edición. El historial y el envío comercial conservan su alcance por
emisor. Los paneles reutilizan la misma configuración global, sin duplicar claves.

Facturación y Comunicaciones usan `UnderlineTabs`, con línea inferior verde,
panel asociado, flechas/Home/End y desplazamiento horizontal en pantallas pequeñas.

## Origen Laravel

`BackEnd/scripts/import_legacy_communications.py` se ejecuta en el servidor.
Por defecto muestra solo indicadores. `--apply --legacy-env <ruta privada>
--backup-dir <directorio privado>` conserva una copia de los valores anteriores,
actualiza los dos canales en una transacción y registra auditoría sin secretos.
No copia cuentas, OTP, plantillas de acceso, configuración fiscal ni cron.

Correo reproduce `MailConfigHelper`: los valores del grupo `mail_config`
prevalecen cuando está habilitado; de lo contrario usa el transporte del entorno.
Wablas reproduce la prioridad de `MedicalEmissionController`: primero
`medical_settings`, después `system_settings`, finalmente entorno.
Claves cifradas con la llave de V2; nunca se devuelven en la API. Los campos vacíos
de las pantallas de edición conservan las claves actuales. OTP queda deshabilitado.

Aplicado el 05/10/2026 desde el Laravel productivo, con copia privada y auditoría.
SMTP: conexión TLS y autenticación verificadas, sin enviar correos.
Wablas: parámetros migrados y descifrado verificado; entrega real no probada.
Pruebas aisladas verifican permisos, precedencia y protocolo Wablas con transporte
simulado. No se enviaron mensajes a clientes durante la migración.

Liquidaciones conserva sus importes, conciliación e historial; su mejora funcional
queda para una siguiente solicitud. La programación automática de envíos de
Laravel no se activa por copiar los canales.
