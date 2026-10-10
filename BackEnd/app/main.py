from fastapi import FastAPI, Request

from fastapi.middleware.cors import CORSMiddleware

from fastapi.responses import JSONResponse

from sqlalchemy import text

from .config import get_settings

from .database import Base, engine

from .routes import documents
from .routes import medical

from .routes import document_tools

from .routes import document_office

from .routes import document_links

from .routes import document_cloud

from .services.document_cloud_scheduler import lifespan as cloud_lifespan

from .observability import request_context_middleware

from .routes import analytics, audit, auth, calendar, devops, documentation, notifications, roles, search, settings as ui_settings, smart_forms, users, wolverine

settings = get_settings()

if settings.auto_create_schema:
    Base.metadata.create_all(bind=engine)

app = FastAPI(title="ABISSOL API", version=settings.app_version, lifespan=cloud_lifespan)

@app.middleware('http')
async def abissol_security(request: Request, call_next):
    unsafe = request.method not in {"GET", "HEAD", "OPTIONS"}
    origin = request.headers.get("origin")
    fetch_site = request.headers.get("sec-fetch-site", "").lower()
    # Las integraciones sin navegador se autentican por su propia clave; un navegador
    # sí debe proceder de un origen conocido y nunca de un sitio cruzado.
    if unsafe and ((origin and origin not in settings.cors_origins) or fetch_site == "cross-site"):
        return JSONResponse(status_code=403, content={"detail": "Origen no autorizado"})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response

app.middleware("http")(request_context_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "X-Request-ID", "X-Devops-Audit-Key"],
)

@app.get('/')
def root():
    return {"message": "ABISSOL API ready"}

@app.get('/health/live', tags=['Salud'])
def health_live():
    return {"status": "ok", "version": settings.app_version}

@app.get('/health/ready', tags=['Salud'])
def health_ready():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ready", "database": "connected", "version": settings.app_version}

PREFIX = "/abissol/api/v1"

app.include_router(auth.router, prefix=PREFIX, tags=["ABISSOL · Sesiones"])
from .routes import medical_workspaces
from .routes import medical_settlements
from .routes import medical_testing
from .routes import medical_public
from .routes import medical_invoice_delivery
from .routes import medical_delivery
app.include_router(medical_delivery.router, prefix=PREFIX, tags=['ABISSOL · Confirmación al cliente'])
app.include_router(medical_invoice_delivery.router, prefix=PREFIX, tags=['ABISSOL · Envío de comprobantes'])
app.include_router(medical_testing.router, prefix=PREFIX, tags=["ABISSOL test mode"])
app.include_router(medical_public.router, prefix=PREFIX, tags=['ABISSOL · Consulta de membresía'])
app.include_router(medical_public.search_router, prefix=PREFIX, tags=['ABISSOL · Web oficial'])
app.include_router(medical_settlements.router, prefix=PREFIX, tags=['ABISSOL · Conciliación'])
from .routes import medical_integrations
app.include_router(medical_integrations.router, prefix=PREFIX, tags=["ABISSOL · Integración externa"])
app.include_router(medical_workspaces.router, prefix=PREFIX, tags=["ABISSOL · Pestañas comerciales"])
app.include_router(medical.router, prefix=PREFIX, tags=["ABISSOL · Negocio"])

app.include_router(analytics.router, prefix=PREFIX, tags=["ABISSOL · Analítica"])

app.include_router(users.router, prefix=PREFIX, tags=["ABISSOL · Usuarios"])

app.include_router(roles.router, prefix=PREFIX, tags=["ABISSOL · Roles"])

app.include_router(wolverine.router, prefix=PREFIX, tags=["ABISSOL · Accesos"])

app.include_router(audit.router, prefix=PREFIX, tags=["ABISSOL · Auditoría"])

app.include_router(calendar.router, prefix=PREFIX, tags=["ABISSOL · Calendario"])

app.include_router(notifications.router, prefix=PREFIX, tags=["ABISSOL · Notificaciones"])

app.include_router(ui_settings.router, prefix=PREFIX, tags=["ABISSOL · Configuración"])

app.include_router(devops.router, prefix=PREFIX, tags=["DevOps"])

app.include_router(search.router, prefix=PREFIX, tags=["ABISSOL · Búsqueda"])

app.include_router(documentation.router, prefix=PREFIX, tags=["ABISSOL · Documentación"])

app.include_router(document_cloud.router, prefix=PREFIX, tags=["ABISSOL · Cuentas conectadas"])

app.include_router(documents.router, prefix=PREFIX, tags=["ABISSOL · Documentos"])

app.include_router(document_tools.router, prefix=PREFIX, tags=["ABISSOL · Documentos"])

app.include_router(document_office.router, prefix=PREFIX, tags=["ABISSOL · ONLYOFFICE"])

app.include_router(document_links.router, prefix=PREFIX, tags=["ABISSOL · Enlaces documentales"])

app.include_router(smart_forms.router, prefix=PREFIX, tags=["ABISSOL · Formularios inteligentes"])
