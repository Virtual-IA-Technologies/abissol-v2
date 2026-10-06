"""UBL 2.1 / SOAP SUNAT. No network request is made while building or signing."""
import base64
import hashlib
import io
import re
import zipfile
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from lxml import etree as E

NS = {None: 'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2',
      'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
      'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
      'ext': 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2',
      'ds': 'http://www.w3.org/2000/09/xmldsig#'}
DS = NS['ds']
C14N = 'http://www.w3.org/TR/2001/REC-xml-c14n-20010315'
SOAP = 'http://schemas.xmlsoap.org/soap/envelope/'
SERVICE = 'http://service.sunat.gob.pe'
WSSE = 'http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd'
ENDPOINTS = {
    'beta': 'https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService',
    'production': 'https://e-factura.sunat.gob.pe/ol-ti-itcpfegem/billService',
}
CDR_ENDPOINT = 'https://e-factura.sunat.gob.pe/ol-it-wsconscpegem/billConsultService'


class FiscalError(ValueError):
    """Safe, operator-facing message; never include raw SOAP or credentials."""


def money(value):
    return Decimal(str(value)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


def amount_words(total):
    # Only the two reconciled ABISSOL plan totals can enter this fiscal flow.
    words = {Decimal('55.00'):'CINCUENTA Y CINCO',Decimal('255.00'):'DOSCIENTOS CINCUENTA Y CINCO'}
    if money(total) not in words:
        raise FiscalError('Importe sin distribución fiscal validada.')
    return words[money(total)]+' CON 00/100 SOLES'


def plan_items(plan_name, total):
    """Exact distribution of the existing ABISSOL plans, not commissions."""
    name = plan_name.upper()
    if 'PLUS' in name:
        amounts = [('Recaudación Meta Assistance', '199'), ('Cuota de admisión asociado', '43'), ('Aporte anual mantenimiento asociado', '13')]
    elif 'ESENCIAL' in name:
        amounts = [('Recaudación Meta Assistance', '12'), ('Cuota de admisión asociado', '43')]
    else:
        raise FiscalError('El plan no tiene una distribución fiscal validada.')
    if sum(money(value) for _, value in amounts) != money(total):
        raise FiscalError('El precio del plan no coincide con su distribución fiscal. Revisar antes de facturar.')
    return [dict(description=description, quantity=1, unit_code='ZZ', unit_value=str(money(amount)),
                 subtotal=str(money(amount)), tax_amount='0.00', total=str(money(amount)), affectation_igv_type='30')
            for description, amount in amounts]


def node(parent, name, text=None, **attrs):
    prefix, local = name.split(':')
    child = E.SubElement(parent, E.QName(NS[prefix], local), **attrs)
    if text is not None:
        child.text = str(text)
    return child


def read_certificate(content, password):
    try:
        key, cert, _ = pkcs12.load_key_and_certificates(content, (password or '').encode() or None)
    except (ValueError, TypeError) as exc:
        raise FiscalError('No se puede abrir el certificado PFX. Revisa su contraseña.') from exc
    if not isinstance(key, rsa.RSAPrivateKey) or cert is None:
        raise FiscalError('El certificado debe contener certificado y clave privada RSA.')
    now = datetime.now(timezone.utc)
    if not cert.not_valid_before_utc <= now <= cert.not_valid_after_utc:
        raise FiscalError('El certificado digital no está vigente.')
    if key.public_key().public_numbers() != cert.public_key().public_numbers():
        raise FiscalError('El certificado no corresponde a su clave privada.')
    return key, cert


def build_invoice(config, invoice, items):
    root = E.Element(E.QName(NS[None], 'Invoice'), nsmap=NS)
    node(node(node(root, 'ext:UBLExtensions'), 'ext:UBLExtension'), 'ext:ExtensionContent')
    node(root, 'cbc:UBLVersionID', '2.1')
    node(root, 'cbc:CustomizationID', '2.0', schemeAgencyName='PE:SUNAT')
    node(root, 'cbc:ProfileID', '0101', schemeName='Tipo de Operacion', schemeAgencyName='PE:SUNAT', schemeURI='urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo51')
    node(root, 'cbc:ID', invoice.full_number)
    node(root, 'cbc:IssueDate', invoice.issue_date.isoformat())
    node(root, 'cbc:IssueTime', invoice.details.get('issue_time','00:00:00'))
    node(root, 'cbc:InvoiceTypeCode', '03', listID='0101', listAgencyName='PE:SUNAT', listName='Tipo de Documento', listURI='urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo01')
    node(root, 'cbc:Note', amount_words(invoice.total), languageLocaleID='1000')
    node(root, 'cbc:DocumentCurrencyCode', 'PEN', listID='ISO 4217 Alpha', listAgencyName='United Nations Economic Commission for Europe', listName='Currency')
    signature = node(root, 'cac:Signature')
    node(signature, 'cbc:ID', config['ruc'])
    party = node(signature, 'cac:SignatoryParty')
    node(node(party, 'cac:PartyIdentification'), 'cbc:ID', config['ruc'])
    node(node(party, 'cac:PartyName'), 'cbc:Name', config['company_name'])
    node(node(node(signature, 'cac:DigitalSignatureAttachment'), 'cac:ExternalReference'), 'cbc:URI', '#SignatureSP')
    party = node(node(root, 'cac:AccountingSupplierParty'), 'cac:Party')
    node(node(party, 'cac:PartyIdentification'), 'cbc:ID', config['ruc'], schemeID='6', schemeName='Documento de Identidad', schemeAgencyName='PE:SUNAT')
    node(node(party, 'cac:PartyName'), 'cbc:Name', config.get('trade_name') or config['company_name'])
    legal = node(party, 'cac:PartyLegalEntity')
    node(legal, 'cbc:RegistrationName', config['company_name'])
    address = node(legal, 'cac:RegistrationAddress')
    for field, value in [('ID',config['ubigeo']),('AddressTypeCode',config.get('sunat_address_type_code') or '0000'),('CityName',config['province']),('CountrySubentity',config['department']),('District',config['district'])]:
        node(address, 'cbc:'+field, value)
    node(node(address, 'cac:AddressLine'), 'cbc:Line', config['address'])
    node(node(address, 'cac:Country'), 'cbc:IdentificationCode', 'PE')
    party = node(node(root, 'cac:AccountingCustomerParty'), 'cac:Party')
    doc_type = {'DNI':'1','CE':'4','PASSPORT':'7'}[invoice.details['customer_document_type']]
    node(node(party, 'cac:PartyIdentification'), 'cbc:ID', invoice.document_number, schemeID=doc_type, schemeName='Documento de Identidad', schemeAgencyName='PE:SUNAT')
    node(node(party, 'cac:PartyLegalEntity'), 'cbc:RegistrationName', invoice.customer)
    if getattr(invoice, 'payment_status', 'paid') == 'paid':
        terms = node(root, 'cac:PaymentTerms')
        node(terms, 'cbc:ID', 'FormaPago')
        node(terms, 'cbc:PaymentMeansID', 'Contado')
    tax_total(root, invoice.total)
    legal = node(root, 'cac:LegalMonetaryTotal')
    for field in ('LineExtensionAmount','TaxInclusiveAmount','PayableAmount'):
        node(legal, 'cbc:'+field, str(money(invoice.total)), currencyID='PEN')
    for index, item in enumerate(items, 1):
        line = node(root, 'cac:InvoiceLine')
        node(line, 'cbc:ID', index)
        node(line, 'cbc:InvoicedQuantity', '1', unitCode='ZZ')
        node(line, 'cbc:LineExtensionAmount', item['subtotal'], currencyID='PEN')
        price = node(node(line, 'cac:PricingReference'), 'cac:AlternativeConditionPrice')
        node(price, 'cbc:PriceAmount', item['total'], currencyID='PEN')
        node(price, 'cbc:PriceTypeCode', '01')
        tax_total(line, item['subtotal'], line=True)
        node(node(line, 'cac:Item'), 'cbc:Description', item['description'])
        node(node(line, 'cac:Price'), 'cbc:PriceAmount', item['unit_value'], currencyID='PEN')
    return root


def tax_total(parent, amount, line=False):
    total = node(parent, 'cac:TaxTotal')
    node(total, 'cbc:TaxAmount', '0.00', currencyID='PEN')
    subtotal = node(total, 'cac:TaxSubtotal')
    node(subtotal, 'cbc:TaxableAmount', str(money(amount)), currencyID='PEN')
    node(subtotal, 'cbc:TaxAmount', '0.00', currencyID='PEN')
    category = node(subtotal, 'cac:TaxCategory')
    if line:
        node(category, 'cbc:Percent', '0.00')
        node(category, 'cbc:TaxExemptionReasonCode', '30', listAgencyName='PE:SUNAT', listName='Afectacion del IGV', listURI='urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo07')
    scheme = node(category, 'cac:TaxScheme')
    for key, value in [('ID','9998'),('Name','INA'),('TaxTypeCode','FRE')]:
        node(scheme, 'cbc:'+key, value)


def sign_xml(root, key, cert):
    # SUNAT's existing ABISSOL implementation uses inclusive C14N / RSA-SHA1.
    digest = base64.b64encode(hashlib.sha1(E.tostring(root, method='c14n')).digest()).decode()
    target = root.find('.//{'+NS['ext']+'}ExtensionContent')
    signature = node(target, 'ds:Signature', Id='SignatureSP')
    info = node(signature, 'ds:SignedInfo')
    node(info, 'ds:CanonicalizationMethod', Algorithm=C14N)
    node(info, 'ds:SignatureMethod', Algorithm=DS+'rsa-sha1')
    reference = node(info, 'ds:Reference', URI='')
    node(node(reference, 'ds:Transforms'), 'ds:Transform', Algorithm=DS+'enveloped-signature')
    node(reference, 'ds:DigestMethod', Algorithm=DS+'sha1')
    node(reference, 'ds:DigestValue', digest)
    value = key.sign(E.tostring(info, method='c14n'), padding.PKCS1v15(), hashes.SHA1())
    node(signature, 'ds:SignatureValue', base64.b64encode(value).decode())
    node(node(node(signature, 'ds:KeyInfo'), 'ds:X509Data'), 'ds:X509Certificate', base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode())
    return E.tostring(root, encoding='UTF-8', xml_declaration=True), digest


def package_xml(name, xml):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name+'.xml', xml)
    return output.getvalue()


