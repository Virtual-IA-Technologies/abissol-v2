import unittest
import test_platform as platform
from app.bootstrap import MENUS
from app.models import AccessGrant, Menu, Usuario
from app.services.access_control import access_by_slug, effective_menu_tree
from app.schemas.wolverine import MenuWrite


class MenuRouteTests(unittest.TestCase):
    setUp = platform.PlatformTests.setUp
    cleanup = platform.PlatformTests.cleanup
    login = platform.PlatformTests.login

    def test_integrated_tabs_keep_permissions_and_navigation(self):
        with self.sessions() as db:
            reader = db.query(Usuario).filter_by(username="reader").one()
            for slug in ("medical-plans", "medical-dispatches", "smtp", "whatsapp"):
                self.assertFalse(db.query(Menu).filter_by(slug=slug).one().is_visible)
            menu = db.query(Menu).filter_by(slug="medical-plans").one()
            db.add(AccessGrant(usuario_id=reader.id, menu_id=menu.id, access_level="lector"))
            db.commit()
            def slugs(nodes):
                return [slug for node in nodes for slug in [node["slug"], *slugs(node["children"])]]
            self.assertIn("medical-emissions", slugs(effective_menu_tree(db, reader)))
            self.assertNotIn("medical-plans", slugs(effective_menu_tree(db, reader)))
            self.assertEqual(access_by_slug(db, reader).get("medical-emissions", "none"), "none")
        _, headers = self.login("reader")
        self.assertEqual(self.client.get(platform.API + "/medical/plans", headers=headers).status_code, 200)
        self.assertEqual(self.client.get(platform.API + "/medical/emissions", headers=headers).status_code, 403)

    def test_rename_and_move_preserve_implemented_routes(self):
        _, headers = self.login()
        with self.sessions() as db:
            module = db.query(Menu).filter_by(slug="medical").one()
            ident = module.id
            payload = MenuWrite.model_validate(module, from_attributes=True).model_dump()
            payload.update(nombre="PROGRAMAS")
        response = self.client.put(platform.API + f"/admin/menus/{ident}", headers=headers, json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        changed_slug = {**payload, "slug": "programas"}
        self.assertEqual(self.client.put(platform.API + f"/admin/menus/{ident}", headers=headers, json=changed_slug).status_code, 409)
        response = self.client.patch(platform.API + f"/admin/menus/{ident}/move", headers=headers, json={"parent_id": None, "position": 1})
        self.assertEqual(response.status_code, 200, response.text)
        with self.sessions() as db:
            self.assertEqual(db.get(Menu, ident).nombre, "PROGRAMAS")
            for slug, _, route, _, _, _ in MENUS:
                if route:
                    self.assertEqual(db.query(Menu).filter_by(slug=slug).one().ruta, route)
            child = db.query(Menu).filter_by(slug="medical-plans").one()
            child_id = child.id
            edit = MenuWrite.model_validate(child, from_attributes=True).model_dump()
        edit.update(nombre="Planes comerciales", slug="planes-renombrados")
        response = self.client.put(platform.API + f"/admin/menus/{child_id}", headers=headers, json=edit)
        self.assertEqual(response.status_code, 409)
        edit["slug"] = "medical-plans"
        response = self.client.put(platform.API + f"/admin/menus/{child_id}", headers=headers, json=edit)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["ruta"], "/plataforma/medical/plans")
