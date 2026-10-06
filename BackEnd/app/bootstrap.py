"""Catálogo inicial independiente; nunca importa datos del proyecto de origen."""
from sqlalchemy.orm import Session
from .models import AccessGrant, Menu, Rol

MENUS = [
    ("inicio", "Panel principal", "/inicio", "menu", None, "LayoutDashboard"),
    ("medical", "Negocio ABISSOL", None, "modulo", None, "HeartPulse"),
    ("medical-plans", "Planes de asistencia", "/plataforma/medical/plans", "menu", "medical", "HeartPulse"),
    ("medical-network", "Red comercial", "/plataforma/medical/network", "menu", "medical", "Users"),
    ("medical-emissions", "Emisiones", "/plataforma/medical/emissions", "menu", "medical", "FileText"),
    ("medical-dispatches", "Comunicaciones", "/plataforma/medical/dispatches", "menu", "medical", "Send"),
    ("medical-liquidations", "Liquidaciones", "/plataforma/medical/liquidations", "menu", "medical", "Wallet"),
    ("medical-billing", "Facturación", "/plataforma/medical/billing", "menu", "medical", "Receipt"),
    ("medical-reports", "Reportes comerciales", "/plataforma/medical/reports", "menu", "medical", "ChartNoAxesCombined"),
    ("plataforma", "Plataforma", None, "modulo", None, "Settings"),
    ("usuarios-seguridad", "Usuarios y seguridad", None, "menu", "plataforma", "Shield"),
    ("usuarios", "Usuarios", "/plataforma/administracion/usuarios", "submenu", "usuarios-seguridad", "Users"),
    ("roles", "Roles", "/plataforma/administracion/roles", "submenu", "usuarios-seguridad", "Contact"),
    ("accesos", "Accesos", "/plataforma/administracion/accesos", "submenu", "usuarios-seguridad", "KeyRound"),
    ("sistema", "Sistema", None, "menu", "plataforma", "Monitor"),
    ("menus", "Menús", "/plataforma/sistema/menus", "submenu", "sistema", "ListTree"),
    ("auditoria", "Auditoría", "/plataforma/sistema/auditoria", "submenu", "sistema", "History"),
    ("calendario", "Calendario", "/plataforma/sistema/calendario", "submenu", "sistema", "Calendar"),
    ("notificaciones", "Notificaciones", "/plataforma/sistema/notificaciones", "submenu", "sistema", "Bell"),
    ("documentacion", "Documentación", "/plataforma/sistema/documentacion", "submenu", "sistema", "BookOpen"),
    ("devops", "DevOps", "/plataforma/sistema/devops", "submenu", "sistema", "Terminal"),
    ("configuracion", "Configuración", "/plataforma/sistema/configuracion", "menu", "plataforma", "SlidersHorizontal"),
    ("general", "Preferencias personales", "/plataforma/sistema/configuracion/general", "pestana", "configuracion", "UserRound"),
    ("apariencia", "Apariencia", "/plataforma/sistema/configuracion/apariencia", "pestana", "configuracion", "Palette"),
    ("smtp", "Correo SMTP", "/plataforma/sistema/configuracion/smtp", "pestana", "configuracion", "Mail"),
    ("whatsapp", "WhatsApp", "/plataforma/sistema/configuracion/whatsapp", "pestana", "configuracion", "MessageCircle"),
    ("plantillas", "Plantillas", "/plataforma/sistema/configuracion/plantillas", "pestana", "configuracion", "FileText"),
    ("automatizacion", "Automatización", None, "menu", "plataforma", "Workflow"),
    ("avi-configuracion", "Asistente", "/plataforma/automatizacion/avi", "submenu", "automatizacion", "Bot"),
    ("modulo-documentos", "Documentos", None, "modulo", None, "FolderOpen"),
    ("documentos", "Archivos", "/documentos/archivos", "menu", "modulo-documentos", "Files"),
]

def seed_platform(db: Session):
    roles = {}
    for name, priority, superuser, default in [
        ("Programador", 0, True, False), ("Administrador", 1, False, False),
        ("Usuario", 100, False, True),
    ]:
        role = db.query(Rol).filter_by(nombre=name).first()
        if role is None:
            role = Rol(nombre=name, prioridad=priority, es_superusuario=superuser,
                       is_default=default, is_active=True)
            db.add(role)
            db.flush()
        roles[name] = role
    menus = {}
    for order, (slug, name, route, kind, parent, icon) in enumerate(MENUS):
        menu = db.query(Menu).filter_by(slug=slug).first()
        if menu is None:
            menu = Menu(slug=slug, nombre=name, ruta=route, tipo=kind, icono=icon,
                        parent_id=menus[parent].id if parent else None, orden=order,
                        is_visible=True, is_active=True)
            db.add(menu)
            db.flush()
            if slug != "devops":
                db.add(AccessGrant(role_id=roles["Administrador"].id,
                                   menu_id=menu.id, access_level="gestor"))
            if slug in {"inicio", "plataforma", "sistema", "calendario", "notificaciones",
                        "documentacion", "modulo-documentos", "documentos", "configuracion", "general"}:
                db.add(AccessGrant(role_id=roles["Usuario"].id, menu_id=menu.id,
                                   access_level="editor" if slug in {"calendario", "documentos", "general"} else "lector"))
        menus[slug] = menu
    db.flush()
    from .models.medical import MedicalPlan, MedicalSource
    for code, name, prefix, price, cost, commission in [
        ("HAMPI-ESENCIAL", "Hampi Esencial", "HE", 55, 12, 15),
        ("HAMPI-PLUS", "Hampi Plus", "HP", 255, 199, 25),
    ]:
        if not db.query(MedicalPlan.id).filter(MedicalPlan.code.in_([code, code.replace('-', '_')])).first():
            db.add(MedicalPlan(code=code, name=name, prefix=prefix, price=price,
                provider_cost=cost, seller_commission=commission, platform_fee=0, validity_days=365))
    if not db.query(MedicalSource.id).filter_by(code="ABISSOL").first():
        db.add(MedicalSource(code="ABISSOL", name="ABISSOL"))
    db.flush()
    from .services.commercial_roles import seed_commercial_roles
    seed_commercial_roles(db)
    return roles
