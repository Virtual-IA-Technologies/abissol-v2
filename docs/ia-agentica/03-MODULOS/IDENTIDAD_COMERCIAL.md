# Cuentas, entidades y participantes comerciales

## Separación de responsabilidades

- **Usuario:** cuenta de inicio de sesión ABISSOL. Conserva autenticación,
  contraseña, sesiones y roles de la plataforma. No representa una AFOCAT.
- **Origen:** entidad comercial ABISSOL, AFOCAT o aliado. Su clave externa
  identifica el sistema de procedencia; no sirve como credencial de API.
- **Participante:** persona o punto de venta, identificado de forma estable.
  Puede vincularse a una cuenta ABISSOL o existir solo como actor externo.
- **Función comercial:** vendedor responsable, emisor dependiente o coordinador.
  Determina alcance y atribución comercial; no otorga acceso automáticamente.
- **Rol de acceso:** operaciones de menú permitidas. Se combina siempre con
  el alcance del participante, nunca lo sustituye.
- **Canal de registro:** portal ABISSOL o conector externo. Una AFOCAT también
  puede tener participantes con cuenta para entrar al portal; entidad y canal
  son conceptos diferentes.

No emparejar participantes por nombre, correo o coincidencia de números entre
tablas. La identidad externa es `(origen, external_user_id)`. Dos AFOCAT pueden
tener un usuario con el mismo número sin representar a la misma persona.

## Funciones y permisos recomendados

| Función | Emisiones y comunicaciones | Reportes | Liquidaciones | Administración |
|---|---|---|---|---|
| Vendedor responsable | Propias y de sus emisores | Su equipo | Preparar/presentar su ámbito | No |
| Emisor dependiente | Solo propias | Solo propias | No | No |
| Coordinador de origen | Su entidad | Su entidad | Preparar/presentar su entidad | No; red comercial en lectura |

Un vendedor responsable puede emitir por sí mismo: no necesita otra cuenta ni
un perfil adicional de emisor. El emisor dependiente debe pertenecer al mismo
origen que su responsable. El coordinador no es administrador de ABISSOL y no
puede confirmar ingresos a ABISSOL ni aprobar/cerrar liquidaciones.

Los roles comerciales no conceden edición de precios, facturación, usuarios,
accesos, configuración ni DevOps. Los roles administrativos existentes y los
permisos individuales permanecen; revisar esas excepciones desde Accesos si
se requiere restringir una cuenta que ya tenía privilegios superiores.

## Flujo de configuración en V2

1. Crear la entidad en **Red comercial → Agregar origen**. ABISSOL ya existe.
2. Crear un **participante**, elegir origen y función.
3. Para operación directa, vincular una cuenta creada en Usuarios. Para un
   actor externo sin acceso al portal, registrar nombre e identificador externo
   bajo una entidad con clave de integración.
4. Al vincular una cuenta, marcar **Asignar rol comercial recomendado** si se
   desea aplicar el rol. Reemplaza únicamente los tres roles comerciales
   administrados por este flujo, con auditoría; no elimina roles de plataforma.
5. Si el externo necesita acceso posteriormente, editar el mismo participante
   y vincular la cuenta. No crear otra identidad para sus ventas históricas.

La tabla muestra participante, cuenta, roles vigentes, ID externo, origen,
responsable y estado. Una cuenta desactivada y un participante comercial
inactivo son estados independientes: el primero impide login; el segundo
impide nueva operación comercial en su ámbito.

## Compatibilidad e integraciones

La revisión productiva se realizó mediante lecturas limitadas en Laravel y en
la integración de La Primera. `emitir/` envía la venta asociada al CAT;
`abissol/nueva_emision.php` permite venta independiente. Ambos transmiten
`external_source`, `external_reference`, `external_emitter_id` y
`external_responsible_id`, autenticándose mediante una cuenta técnica.

En el diseño de V2 la cuenta técnica debe identificar el conector/origen,
no apropiarse de la venta ni de la comisión del responsable. El futuro endpoint
externo debe obtener el origen de la credencial autenticada, resolver ambos
participantes dentro de ese origen y aplicar idempotencia por referencia.
No confiar en un origen arbitrario enviado por el cliente.

Esta entrega **prepara identidad y permisos**, no conecta aún AFOCAT al endpoint
V2. El formulario/API del portal rechaza atribuciones externas manuales.
Los conectores actuales siguen apuntando a Laravel. No se migraron contraseñas,
cuentas ni ventas reales; no se alteraron datos o permisos de producción antigua.

Migración `0004_commercial_identity`: mantiene IDs y relaciones existentes,
completa nombres desde las cuentas vinculadas, permite externos sin cuenta y
agrega unicidad de identidad por origen. Los orígenes previos distintos de
ABISSOL se clasifican como entidad asociada para revisión, sin asumir una AFOCAT.
