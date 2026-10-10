export async function optimizeVoucher(file:File):Promise<File> {
  if(file.size>20*1024*1024)throw Error('El archivo supera 20 MB.');
  if(file.type==='application/pdf')return file;
  const image=await createImageBitmap(file);
  try {
    const scale=Math.min(1,2400/Math.max(image.width,image.height));
    const canvas=document.createElement('canvas');canvas.width=Math.round(image.width*scale);canvas.height=Math.round(image.height*scale);
    const ctx=canvas.getContext('2d')!;ctx.fillStyle='#fff';ctx.fillRect(0,0,canvas.width,canvas.height);
    ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';ctx.drawImage(image,0,0,canvas.width,canvas.height);
    const blob=await new Promise<Blob|null>(resolve=>canvas.toBlob(resolve,'image/jpeg',0.9));
    if(!blob||(scale===1&&blob.size>=file.size))return file;
    return new File([blob],file.name.replace(/\.[^.]+$/,'')+'.jpg',{type:'image/jpeg'});
  } finally {image.close();}
}

export async function readVoucher(file:File,progress:(text:string)=>void):Promise<string> {
  if(file.size>5*1024*1024)throw Error('El voucher debe pesar como máximo 5 MB.');
  const {createWorker}=await import('tesseract.js');
  const asset=new URL(`${import.meta.env.BASE_URL}ocr/`,window.location.origin).href;
  const worker=await createWorker('spa+eng',1,{workerPath:asset+'worker.min.js',corePath:asset,langPath:asset,workerBlobURL:false});
  let pdf:import('pdfjs-dist').PDFDocumentProxy|undefined;
  let loading:import('pdfjs-dist').PDFDocumentLoadingTask|undefined;
  try {
    if(file.type==='application/pdf'||file.name.toLowerCase().endsWith('.pdf')) {
      const engine=await import('pdfjs-dist');
      engine.GlobalWorkerOptions.workerSrc=(await import('pdfjs-dist/build/pdf.worker.min.mjs?url')).default;
      loading=engine.getDocument({data:await file.arrayBuffer()});pdf=await loading.promise;
      if(pdf.numPages>3)throw Error('Adjunta solo el voucher (máximo tres páginas).');
      const texts:string[]=[];
      for(let i=1;i<=pdf.numPages;i++){
        progress(`Leyendo página ${i} de ${pdf.numPages}…`);
        const page=await pdf.getPage(i),content=await page.getTextContent();
        const text=content.items.map(i=>'str' in i?i.str:'').join('\n');
        if(text.trim().length>40){texts.push(text);continue;}
        const base=page.getViewport({scale:1});
        const view=page.getViewport({scale:Math.min(2,Math.sqrt(4000000/(base.width*base.height)))});
        const canvas=document.createElement('canvas');canvas.width=view.width;canvas.height=view.height;
        await page.render({canvas,viewport:view}).promise;
        texts.push((await worker.recognize(canvas)).data.text);canvas.width=canvas.height=0;
      }
      return texts.join('\n').slice(0,20000);
    }
    const image=await createImageBitmap(file),scale=Math.min(1,Math.sqrt(4000000/(image.width*image.height)));
    const canvas=document.createElement('canvas');canvas.width=image.width*scale;canvas.height=image.height*scale;
    canvas.getContext('2d')!.drawImage(image,0,0,canvas.width,canvas.height);image.close();
    return (await worker.recognize(canvas)).data.text.slice(0,20000);
  } finally {await loading?.destroy();await worker.terminate();}
}

export function voucherFields(text:string){
  const amount=text.match(/(?:importe|monto(?:\s+(?:total|transferido|enviado))?|total|S\/\.?|S\.)[^\d\n]{0,25}\s*([\d.,]+[.,]\d{2})(?!\d)/i)?.[1]||'';
  const commaDecimal=amount.lastIndexOf(',')>amount.lastIndexOf('.');
  const normalized=commaDecimal?amount.replace(/\./g,'').replace(',','.'):amount.replace(/,/g,'');
  const reference=text.match(/(?:operaci[oó]n|referencia|transacci[oó]n)[^\d\n]{0,25}\s*([A-Z0-9-]{3,30})/i)?.[1]||'';
  const account=text.match(/(?:cuenta(?:\s+destino)?|CCI)[^\d\n]{0,20}\s*([\d -]{6,34})/i)?.[1]?.replace(/[ -]/g,'')||'';
  const date=text.match(/\b(\d{2})[/-](\d{2})[/-](20\d{2})\b/);
  const bank=['BCP','BBVA','INTERBANK','SCOTIABANK','BANCO DE LA NACION','CAJA AREQUIPA'].find(b=>text.toUpperCase().includes(b))||'';
  return {amount:normalized,reference,account,bank,paid_on:date?`${date[3]}-${date[2]}-${date[1]}`:''};
}