def parse_xml(content):
    if len(content) > 5_000_000 or b'<!DOCTYPE' in content.upper():
        raise FiscalError('Respuesta XML no permitida.')
    try:
        return E.fromstring(content, parser=E.XMLParser(resolve_entities=False, no_network=True))
    except E.XMLSyntaxError as exc:
        raise FiscalError('Respuesta XML inválida de SUNAT.') from exc


def soap(config, method, fields):
    if config['environment'] not in ENDPOINTS:
        raise FiscalError('Entorno SUNAT inválido.')
    endpoint = CDR_ENDPOINT if method == 'getStatusCdr' and config['environment'] == 'production' else ENDPOINTS[config['environment']]
    root = E.Element(E.QName(SOAP,'Envelope'), nsmap={'soap':SOAP,'ser':SERVICE,'wsse':WSSE})
    security = E.SubElement(E.SubElement(root,E.QName(SOAP,'Header')),E.QName(WSSE,'Security'))
    token = E.SubElement(security,E.QName(WSSE,'UsernameToken'))
    sol_user = config['sol_user']
    E.SubElement(token,E.QName(WSSE,'Username')).text = sol_user if sol_user.startswith(config['ruc']) else config['ruc']+sol_user
    E.SubElement(token,E.QName(WSSE,'Password'),Type='http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-username-token-profile-1.0#PasswordText').text = config['sol_password']
    action = E.SubElement(E.SubElement(root,E.QName(SOAP,'Body')),E.QName(SERVICE,method))
    for name,value in fields.items():
        E.SubElement(action,name).text = value
    response = httpx.post(endpoint, content=E.tostring(root, encoding='UTF-8', xml_declaration=True),
                          headers={'Content-Type':'text/xml; charset=utf-8','SOAPAction':method}, timeout=45, follow_redirects=False)
    parsed = parse_xml(response.content)
    faults = parsed.xpath('//*[local-name()="Fault"]')
    if faults:
        code = ''.join(faults[0].xpath('./*[local-name()="faultcode"]/text()'))
        code = re.sub(r'[^a-zA-Z0-9_.:-]', '', code)[:60]
        raise FiscalError('SUNAT respondió un error SOAP ('+code+'). Consultar CDR antes de reenviar.')
    if response.status_code != 200:
        raise FiscalError('SUNAT no confirmó la recepción. Consultar CDR.')
    return parsed


