<?php
require_once __DIR__.'/bootstrap.php';
// Portal session and role scope remain mandatory. Never accept a remote URL or token from the browser.
try {
    $id = filter_input(INPUT_GET, 'emission', FILTER_VALIDATE_INT);
    $kind = (string)($_GET['kind'] ?? '');
    if (!$id || $id < 1 || !in_array($kind, ['letter','PDF','XML','CDR'], true)) throw new Exception('Archivo no válido.', 400);
    $config = alp_int_config()['abissol'];
    if (!alp_abissol_is_v2($config)) throw new Exception('El conector V2 todavía no está activo.', 409);
    $row = alp_abissol_api_request('GET', '/medical/emissions/'.$id)['data'] ?? [];
    if (!$row || !alp_abissol_row_visible_for_current_user($row)) throw new Exception('Sin acceso a esta emisión.', 403);
    $path = '/medical/emissions/'.$id.'/letter';
    if ($kind !== 'letter') {
        $invoiceId = (int)($row['invoice_id'] ?? 0);
        if (!$invoiceId) throw new Exception('Comprobante no disponible.', 404);
        $path = '/medical/billing/'.$invoiceId.'/file/'.$kind;
    }
    $ch = curl_init($config['api_url'].$path);
    curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER=>true,CURLOPT_FOLLOWLOCATION=>false,CURLOPT_CONNECTTIMEOUT=>10,
        CURLOPT_TIMEOUT=>45,CURLOPT_HTTPHEADER=>['Authorization: Bearer '.alp_abissol_auth_token($config)]]);
    $body = curl_exec($ch);
    $status = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    if ($body === false || $status !== 200) throw new Exception('Archivo aún no disponible. Revise el estado del comprobante.', 404);
    $extension = ['letter'=>'pdf','PDF'=>'pdf','XML'=>'xml','CDR'=>'zip'][$kind];
    $type = ['pdf'=>'application/pdf','xml'=>'application/xml','zip'=>'application/zip'][$extension];
    header('Content-Type: '.$type);
    header('Cache-Control: private, no-store');
    header('X-Content-Type-Options: nosniff');
    header('Content-Disposition: inline; filename="abissol-'.$id.'-'.$kind.'.'.$extension.'"');
    echo $body;
} catch (Throwable $error) {
    $status = (int)$error->getCode();
    http_response_code(in_array($status,[400,403,404,409],true) ? $status : 502);
    header('Content-Type: text/plain; charset=utf-8');
    echo 'No se pudo obtener el archivo autorizado. Compruebe su sesión y el estado de la emisión.';
}
