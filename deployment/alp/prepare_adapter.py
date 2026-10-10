"""Prepare reviewed ALP files in a separate directory. Never switches production."""
import argparse
from pathlib import Path
import shutil

parser=argparse.ArgumentParser()
parser.add_argument('--source',type=Path,required=True,help='Snapshot containing emitir/ and abissol/')
parser.add_argument('--output',type=Path,required=True,help='New staging directory; must not exist')
args=parser.parse_args()
if args.output.exists():raise SystemExit('Use a new staging directory')
sources={name:(args.source/name).read_text(encoding='utf-8-sig') for name in ('emitir/integraciones.php','abissol/bootstrap.php','abissol/nueva_emision.php','abissol/enviar_emision.php','abissol/inicio.php')}

def replace(name,old,new):
    if sources[name].count(old)!=1:raise SystemExit(f'Source changed: inspect {name} before patching ({old[:45]})')
    sources[name]=sources[name].replace(old,new,1)

integration='emitir/integraciones.php'
replace(integration,'<?php','<?php\nrequire_once __DIR__ . "/abissol_v2_adapter.php";')
replace(integration,"        $config = require __DIR__ . '/integraciones_config.php';", "        $config = require __DIR__ . '/integraciones_config.php';\n        if (is_file('/home/alp/.abissol-v2-config.php')) {\n            $config['abissol'] = array_replace($config['abissol'], require '/home/alp/.abissol-v2-config.php');\n        }")
replace(integration,"    if (!is_array($decoded)) $decoded = ['raw' => $body];", "    if (!is_array($decoded)) $decoded = ['raw' => $body];\n    $decoded = alp_abissol_v2_response($url, $decoded);")
replace(integration,"    if (strtoupper($method) !== 'GET') $options[CURLOPT_POSTFIELDS] = alp_int_json($payload);", "    if (strpos($url, 'https://v2.abissol.org/abissol/api/v1/integrations/medical/billing/from-issuance/') === 0) $payload = alp_abissol_v2_billing($payload);\n    if (strtoupper($method) !== 'GET') $options[CURLOPT_POSTFIELDS] = alp_int_json($payload);")
replace(integration,'            $storedPayload = $payload;',"            if (alp_abissol_is_v2($config)) {\n                $payload['billing'] = alp_abissol_v2_billing($billingPreference);\n            }\n            $storedPayload = $payload;")
replace(integration,"    if ($host === 'api.abissol.org' && !$config['allow_production'])", "    if (in_array($host, ['api.abissol.org','v2.abissol.org'], true) && !$config['allow_production'])")
new='abissol/nueva_emision.php'
replace(new,"    $created = alp_abissol_api_request('POST', '/medical/emissions', $payload);", "    if (alp_abissol_is_v2($config)) $payload['billing'] = alp_abissol_v2_billing($preparedBilling);\n    $created = alp_abissol_api_request('POST', '/medical/emissions', $payload);")
bootstrap='abissol/bootstrap.php'
replace(bootstrap,"    if ($query) $url .= '?' . http_build_query($query);", "    if (alp_abissol_is_v2($config) && $path === '/medical/emissions') {\n        unset($query['per_page']);\n        $query['limit'] = 500;\n    }\n    if ($query) $url .= '?' . http_build_query($query);")
replace(bootstrap,"    return is_array($rows) ? $rows : [];", """    if (alp_abissol_is_v2($config) && $path === '/medical/emissions' && is_array($rows)) {
        $total = (int)($response['body']['total'] ?? count($rows));
        while (count($rows) < $total) {
            $query['offset'] = count($rows);
            $next = alp_abissol_api_request('GET', $path.'?'.http_build_query($query));
            $batch = $next['data'] ?? [];
            if (!$batch) throw new Exception('La lista cambió durante la consulta. Vuelva a cargar.');
            $rows = array_merge($rows, $batch);
        }
    }
    return is_array($rows) ? $rows : [];""")
replace(bootstrap,"    $query = ['per_page' => 'all'];", "    $query = ['per_page' => 'all'];\n    $v2 = alp_abissol_is_v2(alp_int_config()['abissol']);")
replace(bootstrap,"$query['date_from'] = date('Y-m-d', strtotime($dateFrom . ' +1 day'));", "$query['date_from'] = $v2 ? $dateFrom : date('Y-m-d', strtotime($dateFrom . ' +1 day'));")
replace(bootstrap,"$query['date_to'] = date('Y-m-d', strtotime($dateTo . ' +1 day'));", "$query['date_to'] = $v2 ? $dateTo : date('Y-m-d', strtotime($dateTo . ' +1 day'));")
replace(bootstrap,"        // Compatibilidad con servidores Abissol", "        if (alp_abissol_is_v2(alp_int_config()['abissol'])) throw $exception;\n        // Compatibilidad con servidores Abissol")
replace('abissol/enviar_emision.php',"        'email' => $sendEmail,", "        'real_test' => alp_abissol_is_v2($config),\n        'force' => !empty($_POST['force']),\n        'email' => $sendEmail,")
replace('abissol/inicio.php', "'<input id=\"ab-send-phone-value\" class=\"form-control\" placeholder=\"Teléfono\">',", "'<input id=\"ab-send-phone-value\" class=\"form-control\" placeholder=\"Teléfono\">' +\n      '<label class=\"d-block mt-3 text-start\"><input type=\"checkbox\" id=\"ab-send-force\"> Autorizar reenvío después de revisar el historial</label><p class=\"small mt-2\">En modo de pruebas, la recepción real está limitada a los destinatarios autorizados.</p>',")
replace('abissol/inicio.php',"        email: document.getElementById('ab-send-email').checked,", "        force: document.getElementById('ab-send-force').checked,\n        email: document.getElementById('ab-send-email').checked,")
replace('abissol/inicio.php',"  payload.set('recipient_email', result.value.recipient_email);", "  payload.set('force', result.value.force ? '1' : '');\n  payload.set('recipient_email', result.value.recipient_email);")
for name,content in sources.items():
    destination=args.output/name
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('w',encoding='utf-8',newline='\n') as file:
        file.write(content)
for name,target in [('abissol_v2_adapter.php','emitir'),('archivo_v2.php','abissol')]:
    shutil.copyfile(Path(__file__).parent/name,args.output/target/name)
print('Prepared 7 files; production configuration unchanged. Lint and review before cutover.')
