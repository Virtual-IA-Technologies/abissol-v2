"""META daily/monthly spreadsheet contracts; values never become Excel formulas."""
import json
import re
from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED


def meta_xlsx(emissions, db=None, *, monthly=False):
    originals = {}
    if db is not None:
        from ..models.legacy import LegacyRecord
        from ..utils.secrets import decrypt_secret
        keys = [str(e.legacy_id) for e in emissions if e.legacy_id]
        for record in db.query(LegacyRecord).filter(LegacyRecord.source_table == "medical_issuances", LegacyRecord.source_key.in_(keys)):
            originals[record.source_key] = json.loads(decrypt_secret(record.payload_encrypted))
    headers = ["Apellidos y Nombres", "Tipo de Documento", "N° de Documento", "Teléfono de Contacto", "Correo Electrónico", "Producto", "Fecha de Inicio", "N° de Operación AFOCAT"] if monthly else ["Código", "Plan", "DNI asociado", "Nombre", "Paterno", "Materno", "Emisión", "Inicio", "Fin", "Teléfono", "Correo"]
    rows = [headers]
    for e in emissions:
        original = originals.get(str(e.legacy_id), {})
        name = original.get("contractor_name") or e.customer
        paternal = original.get("contractor_paternal_last_name") or ""
        maternal = original.get("contractor_maternal_last_name") or ""
        surnames = (paternal + " " + maternal).strip() or original.get("contractor_last_name") or ""
        if monthly:
            product = "PLUS" if "PLUS" in e.plan_name.upper() else "ESENCIAL" if "ESENCIAL" in e.plan_name.upper() else ""
            rows.append([(surnames + " " + name).strip(), e.document_type, e.document_number, e.phone, e.email.lower(), product, e.starts_on.strftime("%d/%m/%Y"), e.code])
        else:
            rows.append([e.code, e.plan_name, e.document_number, name, paternal, maternal, e.created_at.strftime("%d/%m/%Y %H:%M"), e.starts_on.strftime("%d/%m/%Y"), e.ends_on.strftime("%d/%m/%Y"), e.phone, e.email])
    content = []
    for number, values in enumerate(rows, 1):
        clean = lambda value: escape(re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value or "")))
        cells = ''.join(f'<c r="{chr(65+i)}{number}" t="inlineStr"><is><t xml:space="preserve">{clean(value)}</t></is></c>' for i, value in enumerate(values))
        content.append(f'<row r="{number}">{cells}</row>')
    result = BytesIO()
    with ZipFile(result, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        archive.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Altas HAMPI" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr('xl/worksheets/sheet1.xml', f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="{len(headers)}" width="26" customWidth="1"/></cols><sheetData>' + ''.join(content) + f'</sheetData><autoFilter ref="A1:{chr(64+len(headers))}{len(rows)}"/></worksheet>')
    return result.getvalue()
