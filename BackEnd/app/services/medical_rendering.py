"""Original ABISSOL layouts, local resources and QR generation without network calls."""
from functools import lru_cache
from html import escape
from pathlib import Path
from string import Template
import io
import base64
import json
import os
import shutil
import subprocess
import qrcode
from . import sunat

TEMPLATES=Path(__file__).resolve().parents[1]/'templates/medical'
ASSETS=Path(__file__).resolve().parents[3]/'FrontEnd/frontend-app/public'

@lru_cache(maxsize=12)
def template(name):return (TEMPLATES/name).read_text(encoding='utf8')

@lru_cache(maxsize=2)
def image_data(name):
    return 'data:image/png;base64,'+base64.b64encode((ASSETS/name).read_bytes()).decode()

def render(html,qr,kind):
    for name in ('abissol-logo.png','alp-logo.png'):
        html=html.replace('src="'+name+'"','src="'+image_data(name)+'"')
    buf=io.BytesIO();qrcode.make(qr).save(buf,format='PNG')
    html=html.replace('src="qr.png"','src="data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()+'"')
    renderer=Path(__file__).resolve().parents[2]/'pdf_renderer/render.php'
    cpanel_php=Path('/opt/cpanel/ea-php82/root/usr/bin/php')
    php=os.environ.get('ABISSOL_PHP_BIN') or (str(cpanel_php) if cpanel_php.is_file() else shutil.which('php'))
    if not php:raise RuntimeError('Falta PHP CLI para conservar el formato PDF original')
    command=[php,*(['-d','extension=gd'] if os.name=='nt' else []),str(renderer)]
    result=subprocess.run(command,input=json.dumps({'kind':kind,'html':html}).encode(),capture_output=True,timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    if result.returncode or not result.stdout.startswith(b'%PDF-'):
        raise RuntimeError('No se pudo generar el PDF original; verifica el motor de impresión')
    return result.stdout


def welcome(row,url):
    months=['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre']
    date=row.sale_date
    context={key:escape(str(value or '-')) for key,value in {'city':getattr(row,'city',None) or 'Lima','letter_date':f'{date.day:02d} de {months[date.month-1]} de {date.year}',
        'name':row.customer,'document':row.document_number,'code':row.code,'start':row.starts_on.strftime('%d/%m/%Y'),'end':row.ends_on.strftime('%d/%m/%Y'),
        'phone':row.phone,'email':row.email,'contribution':'S/ '+str(sunat.money(row.price)),'plan':row.plan_name.upper(),'url':url}.items()}
    context.update(logo='abissol-logo.png',partner='alp-logo.png',qr='qr.png',benefits=template('benefits-'+('plus' if 'plus' in row.plan_name.lower() else 'essential')+'.html'))
    return render(Template(template('welcome.html')).substitute(context),url,'welcome')

def invoice(row,digest,ticket=False):
    data=row.details;issuer=data['issuer'];total=sunat.money(row.total)
    series,number=row.full_number.split('-')
    doc_type={'DNI':'1','CE':'4','PASSPORT':'7','RUC':'6'}[data['customer_document_type']]
    qr='|'.join([issuer['ruc'],'01' if row.document_type=='factura' else '03',series,number,'0.00',str(total),row.issue_date.isoformat(),doc_type,row.document_number,digest])
    context={key:escape(str(value or '-')) for key,value in {
        'docTitle':('FACTURA' if row.document_type=='factura' else 'BOLETA DE VENTA')+' ELECTRÓNICA','fullNumber':row.full_number,
        'company':issuer['company_name'],'legalName':issuer['company_name'],'issuerTop':issuer.get('trade_name') or 'ABISSOL','tradeName':issuer.get('trade_name') or 'ABISSOL',
        'ruc':issuer['ruc'],'address':issuer['address'],'location':' - '.join(str(issuer.get(k) or '') for k in ['district','province','department']),
        'clientName':row.customer,'clientDoc':data['customer_document_type']+' '+row.document_number,'clientAddress':data.get('customer_address') or '-',
        'clientLocation':data.get('customer_ubigeo') or '-','currency':'SOLES','issueDate':row.issue_date.strftime('%d/%m/%Y'),'dueDate':data.get('due_date') or '-',
        'reference':data.get('external_reference') or '-','notes':data.get('notes') or '', 'amountWords':sunat.amount_words(total),'hash':digest,'tax_percent':'0.00',
        'payment_terms':data.get('payment_terms') or 'Contado'}.items()}
    context['company']=context['company'].replace(', SALUD Y SOLIDARIDAD',',<br>SALUD Y SOLIDARIDAD')
    context['contact']=' | '.join(escape(str(issuer[k])) for k in ['phone','email'] if issuer.get(k))
    context['logo']='<img class="'+('ticket-logo' if ticket else 'a4-logo')+'" src="abissol-logo.png" alt="ABISSOL">'
    context['qr']='<img class="qr-img" src="qr.png" alt="QR SUNAT">'
    rows=[]
    for index,item in enumerate(data['items'],1):
        lines=item['description'].splitlines();description='<span class="main">'+escape(lines[0])+'</span>'+''.join('<span class="feature">• '+escape(line.lstrip('-• '))+'</span>' for line in lines[1:])
        amount=str(sunat.money(item['total']))
        cells=[f'{index:03d}',description,'1',amount] if ticket else [f'{index:03d}','1','ZZ',description,amount,'0.00',amount]
        rows.append('<tr>'+''.join('<td class="'+('desc' if ticket and i==1 else 'item-description' if not ticket and i==3 else 'right')+'">'+cell+'</td>' for i,cell in enumerate(cells))+'</tr>')
    context['rows']=''.join(rows)
    labels=['OPERACIÓN GRAVADA:','OPERACIÓN INAFECTA:','OPERACIÓN EXONERADA:','SUB TOTAL:','IGV (0.00%):','TOTAL A PAGAR:'] if ticket else ['OP. GRAVADAS','OP. INAFECTAS','OP. EXONERADAS','SUB TOTAL','IGV','TOTAL']
    context['totals']=''.join('<tr'+(' class="total-final"' if i==5 else '')+'><td class="total-label">'+label+'</td><td class="total-value right">S/ '+str(sunat.money(value))+'</td></tr>' for i,(label,value) in enumerate(zip(labels,[0,total,0,total,0,total])))
    context['beta_notice']='<p style="color:#b91c1c;font-weight:bold">PRUEBA BETA - SIN VALIDEZ TRIBUTARIA</p>' if data['environment']!='production' else ''
    context['credit_note']=f'<p>Cuota 001: S/ {total} · Vence: {escape(str(data.get("due_date") or ""))}</p>' if data.get('payment_terms')=='Credito' else ''
    return render(Template(template('ticket.html' if ticket else 'invoice.html')).substitute(context),qr,'ticket' if ticket else 'invoice')
