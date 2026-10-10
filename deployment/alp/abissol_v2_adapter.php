<?php
// Staged ALP adapter: load from emitir/integraciones.php. No secrets in this file.
function alp_abissol_is_v2(array $config)
{
    return rtrim((string)($config['api_url'] ?? ''), '/') === 'https://v2.abissol.org/abissol/api/v1/integrations';
}

function alp_abissol_v2_billing(array $preference)
{
    $result = ['invoice_type_code' => (string)($preference['invoice_type_code'] ?? '03')];
    foreach (['customer_document_type','customer_document_number','customer_name','customer_address','customer_ubigeo','due_date'] as $key) {
        if (isset($preference[$key]) && $preference[$key] !== '') $result[$key] = (string)$preference[$key];
    }
    if (empty($result['customer_ubigeo']) && !empty($preference['customer_district_id'])) {
        $result['customer_ubigeo'] = (string)$preference['customer_district_id'];
    }
    // Boleta without an explicit receiver uses the insured person's document.
    if ($result['invoice_type_code'] === '03' && empty($result['customer_document_number'])) return ['invoice_type_code'=>'03'];
    return $result;
}

function alp_abissol_v2_response($url, array $decoded)
{
    if (strpos($url, 'https://v2.abissol.org/abissol/api/v1/integrations/medical/') !== 0) return $decoded;
    if (!isset($decoded['message']) && isset($decoded['detail'])) {
        $decoded['message'] = is_string($decoded['detail']) ? $decoded['detail'] : 'Revise los datos obligatorios de la solicitud.';
    }
    if (substr($url, -7) === '/resend' && isset($decoded['data']) && is_array($decoded['data'])) {
        $messages = [];
        foreach ($decoded['data'] as $attempt) {
            $messages[] = (($attempt['channel'] ?? '') === 'email' ? 'Correo' : 'WhatsApp') . ': ' .
                (($attempt['status'] ?? '') === 'sent' ? 'aceptado por el proveedor' : (($attempt['status'] ?? '') === 'simulated' ? 'simulado, sin envío real' : 'sin confirmación; revise antes de reenviar'));
        }
        $decoded['message'] = implode('. ', $messages);
    }
    $map = static function (array $row) {
        if (!empty($row['welcome_letter_api_url'])) {
            $row['welcome_letter_url'] = '/abissol/archivo_v2.php?emission='.(int)$row['id'].'&kind=letter';
        }
        if (!empty($row['invoice_pdf_api_url'])) {
            $row['invoice_pdf_url'] = '/abissol/archivo_v2.php?emission='.(int)$row['id'].'&kind=PDF';
        }
        if (!empty($row['pdf_api_url']) && !empty($row['issuance_id'])) {
            $row['pdf_url'] = '/abissol/archivo_v2.php?emission='.(int)$row['issuance_id'].'&kind=PDF';
        }
        return $row;
    };
    if (isset($decoded['data']) && is_array($decoded['data'])) {
        if (isset($decoded['data']['id'])) $decoded['data'] = $map($decoded['data']);
        elseif (isset($decoded['data'][0]) && is_array($decoded['data'][0])) $decoded['data'] = array_map($map, $decoded['data']);
    }
    return $decoded;
}
