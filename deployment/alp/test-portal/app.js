const $=id=>document.getElementById(id);let catalog,reference='alp-prueba-'+crypto.randomUUID(),busy=false;
async function api(action,data){const response=await fetch('api.php?action='+action,data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...data,csrf:$('csrf').value})}:{});const body=await response.json();if(!response.ok)throw Error(body.error||'No se pudo completar la prueba.');return body;}
function message(text){$('status').textContent=text;}
function seller(){return catalog.sellers.find(p=>p.label===$('seller').value);}
$('seller').oninput=()=>{$('responsible').textContent=seller()?'Responsable: '+seller().responsible_name:'';};
$('type').oninput=()=>{$('business').hidden=$('type').value!=='Factura';};
for(const [id,length] of [['dni',8],['ruc',11]]){
 let timer,sequence=0;
 $(id).oninput=()=>{clearTimeout(timer);const number=$(id).value,version=++sequence;if(!new RegExp('^\\d{'+length+'}$').test(number))return;
 timer=setTimeout(async()=>{try{message('Consultando documento…');const {data}=await api('lookup',{number});if(version!==sequence)return;
 if(id==='dni'){$('names').value=data.first_names||data.names||'';$('paternal').value=data.paternal_surname||data.paternal_last_name||'';$('maternal').value=data.maternal_surname||data.maternal_last_name||'';}
 else{$('company').value=data.business_name||data.name||'';$('address').value=data.address||'';$('ubigeo').value=data.ubigeo||data.district_id||'';}message('Documento consultado.');}catch(e){if(version===sequence)message(e.message+' Puedes completar los datos manualmente.');}},300);};
}
$('sale').onsubmit=async event=>{event.preventDefault();if(busy)return;const plan=catalog.plans.find(p=>p.label===$('plan').value),emitter=seller(),invoice=$('type').value==='Factura';
 if(!plan||!emitter||!['Boleta','Factura'].includes($('type').value)||!['Cobrado por vendedor','Pendiente'].includes($('payment').value))return message('Selecciona las opciones del catálogo.');
 const values=Object.fromEntries(new FormData(event.currentTarget));for(const key of ['contractor_email','contractor_phone'])if(!values[key])delete values[key];
 const billing=invoice?{invoice_type_code:'01',customer_document_type:'RUC',customer_document_number:$('ruc').value,customer_name:$('company').value,customer_address:$('address').value,customer_ubigeo:$('ubigeo').value,due_date:$('due').value||null}:{invoice_type_code:'03'};
 busy=true;const submit=event.currentTarget.querySelector('button[type=submit]');submit.disabled=true;message('Generando documentos de prueba…');
 try{const response=await api('emit',{emission:{...values,plan_id:plan.id,external_emitter_id:emitter.id,external_responsible_id:emitter.responsible_id,external_reference:reference,payment_method:'cash',payment_status:$('payment').value==='Pendiente'?'pending':'collected_by_seller',billing}});const row=response.data;
 $('result').replaceChildren();const heading=document.createElement('h2');heading.textContent='Prueba registrada: '+row.internal_code;$('result').append(heading);
 for(const [kind,label] of [['letter','Carta de bienvenida'],['PDF','Comprobante A4'],['Ticket','Ticket'],['XML','XML sin firma'],['ZIP','ZIP de muestra']]){const a=document.createElement('a');a.className='document';a.textContent=label;a.href='api.php?action=file&emission='+row.id+'&kind='+kind;a.target='_blank';a.rel='noopener';$('result').append(a);}
 const qr=document.createElement('a');qr.textContent='Abrir validación del QR';qr.href=row.public_verification_url;qr.target='_blank';qr.rel='noopener';$('result').append(qr);
 const send=document.createElement('button');send.type='button';send.textContent='Simular envío de bienvenida';send.onclick=async()=>{send.disabled=true;try{await api('resend',{emission_id:row.id});message('Envío simulado registrado. No se ha enviado correo.');}catch(e){message(e.message);}finally{send.disabled=false;}};$('result').append(send);$('result').hidden=false;$('sale').hidden=true;message('Completado. No se reservó numeración real ni se envió a SUNAT.');
 }catch(e){message(e.message);}finally{busy=false;submit.disabled=false;}
};
api('bootstrap').then(data=>{catalog=data;$('batch').textContent='Lote: '+data.batch;$('start').value=$('start').min=$('due').min=data.tomorrow;
 for(const [items,list] of [[data.plans,'plans'],[data.sellers,'sellers']])for(const item of items){item.label=item.name+' · '+item.id;const option=document.createElement('option');option.value=item.label;$(list).append(option);}
 $('sale').hidden=false;message('Acceso de pruebas listo.');}).catch(e=>message(e.message));
