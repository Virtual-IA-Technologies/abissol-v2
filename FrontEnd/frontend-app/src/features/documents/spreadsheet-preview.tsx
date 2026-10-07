import {useEffect,useState} from 'react';
import {UnderlineTabs} from '@/components/underline-tabs';

export default function SpreadsheetPreview({file}:{file:File}) {
  const [sheets,setSheets]=useState<{name:string;rows:string[][]}[]>([]);
  const [error,setError]=useState('');const [selected,setSelected]=useState('0');
  useEffect(()=>{let active=true;void(async()=>{
    const {default:ExcelJS}=await import('exceljs');const workbook=new ExcelJS.Workbook();
    await workbook.xlsx.load(await file.arrayBuffer());
    const result=workbook.worksheets.slice(0,10).map(sheet=>({name:sheet.name,rows:Array.from({length:Math.min(sheet.rowCount,200)},(_,row)=>Array.from({length:Math.min(sheet.columnCount,50)},(_,column)=>sheet.getCell(row+1,column+1).text))}));
    if(active)setSheets(result);
  })().catch(()=>{if(active)setError('No se pudo interpretar la hoja. Puedes descargar el original.');});return()=>{active=false;};},[file]);
  if(error)return <p role="alert" className="p-4 text-sm">{error}</p>;
  if(!sheets.length)return <p className="p-4">Leyendo hojas…</p>;
  return <div className="space-y-3 p-3"><UnderlineTabs label="Hojas del documento" value={selected} onChange={setSelected} tabs={sheets.map((sheet,index)=>({value:String(index),label:sheet.name}))}><p className="text-xs text-muted-foreground">Vista de las primeras 10 hojas, hasta 200 filas y 50 columnas por hoja. La descarga conserva el libro completo.</p><div className="max-h-[65vh] overflow-auto"><table className="border-collapse text-sm"><tbody>{sheets[Number(selected)].rows.map((row,i)=><tr key={i}>{row.map((cell,j)=><td key={j} className="min-w-24 whitespace-pre-wrap border px-2 py-1">{cell}</td>)}</tr>)}</tbody></table></div></UnderlineTabs></div>;
}
