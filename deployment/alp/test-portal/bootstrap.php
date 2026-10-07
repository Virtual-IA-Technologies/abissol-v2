<?php
// Runs inside ALP; existing authentication is reused, never copied/exported.
require_once __DIR__ . '/../abissol/bootstrap.php';
if ($abissolUserId <= 0 || !in_array($abissolRole, [0,1,2,3,4], true)) {
    http_response_code(403); exit('Acceso de AFOCAT requerido.');
}
header('Cache-Control: no-store');
header('X-Robots-Tag: noindex, nofollow');
header('X-Content-Type-Options: nosniff');
function pilot_request($method, $path, $payload = null, $binary = false) {
    $token = trim((string)@file_get_contents('/home/alp/.abissol-v2-test-token'));
    if (!$token) throw new RuntimeException('Acceso de pruebas no configurado.');
    $curl = curl_init('https://v2.abissol.org/abissol/api/v1/integrations/medical' . $path);
    curl_setopt_array($curl, [CURLOPT_RETURNTRANSFER=>true,CURLOPT_CUSTOMREQUEST=>$method,
        CURLOPT_HTTPHEADER=>['Authorization: Bearer '.$token,'Content-Type: application/json'],
        CURLOPT_CONNECTTIMEOUT=>10,CURLOPT_TIMEOUT=>90,CURLOPT_FOLLOWLOCATION=>false,
        CURLOPT_SSL_VERIFYPEER=>true,CURLOPT_SSL_VERIFYHOST=>2]);
    if ($payload !== null) curl_setopt($curl,CURLOPT_POSTFIELDS,json_encode($payload));
    $body=curl_exec($curl); $status=curl_getinfo($curl,CURLINFO_HTTP_CODE); curl_close($curl);
    $data=$binary && $status===200 ? null : json_decode((string)$body,true);
    if ($status < 200 || $status >= 300) throw new RuntimeException(is_string($data['detail']??null)?$data['detail']:'No se pudo completar la prueba. Revisa los datos y el modo de pruebas en V2.');
    return $binary ? $body : $data;
}
function pilot_record($id) {
    global $abissolRole,$abissolUserId;
    $record=pilot_request('GET','/emissions/'.(int)$id)['data'];
    if (empty($record['test_batch']) || !alp_int_user_can_access($abissolRole,$abissolUserId,$record['external_emitter_id'],$record['external_responsible_id'])) {
        throw new RuntimeException('No tienes acceso a esta emisión de prueba.');
    }
    return $record;
}
