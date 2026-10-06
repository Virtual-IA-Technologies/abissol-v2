"""Importación transaccional desde una instantánea Laravel, sin llamadas externas.

Los datos personales y los hashes nunca se escriben en logs. Los registros
originales se conservan cifrados para conciliar campos sin equivalente en V2.
Una segunda ejecución verifica la instantánea y no sobreescribe operación V2.
"""
import hashlib
import json
import os
import shutil
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from ..models import Usuario, UsuarioRol, Rol, Document, DocumentFolder, DocumentVersion, DocumentShare
from ..models.legacy import LegacyRecord, LegacyFile, MedicalBillingConfiguration
from ..models.medical import (MedicalPlan as Plan, MedicalSource as Source, MedicalProfile as Profile,
    MedicalIssuance as Issuance, MedicalLiquidation as Liquidation, MedicalLiquidationItem as Item,
    MedicalVoucher as Voucher, MedicalInvoice as Invoice, MedicalDispatch as Dispatch)
from ..utils.secrets import encrypt_secret
from .commercial_roles import seed_commercial_roles


def packed(value):
    return json.dumps(value, default=str, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def day(value):
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def money(value):
    return Decimal(str(value or 0)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


class ImportFailure(RuntimeError):
    """Mensaje sin valores personales ni credenciales."""


class Importer:
    def __init__(self, db, data, source_root, storage_root, operator_id, copy_files=False):
        self.db, self.data = db, data
        self.source_root, self.storage = Path(source_root).resolve(), Path(storage_root).resolve()
        self.operator_id, self.copy_files = operator_id, copy_files
        self.maps = defaultdict(dict)
        self.records = {(r.source_table, r.source_key): r for r in db.query(LegacyRecord)}
        self.files = {r.path_hash: r for r in db.query(LegacyFile)}
        self.missing_files = set()
        self.report = {'source_counts': {t: len(rows) for t, rows in data.items()}, 'new_records': 0,
                       'linked_existing_users': 0, 'shared_contact_phones': 0}

    def private_permissions(self, path):
        path.parent.chmod(0o750)
        path.chmod(0o640)
        if os.name == 'posix' and os.geteuid() == 0:
            owner = self.storage.stat()
            os.chown(path.parent, owner.st_uid, owner.st_gid)
            os.chown(path, owner.st_uid, owner.st_gid)

    def archive(self, table, row):
        key = str(row['id']) if 'id' in row else digest(packed(row))
        raw = packed(row)
        existing = self.records.get((table, key))
        if existing:
            if existing.checksum != digest(raw):
                raise ImportFailure(f'La instantánea cambió: {table} ({key}); conciliar antes de reimportar.')
            return existing
        record = LegacyRecord(source_table=table, source_key=key, checksum=digest(raw), payload_encrypted=encrypt_secret(raw))
        self.db.add(record)
        self.records[table, key] = record
        self.report['new_records'] += 1
        return record

    def put(self, table, row, model, values, existing=None):
        record = self.archive(table, row)
        if record.target_id is not None:
            obj = self.db.get(model, record.target_id)
            if obj is None:
                raise ImportFailure(f'Destino ausente: {table} ({row["id"]})')
        else:
            obj = existing or model(**values)
            if existing:
                for key, value in values.items():
                    setattr(obj, key, value)
            self.db.add(obj)
            self.db.flush()
            record.target_id = obj.id
        self.maps[table][row['id']] = obj
        return obj

    def ref(self, table, key, optional=False):
        if key is None and optional:
            return None
        obj = self.maps[table].get(key)
        if obj is None:
            raise ImportFailure(f'Referencia sin correspondencia: {table} ({key})')
        return obj.id

    def author(self, key):
        return self.ref('users', key) if key else self.operator_id

    def copy(self, relative):
        if not relative:
            return None
        text = str(relative).replace('\\', '/')
        h = digest(text)
        if h in self.files:
            return self.files[h]
        roots = [self.source_root / 'storage/app/public', self.source_root / 'storage/app/private',
                 self.source_root / 'storage/app', self.source_root / 'public']
        path = Path(text)
        candidates = [path] if path.is_absolute() else [r / text for r in roots]
        if text.startswith('storage/'):
            candidates += [r / text[8:] for r in roots[:3]]
        source = next((p.resolve() for p in candidates if p.is_file() and any(p.resolve().is_relative_to(r.resolve()) for r in roots)), None)
        if source is None:
            self.missing_files.add(h)
            return None
        content_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        key = f'legacy-{h}'
        result = LegacyFile(path_hash=h, storage_key=key, filename=source.name[:255], sha256=content_hash, size=source.stat().st_size)
        if self.copy_files:
            target = self.storage / 'legacy_abissol' / key
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != content_hash:
                raise ImportFailure('El archivo de destino difiere; no se sobreescribió.')
            if not target.exists():
                shutil.copyfile(source, target)
                target.chmod(0o640)
            if hashlib.sha256(target.read_bytes()).hexdigest() != content_hash:
                raise ImportFailure('Un archivo cambió mientras se copiaba; repetir desde una instantánea estable.')
            self.private_permissions(target)
        self.db.add(result)
        self.db.flush()
        self.files[h] = result
        return result

    def materialize(self, file, folder, key):
        if self.copy_files and file:
            target = self.storage / folder / key
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                shutil.copyfile(self.storage / 'legacy_abissol' / file.storage_key, target)
                target.chmod(0o640)
            self.private_permissions(target)

    def run(self):
        # Se archivan también permisos originales, ajustes y logs, sin convertirlos
        # en autorizaciones equivalentes por suposición.
        for table, rows in self.data.items():
            for row in rows:
                self.archive(table, row)
        self.users()
        self.catalogs()
        self.profiles()
        self.emissions()
        self.liquidations()
        self.invoices()
        self.documents()
        self.dispatches()
        self.configuration()
        self.db.flush()
        for row in self.data.get('documents', []):
            self.copy(row.get('preview_path'))
        self.report.update(files=len(self.files), missing_files=len(self.missing_files),
                           issuance_total=str(sum((money(r['sale_price']) for r in self.data['medical_issuances']), Decimal(0))),
                           invoice_total=str(sum((money(r['total']) for r in self.data['billing_invoices']), Decimal(0))))
        self.verify()
        return self.report

    def verify(self):
        pairs = {'users': Usuario, 'medical_sources': Source, 'medical_plans': Plan, 'medical_sellers': Profile,
                 'medical_issuances': Issuance, 'medical_liquidations': Liquidation, 'medical_liquidation_items': Item,
                 'medical_liquidation_vouchers': Voucher, 'billing_invoices': Invoice, 'medical_dispatches': Dispatch, 'documents': Document}
        for table, model in pairs.items():
            ids = [self.records[table, str(r['id'])].target_id for r in self.data.get(table, [])]
            if len(set(ids)) != len(ids) or (ids and self.db.query(model).filter(model.id.in_(ids)).count() != len(ids)):
                raise ImportFailure(f'No cuadran los registros migrados: {table}')
        for r in self.data['medical_issuances']:
            dest = self.maps['medical_issuances'][r['id']]
            if any(money(getattr(dest, field)) != money(r[source]) for field, source in [('price','sale_price'),('paid_amount','paid_amount'),('provider_cost','provider_cost'),('seller_commission','seller_commission_amount'),('platform_fee','platform_commission_amount')]):
                raise ImportFailure('No cuadran los importes por emisión')
            if dest.code != r['internal_code'] or dest.token != r['public_token']:
                raise ImportFailure('Cambió el certificado o su token original')
        for r in self.data['billing_invoices']:
            dest = self.maps['billing_invoices'][r['id']]
            if money(dest.total) != money(r['total']) or dest.sunat_status != r['sunat_status'] or dest.full_number != r['full_number']:
                raise ImportFailure('No cuadra la información fiscal original')
        for r in self.data['medical_liquidations']:
            dest = self.maps['medical_liquidations'][r['id']]
            if money(dest.deposit_required) != money(r['amount_to_pay']) or money(dest.sales_total) != money(r['sale_total']) or dest.status != r['status']:
                raise ImportFailure('No cuadra la conciliación de liquidaciones')
        self.report['verified'] = True

    def users(self):
        phones = Counter(str(r.get('phone') or '').strip() for r in self.data['users'])
        source_roles = {r['id']: r['name'] for r in self.data['roles']}
        self.user_roles = defaultdict(set)
        for r in self.data.get('model_has_roles', []):
            if r['model_type'].endswith('User'):
                self.user_roles[r['model_id']].add(source_roles[r['role_id']])
        target_roles = {r.nombre: r for r in self.db.query(Rol)}
        for row in self.data['users']:
            record = self.records['users', str(row['id'])]
            if record.target_id:
                self.maps['users'][row['id']] = self.db.get(Usuario, record.target_id)
                continue
            email = (row.get('email') or '').strip() or None
            username = (row.get('username') or '').strip() or f'legacy-{row["id"]}'
            existing = self.db.query(Usuario).filter(Usuario.correo == email).first() if email else None
            name_conflict = self.db.query(Usuario).filter_by(username=username).first()
            if name_conflict and (not existing or name_conflict.id != existing.id):
                raise ImportFailure(f'Conflicto de usuario en origen ({row["id"]}); resolver sin fusionar personas.')
            phone = str(row.get('phone') or '').strip()
            unique_phone = phone if phone and phones[phone] == 1 and len(phone) <= 20 else None
            if unique_phone and self.db.query(Usuario).filter_by(telefono=unique_phone).first():
                unique_phone = None
            if phone and not unique_phone:
                self.report['shared_contact_phones'] += 1
            hashed = str(row['password'])
            if not hashed.startswith(('$2y$', '$2b$', '$2a$')) or len(hashed) != 60:
                raise ImportFailure(f'Hash de acceso incompatible ({row["id"]})')
            if existing:
                # No cambiar la clave, nombre de acceso, estado ni roles ya usados en V2.
                record.target_id = existing.id
                self.maps['users'][row['id']] = existing
                self.report['linked_existing_users'] += 1
                continue
            user = self.put('users', row, Usuario, dict(nombre=row['name'], apellido='', username=username,
                correo=email, telefono=unique_phone, legacy_contact_phone=phone or None,
                contrasena=hashed, fecha_registro=row['created_at'], is_active=True, requiere_cambio_clave=False))
            names = self.user_roles[row['id']]
            roles = {'Usuario'}
            for name in names:
                if name in {'superadmin', 'Programmers', 'programmer', 'devops'}:
                    roles.add('Programador')
                elif name == 'Administrador':
                    roles.add('Administrador')
                elif name not in {'seller', 'branch_seller', 'afocat_admin', 'Vendedor'}:
                    role_name = f'Legado · {name}'[:50]
                    if role_name not in target_roles:
                        target_roles[role_name] = Rol(nombre=role_name, es_superusuario=False, is_default=False, is_active=True)
                        self.db.add(target_roles[role_name]); self.db.flush()
                    roles.add(role_name)
            for name in roles:
                role = target_roles.get(name)
                if role is None:
                    raise ImportFailure(f'Falta rol de plataforma: {name}')
                self.db.add(UsuarioRol(usuario_id=user.id, rol_id=role.id, is_permanent=True, is_active=True))

    def catalogs(self):
        settings = {r['key']: r['value'] for r in self.data.get('medical_settings', [])}
        for r in self.data['medical_sources']:
            existing = self.db.query(Source).filter_by(code=r['code']).first()
            self.put('medical_sources', r, Source, dict(code=r['code'], name=r['name'], kind=r['source_type'],
                external_key=r['external_key'], active=r['status'] == 'active' and not r['deleted_at']), existing)
        for r in self.data['medical_plans']:
            existing = self.db.query(Plan).filter(Plan.code.in_([r['code'], r['code'].replace('_', '-')])).first()
            if existing and ('medical_plans', str(r['id'])) in self.records and not self.records['medical_plans', str(r['id'])].target_id:
                if self.db.query(Issuance.id).filter_by(plan_id=existing.id).first():
                    raise ImportFailure('El plan de plantilla ya tiene ventas V2; requiere conciliar series.')
            commission = settings.get('medical.default_seller_commission_hampi_plus_amount' if 'PLUS' in r['code'] else 'medical.default_seller_commission_hampi_esencial_amount')
            if commission is None:
                raise ImportFailure('Falta comisión comercial predeterminada en origen.')
            self.put('medical_plans', r, Plan, dict(code=r['code'], name=r['name'], prefix=r['series_prefix'], counter=r['current_number'],
                price=r['sale_price'], provider_cost=r['provider_cost'], seller_commission=money(commission),
                platform_fee=money(r['platform_fee']) or money(r['platform_commission']), meta_percent=r['meta_commission_percent'],
                validity_days=r['validity_days'], active=bool(r['is_active'] and not r['deleted_at']), conditions_url=''), existing)
            self.copy(r.get('conditioned_document_path'))

    def profiles(self):
        roles = seed_commercial_roles(self.db)
        new_profiles = set()
        for r in self.data['medical_sellers']:
            if not self.records['medical_sellers', str(r['id'])].target_id:
                new_profiles.add(r['id'])
            user = self.maps['users'][r['user_id']]
            kind = 'source_admin' if 'afocat_admin' in self.user_roles[r['user_id']] else 'emitter' if r['responsible_seller_id'] or r['source_role'] == 'emitter' else 'responsible'
            overrides = {}
            for old_plan in self.data['medical_plans']:
                value = r.get('commission_hampi_plus_amount' if 'PLUS' in old_plan['code'] else 'commission_hampi_esencial_amount')
                if value is not None:
                    overrides[str(self.ref('medical_plans', old_plan['id']))] = str(money(value))
            existing = self.db.query(Profile).filter_by(user_id=user.id).first()
            p = self.put('medical_sellers', r, Profile, dict(user_id=user.id, display_name=user.nombre,
                source_id=self.ref('medical_sources', r['source_id']), external_user_id=str(r['external_user_id']) if r['external_user_id'] is not None else None,
                kind=kind, commission_overrides=overrides, active=r['status'] == 'active' and not r['deleted_at']), existing)
            if r['id'] in new_profiles and p.active and not self.db.get(UsuarioRol, (user.id, roles[kind].id)):
                self.db.add(UsuarioRol(usuario_id=user.id, rol_id=roles[kind].id, is_permanent=True, is_active=True))
        for r in self.data['medical_sellers']:
            p = self.maps['medical_sellers'][r['id']]
            if r['id'] in new_profiles and r['responsible_seller_id']:
                parent = self.maps['medical_sellers'].get(r['responsible_seller_id'])
                if not parent or parent.source_id != p.source_id:
                    raise ImportFailure(f'Responsable comercial inconsistente ({r["id"]})')
                p.manager_id = parent.id
        # Coordinadores sin ficha comercial también deben tener ámbito de origen.
        for r in self.data['users']:
            if 'afocat_admin' not in self.user_roles[r['id']]:
                continue
            user_id = self.ref('users', r['id'])
            if self.db.query(Profile).filter_by(user_id=user_id).first():
                continue
            if not r['medical_source_id']:
                raise ImportFailure('Coordinador sin origen; no se concede ámbito global.')
            self.db.add(Profile(user_id=user_id, display_name=r['name'], source_id=self.ref('medical_sources', r['medical_source_id']), kind='source_admin', active=True))
            self.db.add(UsuarioRol(usuario_id=user_id, rol_id=roles['source_admin'].id, is_permanent=True, is_active=True))

    def emissions(self):
        sellers_by_user = {r['user_id']: r['id'] for r in self.data['medical_sellers']}
        for r in self.data['medical_issuances']:
            plan = self.maps['medical_plans'][r['plan_id']]
            status = {'pending_payment': 'issued', 'active': 'issued', 'issued': 'issued', 'cancelled': 'cancelled'}.get(r['status'])
            if not status or r['deleted_at']:
                raise ImportFailure('Estado de emisión no contemplado; requiere conciliación.')
            surname = ' '.join(x for x in [r['contractor_paternal_last_name'], r['contractor_maternal_last_name']] if x) or (r['contractor_last_name'] or '')
            self.put('medical_issuances', r, Issuance, dict(legacy_id=r['id'], legacy_status=r['status'], code=r['internal_code'], token=r['public_token'],
                plan_id=plan.id, plan_name=plan.name, source_id=self.ref('medical_sources', r['source_id']),
                emitter_id=self.ref('medical_sellers', r['emitter_seller_id'] or sellers_by_user.get(r['emitter_user_id']) or r['seller_id']),
                responsible_id=self.ref('medical_sellers', r['seller_id'] or sellers_by_user.get(r['seller_user_id'])),
                document_type=r['contractor_document_type'], document_number=r['contractor_document_number'],
                customer=(r['contractor_name'] + ' ' + surname).strip(), email=r['contractor_email'] or '', phone=r['contractor_phone'] or '',
                sale_date=day(r['sale_date']), starts_on=day(r['starts_at']), ends_on=day(r['ends_at']), price=r['sale_price'],
                provider_cost=r['provider_cost'], seller_commission=r['seller_commission_amount'], platform_fee=r['platform_commission_amount'],
                meta_commission=money(money(r['provider_cost']) * money(plan.meta_percent) / 100), conditions_url='', status=status,
                payment_status=r['payment_status'], payment_method=r['payment_method'], paid_amount=r['paid_amount'],
                cancellation_reason=r['cancellation_reason'], external_source=r['external_source'], external_reference=r['external_reference'],
                created_by=self.author(r['created_by']), created_at=r['created_at']))
            self.copy(r['welcome_letter_path'])

    def liquidations(self):
        for r in self.data['medical_liquidations']:
            kind = {'seller': 'seller', 'metafin': 'meta', 'platform': 'platform'}.get(r['type'])
            if not kind or r['deleted_at']:
                raise ImportFailure('Liquidación con tipo/estado de borrado no contemplado.')
            self.put('medical_liquidations', r, Liquidation, dict(legacy_id=r['id'], code=r['code'], kind=kind,
                responsible_id=self.ref('medical_sellers', r['seller_id'], optional=True), starts_on=day(r['period_start']),
                ends_on=day(r['period_end']), status=r['status'], sales_total=r['sale_total'],
                commission_total=r['seller_commission_total'] if kind == 'seller' else r['amount_to_pay'], deposit_required=r['amount_to_pay'],
                notes=r['notes'] or '', created_by=self.author(r['created_by']), created_at=r['created_at']))
        for r in self.data['medical_liquidation_items']:
            liq = self.maps['medical_liquidations'][r['liquidation_id']]
            emission_id = self.ref('medical_issuances', r['issuance_id'])
            self.put('medical_liquidation_items', r, Item, dict(liquidation_id=liq.id, issuance_id=emission_id,
                active_key=None if liq.status == 'cancelled' else f'{liq.kind}:{emission_id}', sale=r['sale_price'],
                commission=r['seller_commission_amount'] if liq.kind == 'seller' else r['amount_to_pay'], deposit=r['amount_to_pay']))
        for r in self.data['medical_liquidation_vouchers']:
            liq = self.maps['medical_liquidations'][r['liquidation_id']]
            f = self.copy(r['file_path'])
            key = f'legacy-voucher-{r["id"]}'
            self.materialize(f, 'medical', key)
            reference = r['operation_number'] or f'LEGACY-{r["id"]}'
            self.put('medical_liquidation_vouchers', r, Voucher, dict(liquidation_id=liq.id, reference=reference,
                active_reference=None, amount=r['amount'], paid_on=day(r['deposited_at']), filename=r['original_name'] or r['file_name'],
                storage_key=key, digest=f.sha256 if f else '0' * 64, active_digest=None, active=liq.status != 'cancelled'))

    def invoices(self):
        items = defaultdict(list)
        for r in self.data['billing_invoice_items']:
            items[r['invoice_id']].append({k: v for k, v in r.items() if k not in {'extra_data'}})
        fields = ('invoice_type_code', 'series', 'number', 'currency', 'exchange_rate', 'subtotal', 'tax_amount', 'total_paid', 'balance_due',
                  'customer_address', 'customer_ubigeo', 'due_date', 'affected_invoice_id', 'affected_series', 'affected_number',
                  'credit_note_reason_code', 'credit_note_reason_description', 'debit_note_reason_code', 'debit_note_reason_description',
                  'sunat_response_code', 'sunat_message', 'accepted_at', 'rejected_at', 'hash', 'notes')
        for r in self.data['billing_invoices']:
            details = {k: r.get(k) for k in fields}
            details['items'] = items[r['id']]
            files = {}
            unavailable = []
            for label, field in [('PDF', 'pdf_a4_path'), ('Ticket', 'pdf_ticket_path'), ('XML', 'xml_path'), ('ZIP', 'zip_path'), ('CDR', 'cdr_path')]:
                f = self.copy(r.get(field))
                if f:
                    files[label] = f.id
                elif r.get(field):
                    unavailable.append(label)
            details['files'] = files
            details['unavailable_files'] = unavailable
            self.put('billing_invoices', r, Invoice, dict(legacy_id=r['id'], issuance_id=self.ref('medical_issuances', r['medical_issuance_id'], optional=True),
                document_type=r['invoice_type'], full_number=r['full_number'], issue_date=day(r['issue_date']),
                customer=r['customer_name'], document_number=r['customer_document_number'], total=r['total'], status=r['internal_status'],
                sunat_status=r['sunat_status'], payment_status=r['payment_status'], deleted_at=r['deleted_at'],
                details=json.loads(packed(details)), created_by=self.author(r['created_by']), created_at=r['created_at']))

    def documents(self):
        folders = {}
        for r in self.data.get('documents', []):
            owner = self.author(r['uploaded_by'] or r['created_by'])
            if owner not in folders:
                folder = self.db.query(DocumentFolder).filter_by(owner_id=owner, name='Archivo ABISSOL anterior', parent_id=None).first()
                if not folder:
                    folder = DocumentFolder(owner_id=owner, name='Archivo ABISSOL anterior')
                    self.db.add(folder); self.db.flush()
                folders[owner] = folder.id
            record = self.records['documents', str(r['id'])]
            imported = record.target_id is not None
            doc = self.put('documents', r, Document, dict(owner_id=owner, folder_id=folders[owner], title=(r['title'] or r['original_name'] or f'Documento {r["id"]}')[:180],
                description=(r['description'] or '')[:1000], current_version=int(r['version'] or 1), deleted_at=r['deleted_at'], updated_at=r['updated_at']))
            f = self.copy(r['file_path'])
            if not imported:
                key = f'legacy-document-{r["id"]}'
                self.materialize(f, 'documents', key)
                self.db.add(DocumentVersion(document_id=doc.id, number=doc.current_version, author_id=owner,
                    filename=(r['original_name'] or r['file_name'] or doc.title)[:180], storage_key=key,
                    mime=r['mime_type'] or 'application/octet-stream', size=f.size if f else r['file_size'] or 0,
                    sha256=f.sha256 if f else '0' * 64, reason='Importación ABISSOL Laravel; versión conservada',
                    created_at=r['created_at'], processing='unsupported' if f else 'missing'))
                if owner != self.operator_id:
                    self.db.add(DocumentShare(document_id=doc.id, user_id=self.operator_id))

    def dispatches(self):
        for r in self.data['medical_dispatches']:
            self.put('medical_dispatches', r, Dispatch, dict(legacy_id=r['id'],
                issuance_id=self.ref('medical_issuances', r['issuance_id'], optional=True),
                liquidation_id=self.ref('medical_liquidations', r['liquidation_id'], optional=True), kind=r['type'],
                channel=r['channel'], recipient=(r['recipient_email'] if r['channel'] == 'email' else r['recipient_phone']) or '',
                status=r['status'], attempts=1 if r['sent_at'] else 0, error=(r['error_message'] or '')[:250],
                created_by=self.author(r['created_by']), created_at=r['created_at']))

    def configuration(self):
        for r in self.data.get('billing_invoice_settings', []):
            config = dict(r)
            config['series'] = self.data.get('billing_invoice_series', [])
            config['enabled_in_v2'] = False
            for field in ('logo_path', 'certificate_path'):
                f = self.copy(r.get(field))
                config[field + '_file_id'] = f.id if f else None
            self.put('billing_invoice_settings', r, MedicalBillingConfiguration,
                     dict(payload_encrypted=encrypt_secret(packed(config))))
