// Bounded, entirely local adjustments. The source File is never modified.
export async function adjustImage(file: File, turns: number, sharpen: boolean): Promise<File> {
  const bitmap = await createImageBitmap(file);
  try {
    if (bitmap.width * bitmap.height > 16_000_000) throw Error('Para ajustar, usa una imagen de hasta 16 megapíxeles. Puedes subir el original.');
    const canvas = document.createElement('canvas');
    canvas.width = turns % 2 ? bitmap.height : bitmap.width;
    canvas.height = turns % 2 ? bitmap.width : bitmap.height;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw Error('El navegador no permite ajustar esta imagen');
    ctx.translate(canvas.width / 2, canvas.height / 2); ctx.rotate(turns * Math.PI / 2);
    ctx.drawImage(bitmap, -bitmap.width / 2, -bitmap.height / 2);
    if (sharpen) {
      const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const original = new Uint8ClampedArray(pixels.data), stride = canvas.width * 4;
      for (let y=1;y<canvas.height-1;y++) for(let x=1;x<canvas.width-1;x++) {
        const i=y*stride+x*4;
        for(let c=0;c<3;c++) pixels.data[i+c]=2*original[i+c]-.25*(original[i+c-4]+original[i+c+4]+original[i+c-stride]+original[i+c+stride]);
      }
      ctx.putImageData(pixels,0,0);
    }
    const blob = await new Promise<Blob>((resolve,reject)=>canvas.toBlob(b=>b?resolve(b):reject(Error('No se pudo preparar la imagen')),'image/png'));
    return new File([blob],file.name.replace(/\.[^.]+$/, '')+'.png',{type:'image/png'});
  } finally { bitmap.close(); }
}

export async function rotatePdf(file: File): Promise<File> {
  const {PDFDocument, degrees}=await import('pdf-lib');
  const pdf=await PDFDocument.load(await file.arrayBuffer());
  for(const page of pdf.getPages()) page.setRotation(degrees((page.getRotation().angle+90)%360));
  const data=await pdf.save();
  return new File([new Uint8Array(data)],file.name,{type:'application/pdf'});
}
