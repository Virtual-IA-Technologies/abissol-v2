"""One archived welcome letter for portal, external API, public QR and email."""
from pathlib import Path
from html import escape
from string import Template
from ..models.documents import DocumentVersion
from .medical_documents import binding
from .documents import file_path
from .medical_rendering import template

def archived_file(db,source,ident,key):
    link=binding(db,source,ident,key)
    if not link:return None
    version=db.query(DocumentVersion).filter_by(document_id=link.document_id).order_by(DocumentVersion.number.desc()).first()
    if not version:return None
    path=file_path(version.storage_key)
    if not path.is_file():return None
    return path,version.filename,version.mime

def letter_file(db,row):
    archived=archived_file(db,'emission',row.id,'letter')
    if archived:return archived
    from ..routes import medical as m
    if row.legacy_id:
        result=m.legacy_download(db,m.legacy_data(db,'medical_issuances',row.legacy_id).get('welcome_letter_path'))
        return Path(result.path),row.code+'.pdf','application/pdf'
    return None

def conditions_file(db,row):
    return archived_file(db,'plan',row.plan_id,'conditions')

def welcome_message(db,row,url,*,condition_available=False):
    """Escaped canonical HTML; custom text remains a supported explicit configuration."""
    from .medical_settings import business_settings,insured_message
    letter_url=url+'/letter';condition_url=url+'/conditions' if condition_available else row.conditions_url
    context={key:escape(str(value or '')) for key,value in {'safeName':row.customer,'safePlan':row.plan_name,'startsAt':row.starts_on.strftime('%d/%m/%Y'),'endsAt':row.ends_on.strftime('%d/%m/%Y')}.items()}
    def button(url,label,background,color):
        return f'<a href="{escape(url,quote=True)}" target="_blank" style="display:inline-block;padding:12px 17px;border-radius:10px;background:{background};color:{color};text-decoration:none;font-weight:700;margin:0 8px 8px 0;">{label}</a>' if url.startswith('https://') else ''
    context.update(welcomeLetterButton=button(letter_url,'Descargar carta de bienvenida','#0f6b2e','#ffffff'),conditionedButton=button(condition_url,'Descargar condicionado','#8cc63f','#102a05'),verificationButton=button(url,'Consultar membresía','#0f172a','#ffffff'))
    def direct(link,label):return f'<p style="margin:6px 0 10px;line-height:1.5;color:#475569;font-size:12px;">{label}:<br><a href="{escape(link,quote=True)}" style="color:#0f6b2e;word-break:break-all;">{escape(link)}</a></p>' if link.startswith('https://') else ''
    context['welcome_direct']=direct(letter_url,'Enlace directo de la carta');context['conditions_direct']=direct(condition_url,'Enlace directo del condicionado')
    text=f'Estimado(a) {row.customer},\n\nLe damos la bienvenida como miembro asociado de ABISSOL.\n\nSu membresía en el programa {row.plan_name} ha sido registrada correctamente.\nInicio de membresía: {context["startsAt"]}\nFin de membresía: {context["endsAt"]}\n\nCarta de bienvenida:\n{letter_url}\n\nCondicionado oficial del programa:\n{condition_url or "No disponible"}\n\nConsulta de membresía:\n{url}\n\nLa prestación de los servicios asistenciales es responsabilidad exclusiva de META ASSISTANCE PERÚ S.A.C.; ABISSOL actúa como entidad asociativa que gestiona el acceso de sus miembros al programa.\n\nAtentamente,\nABISSOL\nÁrea de Afiliación y Atención al Asociado'
    html=Template(template('welcome-email.html')).substitute(context)
    settings=business_settings(db)
    if settings['insured_email_template']:
        text=insured_message(db,row,'email',url,settings=settings)
        html=html.replace('</body>','<p style="white-space:pre-wrap">'+escape(text)+'</p></body>')
    return text,html
