# Impersonación — 12/10/2026

La base ya incluía `POST /impersonation/start/{id}` y `/impersonation/leave`, tabla de sesiones, identidad de actor/usuario efectivo y auditoría HTTP. Se reutilizan; no se agregan tablas ni permisos equivalentes a Programador para vendedores.

Usuarios incorpora el botón visible **Impersonar usuario** y un panel lateral con selector buscable por nombre, usuario o correo. Se conserva la acción contextual de cada fila. La entrada dirige a Inicio con los permisos reales del destinatario. El aviso superior ofrece **Volver a mi usuario**.

Solo Programador puede entrar como otra cuenta activa que no sea Programador. Se rechazan impersonaciones anidadas. No se necesitan ni se cambian contraseñas. Si el actor o destinatario tiene cambio obligatorio de clave pendiente, se rechaza el inicio: el usuario debe completar su cambio primero, evitando quedar encerrado en la pantalla de contraseña durante la impersonación.

La sesión guarda actor, destino, dispositivo, inicio y final; las acciones conservan identidad real y efectiva en auditoría. Los cambios hechos durante la impersonación son operaciones reales, no una simulación de solo lectura.

Prueba aislada `test_impersonation`: entrada, permisos efectivos sin acceso a Usuarios, rechazo de anidación, retorno a Programador, sesión cerrada, auditoría asociada y bloqueo por contraseña pendiente. Sin modificar cuentas reales ni enviar mensajes.

Verificación local completada: prueba aprobada, TypeScript y ESLint sin errores, compilación Vite correcta. Publicación autorizada en main y V2.

El gateway histórico pendiente de autorización en el workspace es un trabajo separado: no incluirlo inadvertidamente en la publicación de impersonación.
