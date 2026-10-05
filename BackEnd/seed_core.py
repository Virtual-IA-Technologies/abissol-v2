"""Inicializa la plataforma y una cuenta; repetir no restablece permisos ni claves."""
import getpass
import os
from app.database import SessionLocal
from app.bootstrap import seed_platform
from app.models import AuditLog, Usuario
from app.routes.auth import hash_password, validate_password


def main():
    email = (os.getenv("INITIAL_ADMIN_EMAIL") or input("Correo del administrador inicial: ")).strip().lower()
    from email_validator import validate_email
    email = validate_email(email, check_deliverability=False).normalized
    with SessionLocal() as db:
        roles = seed_platform(db)
        if not db.query(Usuario.id).filter_by(correo=email).first():
            password = os.getenv("INITIAL_ADMIN_PASSWORD") or getpass.getpass("Contraseña inicial (no se muestra): ")
            validate_password(password)
            user = Usuario(nombre="Administrador", apellido="ABISSOL", username="administrador",
                           correo=email, contrasena=hash_password(password), requiere_cambio_clave=True,
                           is_active=True, roles=[roles["Programador"]])
            db.add(user)
            db.flush()
            db.add(AuditLog(usuario_id=user.id, actor_usuario_id=user.id, accion="instalar",
                           entidad="sistema", modulo="core", detalle="Plataforma ABISSOL inicializada"))
        db.commit()
    from app.services.documentation import sync_repository
    with SessionLocal() as db:
        count = sync_repository(db)
    print(f"Plataforma lista; {count} documentos sincronizados. No se alteraron cuentas existentes.")


if __name__ == "__main__":
    main()