#!/usr/bin/env bash
set -euo pipefail
umask 027
root=/home/abissol/apps/abissol-v2
backend="$root/current/BackEnd"
portal=/home/alp/public_html/siacat/abissol-pruebas
test -f /home/alp/public_html/siacat/abissol/bootstrap.php
test -f "$backend/migrations/versions/0015_medical_test_batch.py"
if [ -d "$portal" ] && [ ! -f "$portal/.abissol-v2-test-portal" ]; then
 echo 'Existing directory is not managed by this installer.' >&2; exit 1
fi
mkdir -p "$portal"
cp "$root/current/deployment/alp/test-portal/"* "$portal/"
touch "$portal/.abissol-v2-test-portal"
chown -R alp:alp "$portal"
chmod 755 "$portal"
find "$portal" -maxdepth 1 -type f -exec chmod 644 {} +
for file in "$portal/"*.php; do /opt/cpanel/ea-php82/root/usr/bin/php -l "$file"; done
cd "$backend"
if [ ! -f /home/alp/.abissol-v2-test-token ]; then
 "$root/.venv/bin/python" scripts/create_medical_connector.py --source externa_alp --test-only --output /home/alp/.abissol-v2-test-token
fi
chown alp:alp /home/alp/.abissol-v2-test-token
chmod 600 /home/alp/.abissol-v2-test-token
"$root/.venv/bin/python" - <<'PY'
import json,hashlib,os
from pathlib import Path
from datetime import datetime,timezone
from app.database import SessionLocal,engine
from app.models import Usuario
from app.models.medical import MedicalPlan,MedicalIntegrationCredential,MedicalSource
from app.services.medical_testing import activate
from app.services.medical_billing import configuration
from app.routes.audit import audit_change
assert engine.url.database=='abissol_v2'
with SessionLocal() as db:
    digest=hashlib.sha256(Path('/home/alp/.abissol-v2-test-token').read_bytes().strip()).hexdigest()
    credential=db.query(MedicalIntegrationCredential).filter_by(token_hash=digest,active=True,test_only=True).one()
    assert db.get(MedicalSource,credential.source_id).external_key=='externa_alp'
    user=db.query(Usuario).filter_by(correo='lcmariaca@gmail.com',is_active=True).one()
    _,raw=configuration(db)
    before={'test_batch':raw.get('test_batch'),'enabled':bool(raw.get('enabled_in_v2'))}
    batch=activate(db,True)
    baseline={'test_batch':batch,'plans':{str(p.id):p.counter for p in db.query(MedicalPlan)},'fiscal_counters':{k:raw.get(k) for k in ('v2_counter','v2_invoice_counter')},'legacy_series':raw.get('series',[])}
    path=Path('/home/abissol/apps/abissol-v2/backups')/('test-baseline-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'.json')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as file:json.dump(baseline,file)
    audit_change(db,None,user,'medical_test_mode',0,before=before,after={'test_batch':batch,'enabled':False},module='abissol_medical')
    db.commit()
    print(json.dumps({'test_batch':batch,'sunat_enabled':False,'external_test_credential':True,'baseline_saved':True}))
PY
curl -fsS https://v2.abissol.org/health/ready