def send_bill(config, name, content):
    root = soap(config,'sendBill',{'fileName':name+'.zip','contentFile':base64.b64encode(content).decode()})
    result = root.xpath('//*[local-name()="applicationResponse"]/text()')
    if not result:
        raise FiscalError('SUNAT no devolvió CDR. Recepción por confirmar.')
    return base64.b64decode(result[0],validate=True)


def query_cdr(config, full_number):
    series, number = full_number.split('-')
    root = soap(config,'getStatusCdr',{'rucComprobante':config['ruc'],'tipoComprobante':'03','serieComprobante':series,'numeroComprobante':str(int(number))})
    result = root.xpath('//*[local-name()="content"]/text()')
    if not result:
        raise FiscalError('CDR aún no disponible. No se reenviará el comprobante automáticamente.')
    return base64.b64decode(result[0],validate=True)


def cdr_result(content, expected_number, expected_ruc):
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = [entry for entry in archive.infolist() if entry.filename.lower().endswith('.xml')]
            if len(entries) != 1 or entries[0].file_size > 2_000_000:
                raise FiscalError('CDR con contenido inesperado.')
            root = parse_xml(archive.read(entries[0]))
    except (zipfile.BadZipFile, RuntimeError) as exc:
        raise FiscalError('SUNAT devolvió un CDR inválido.') from exc
    values = lambda path: root.xpath(path, namespaces={k:v for k,v in NS.items() if k})
    reference = values('//cac:DocumentResponse/cac:DocumentReference/cbc:ID/text()')
    receiver = values('//cac:ReceiverParty/cac:PartyIdentification/cbc:ID/text()')
    code = values('//cac:DocumentResponse/cac:Response/cbc:ResponseCode/text()')
    if reference != [expected_number] or receiver != [expected_ruc] or len(code) != 1 or not code[0].isdigit():
        raise FiscalError('El CDR no corresponde al emisor y comprobante enviado.')
    description = values('//cac:DocumentResponse/cac:Response/cbc:Description/text()')
    return {'code':code[0], 'status':'accepted' if code[0]=='0' else 'rejected',
            'message':' '.join(description)[:500], 'notes':values('//cbc:Note/text()')[:20]}
