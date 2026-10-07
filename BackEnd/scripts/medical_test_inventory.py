"""Private dependency map for later reviewed cleanup. Never deletes records."""
import argparse,json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import or_,and_
from app.database import SessionLocal
from app.models.medical import MedicalIssuance,MedicalInvoice,MedicalDispatch
from app.models.documents import DocumentBinding,DocumentVersion
from app.models.fiscal import FiscalJob

def inventory(db,batch):
    sales=db.query(MedicalIssuance).filter_by(test_batch=batch).all();ids=[r.id for r in sales]
    invoices=db.query(MedicalInvoice).filter(MedicalInvoice.issuance_id.in_(ids)).all();invoice_ids=[r.id for r in invoices]
    bindings=db.query(DocumentBinding).filter(or_(and_(DocumentBinding.source_type=='emission',DocumentBinding.source_id.in_(ids)),and_(DocumentBinding.source_type=='invoice',DocumentBinding.source_id.in_(invoice_ids)))).all()
    documents=[r.document_id for r in bindings]
    versions=db.query(DocumentVersion).filter(DocumentVersion.document_id.in_(documents)).all()
    return {'test_batch':batch,'emissions':[{'id':r.id,'code':r.code,'external_source':r.external_source,'external_reference':r.external_reference} for r in sales],
        'invoices':[{'id':r.id,'number':r.full_number,'fiscal_directory':'storage/fiscal/'+str(r.id)} for r in invoices],
        'dispatch_ids':[r.id for r in db.query(MedicalDispatch).filter(or_(MedicalDispatch.issuance_id.in_(ids),MedicalDispatch.invoice_id.in_(invoice_ids)))],
        'document_ids':documents,'versions':[{'id':r.id,'document_id':r.document_id,'storage_key':r.storage_key} for r in versions],
        'fiscal_job_ids':[r.id for r in db.query(FiscalJob).filter(FiscalJob.invoice_id.in_(invoice_ids))]}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--batch',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if not args.batch.startswith('PRUEBA-'):raise SystemExit('Solo se mapean lotes de prueba identificados.')
    with SessionLocal() as db:result=inventory(db,args.batch)
    fd=os.open(args.output,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps({'emissions':len(result['emissions']),'invoices':len(result['invoices']),'documents':len(result['document_ids']),'fiscal_jobs':len(result['fiscal_job_ids']),'deleted':0}))
