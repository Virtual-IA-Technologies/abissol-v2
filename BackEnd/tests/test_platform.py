"""Contrato de la base limpia: sin datos reales ni servicios externos."""
import os
import secrets
import unittest
from unittest.mock import patch

os.environ.setdefault("DB_NAME", "abissol_v2_local")
os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("SECRET_KEY", secrets.token_urlsafe(48))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database import Base, get_db
from app.bootstrap import MENUS, seed_platform
from app.models import AccessGrant, Menu, Usuario
from app.routes.auth import hash_password

API = "/abissol/api/v1"

class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        event.listen(self.engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.password = "Test-" + secrets.token_urlsafe(20) + "Aa1"
        with self.sessions() as db:
            roles = seed_platform(db)
            for username, role in [("admin", "Programador"), ("reader", "Usuario")]:
                db.add(Usuario(nombre=username, apellido="Prueba", username=username,
                               correo=f"{username}@example.com", contrasena=hash_password(self.password),
                               requiere_cambio_clave=False, is_active=True, roles=[roles[role]]))
            db.commit()
        def dependency():
            with self.sessions() as db:
                yield db
        app.dependency_overrides[get_db] = dependency
        self.audit_patch = patch("app.observability.SessionLocal", self.sessions)
        self.audit_patch.start()
        self.client = TestClient(app)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.client.close()
        app.dependency_overrides.clear()
        self.audit_patch.stop()
        self.engine.dispose()

    def login(self, user="admin"):
        response = self.client.post(API + "/login", json={"identificador": user, "contrasena": self.password})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json(), {"Authorization": "Bearer " + response.json()["access_token"]}

    def test_schema_and_routes_have_no_source_business_modules(self):
        forbidden = ("em_", "sin_", "cpe_", "accounting", "cat_", "alp_", "mtc_", "abissol_sales")
        self.assertFalse([name for name in Base.metadata.tables if name.startswith(forbidden)])
        for path in app.openapi()["paths"]:
            self.assertFalse(any(word in path for word in ("/emisiones", "/siniestros", "/contabilidad", "/mtc", "/liquidaciones", "/vencimientos/cat")), path)
        self.assertEqual(self.client.get("/health/live").status_code, 200)

    def test_seed_is_idempotent_and_preserves_permissions(self):
        with self.sessions() as db:
            grant = db.query(AccessGrant).first()
            grant.access_level = "lector"
            db.commit()
            counts = (db.query(Menu).count(), db.query(AccessGrant).count())
            seed_platform(db)
            db.commit()
            self.assertEqual(counts, (db.query(Menu).count(), db.query(AccessGrant).count()))
            self.assertEqual(grant.access_level, "lector")
            self.assertEqual(counts[0], len(MENUS))

    def test_login_refresh_logout(self):
        session, headers = self.login()
        self.assertIn("abissol_device_session", self.client.cookies)
        self.assertEqual(self.client.get(API + "/me", headers=headers).status_code, 200)
        self.assertEqual(self.client.post(API + "/refresh-session").status_code, 200)
        self.assertEqual(self.client.post(API + "/logout-session", headers=headers).status_code, 204)
        self.assertEqual(self.client.get(API + "/me", headers=headers).status_code, 401)

    def test_platform_pages_api(self):
        _, headers = self.login()
        for path in ("/ui-settings", "/usuarios", "/roles", "/menus", "/calendario/eventos",
                     "/notificaciones", "/documentacion", "/documentos", "/panel-principal/metricas",
                     "/admin/menus", "/access-grants", "/smtp-settings", "/whatsapp-settings",
                     "/message-templates", "/avi-settings", "/avi/contexto", "/avi/hilo",
                     "/auditoria", "/auditoria/estadisticas", "/devops/logs", "/devops/progress",
                     "/calendario/etiquetas", "/calendario/personas", "/calendario/notificaciones",
                     "/notificaciones/reglas", "/notificaciones/tipos", "/documentos/carpetas",
                     "/documentos/almacenamiento", "/documentos/papelera/configuracion"):
            with self.subTest(path=path):
                response = self.client.get(API + path, headers=headers)
                self.assertEqual(response.status_code, 200, response.text)

    def test_reader_cannot_manage_users(self):
        _, headers = self.login("reader")
        self.assertEqual(self.client.get(API + "/usuarios", headers=headers).status_code, 403)
        self.assertEqual(self.client.get(API + "/calendario/eventos", headers=headers).status_code, 200)

    def test_cross_site_login_is_rejected(self):
        response = self.client.post(API + "/login", json={"identificador": "admin", "contrasena": self.password},
                                    headers={"Origin": "https://untrusted.example"})
        self.assertEqual(response.status_code, 403)

    def test_deployment_is_disabled(self):
        _, headers = self.login()
        with patch.dict(os.environ, {"DEVOPS_PUBLISH_ENABLED": "false"}):
            response = self.client.post(API + "/devops/publish", json={"target": "both"}, headers=headers)
        self.assertEqual(response.status_code, 409)

    def test_initializer_creates_account_and_documentation_once(self):
        import seed_core
        from app.models.documentation import DocArticle
        with patch.object(seed_core, "SessionLocal", self.sessions), patch.dict(os.environ, {
            "INITIAL_ADMIN_EMAIL": "initial@example.com", "INITIAL_ADMIN_PASSWORD": self.password,
        }):
            seed_core.main()
            seed_core.main()
        with self.sessions() as db:
            users = db.query(Usuario).filter_by(correo="initial@example.com").all()
            self.assertEqual(len(users), 1)
            self.assertTrue(users[0].requiere_cambio_clave)
            self.assertTrue(any(role.es_superusuario for role in users[0].roles))
            self.assertGreater(db.query(DocArticle).count(), 0)

if __name__ == "__main__":
    unittest.main()
