"""Patch only the official site's medical search, retaining payment code untouched."""
import argparse
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--source',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
s=a.source.read_text(encoding='utf-8-sig')

def replace(old,new):
    global s
    if s.count(old)!=1:raise SystemExit('Website changed: expected marker not unique: '+old[:60])
    s=s.replace(old,new,1)

replace("$isDocument = $digits !== '' && strlen($digits) >= 8 && strlen($digits) <= 12;", "$isDocument = preg_match('/^[0-9]{8,12}$/', $rawQuery) === 1;")
start=s.index('    $candidateParams = $isDocument')
end=s.index("    $payload = $result['payload']",start)
s=s[:start]+"""    // One canonical request; do not overwrite useful errors with fallback queries.
    $endpoint = 'https://v2.abissol.org/abissol/api/v1/medical/public/search?'
        . http_build_query(['q' => $searchValue]);
    $result = abissol_landing_json_request($endpoint);

"""+s[end:]
replace("const isValid = found && !isCancelled && item.valid !== false;", "const isValid = found && !isCancelled && item.valid !== false && !item.is_test;")
replace('        isCancelled,', '        isCancelled,\n        isTest: Boolean(item.is_test),\n        welcomeLetterUrl: item.welcome_letter_url || \'\',')
replace("const title = item.isValid\n        ? 'Programa vigente'\n        : (item.isCancelled ? 'Programa anulado' : 'Programa no vigente');", "const title = item.isTest ? 'PRUEBA — No acredita cobertura real' : (item.statusLabel || (item.isValid ? 'Programa vigente' : 'Programa no vigente'));")
replace("      if (item.isValid && item.conditionedUrl) {", "      if (!item.isCancelled && item.welcomeLetterUrl && /^https:\\/\\//.test(item.welcomeLetterUrl)) {\n        actions.push('<a class=\"assistance-link\" href=\"' + escapeHtml(item.welcomeLetterUrl) + '\" target=\"_blank\" rel=\"noopener noreferrer\">Descargar carta de bienvenida</a>');\n      }\n      if (!item.isCancelled && item.conditionedUrl) {")
replace("if (!/^[0-9]{8,12}$/.test(documentNumber))", "if (!/^[A-Za-z0-9_-]{6,100}$/.test(documentNumber))")
replace("Ingresa un documento válido. Solo números, entre 8 y 12 dígitos.", "Ingresa un documento o código de verificación válido.")
replace("input.value = input.value.replace(/\\D/g, '').slice(0, 12);", "input.value = input.value.replace(/[^A-Za-z0-9_-]/g, '').slice(0, 100);")
replace("document_number: String(value || '').replace(/\\D/g, '').slice(0, 12)", "document_number: String(value || '').replace(/[^A-Za-z0-9_-]/g, '').slice(0, 100)")
replace('maxlength="12"', 'maxlength="100"')
start=s.index('    function decodeConsultaParam(value)')
end=s.index('\n    }',start)+6
piece=s[start:end]
piece=piece.replace(".replace(/\\D/g, '')", ".replace(/[^A-Za-z0-9_-]/g, '')")
s=s[:start]+piece+s[end:]
replace("decodeConsultaParam(params.get('consulta')).slice(0, 12)","decodeConsultaParam(params.get('consulta')).slice(0, 100)")
replace("if (autoQuery && /^[0-9]{8,12}$/.test(autoQuery))", "if (autoQuery && /^[A-Za-z0-9_-]{6,100}$/.test(autoQuery))")
replace("    function maskDocument(value) {", "    function maskDocument(value) {\n      if (String(value || '').includes('****')) return String(value);")
a.output.parent.mkdir(parents=True,exist_ok=True)
with a.output.open('x',encoding='utf-8',newline='') as f:f.write(s)
print('Official search prepared for V2; payment functions untouched.')
