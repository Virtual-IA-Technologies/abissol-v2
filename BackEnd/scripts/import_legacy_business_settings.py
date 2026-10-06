"""Apply the four non-secret emission settings from Laravel on the same server."""
import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy-env',type=Path,required=True)
    parser.add_argument('--backup-dir',type=Path,required=True)
    args=parser.parse_args()
    import pymysql
    from dotenv import dotenv_values
    from app.database import SessionLocal
    import app.models
    from app.models.medical import MedicalBusinessSetting
    from app.models.audit import AuditLog
    from app.services.medical_settings import BusinessSettingsInput
    env=dotenv_values(args.legacy_env,encoding='latin-1')
    with pymysql.connect(read_default_file='/root/.my.cnf',database=env['DB_DATABASE']) as conn:
        with conn.cursor() as cursor:
            keys=['medical.'+key for key in BusinessSettingsInput.model_fields]
            cursor.execute('SELECT `key`,`value` FROM medical_settings WHERE `key` IN (%s,%s,%s,%s)',keys)
            values={key.removeprefix('medical.'):value for key,value in cursor.fetchall() if value is not None}
    values=BusinessSettingsInput.model_validate(values).model_dump()
    with SessionLocal() as db:
        row=db.get(MedicalBusinessSetting,1)
        args.backup_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
        target=args.backup_dir/('emission-settings-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.json')
        with os.fdopen(os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as backup:
            json.dump(row.values if row else None,backup)
        row=row or MedicalBusinessSetting(id=1)
        row.values=values
        db.add(row)
        db.add(AuditLog(accion='import',modulo='medical-emissions',entidad='medical_business_settings',detalle='Parametros de emisiones copiados de Laravel; sin activar programacion ni enviar mensajes'))
        db.commit()
    print(json.dumps({'imported':True,'meta_recipient_configured':bool(values['metafin_email']),'automatic_sends_enabled':False}))


if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('Importacion detenida: '+type(exc).__name__,file=sys.stderr)
        sys.exit(1)
