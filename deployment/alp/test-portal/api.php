<?php
require_once __DIR__.'/bootstrap.php';
header('Content-Type: application/json; charset=utf-8');
try {
    $action=$_GET['action']??'';
    $payload=[];
    if ($_SERVER['REQUEST_METHOD']==='POST') {
        $raw=file_get_contents('php://input',false,null,0,16385);
        if (strlen($raw)>16384) throw new RuntimeException('Solicitud demasiado grande.');
        $payload=json_decode($raw,true);
        if (!is_array($payload) || !alp_abissol_verify_action_csrf((string)($payload['csrf']??''))) throw new RuntimeException('Recarga la página: sesión de prueba vencida.');
    } elseif (!in_array($action,['bootstrap','file'],true)) {
        http_response_code(405);exit;
    }
    if ($action==='bootstrap') {
        $caps=pilot_request('GET','/capabilities');
        if (empty($caps['test_batch'])) throw new RuntimeException('El modo de pruebas está cerrado.');
        $all=pilot_request('GET','/sellers')['data'];$byId=[];
        foreach ($all as $item) $byId[$item['id']]=$item;
        $sellers=[];
        foreach ($all as $item) {
            if (!$item['active'] || !in_array($item['source_role'],['responsible','emitter'],true)) continue;
            $responsible=$item['source_role']==='responsible'?$item:($byId[$item['responsible_seller_id']]??null);
            if (!$responsible || !$responsible['external_user_id'] || !$item['external_user_id']) continue;
            if (!alp_int_user_can_access($abissolRole,$abissolUserId,$item['external_user_id'],$responsible['external_user_id'])) continue;
            $sellers[]=['id'=>(int)$item['external_user_id'],'name'=>$item['name'],'responsible_id'=>(int)$responsible['external_user_id'],'responsible_name'=>$responsible['name']];
        }
        $result=['plans'=>pilot_request('GET','/plans')['data'],'sellers'=>$sellers,'batch'=>$caps['test_batch'],
            'tomorrow'=>(new DateTimeImmutable('tomorrow',new DateTimeZone('America/Lima')))->format('Y-m-d')];
    } elseif ($action==='lookup') {
        $number=(string)($payload['number']??'');
        if (preg_match('/^\d{8}$/',$number)) $result=pilot_request('POST','/lookup/dni',['dni'=>$number]);
        elseif(preg_match('/^\d{11}$/',$number)) $result=pilot_request('POST','/billing/lookup-document',['document'=>$number]);
        else throw new RuntimeException('Documento inválido.');
    } elseif ($action==='emit') {
        $data=$payload['emission']??[];
        if (!alp_int_user_can_access($abissolRole,$abissolUserId,(int)($data['external_emitter_id']??0),(int)($data['external_responsible_id']??0))) throw new RuntimeException('Emisor no autorizado.');
        $data['external_source']='externa_alp';$data['metadata']=['is_test'=>true];
        if (!preg_match('/^alp-prueba-[a-f0-9-]{36}$/',$data['external_reference']??'')) throw new RuntimeException('Referencia de prueba inválida.');
        $result=pilot_request('POST','/emissions',$data);
    } elseif ($action==='resend') {
        $record=pilot_record($payload['emission_id']??0);
        $result=pilot_request('POST','/emissions/'.$record['id'].'/resend',['email'=>true]);
    } elseif ($action==='file') {
        $record=pilot_record($_GET['emission']??0);$kind=$_GET['kind']??'letter';
        if (!in_array($kind,['letter','PDF','Ticket','XML','ZIP'],true)) throw new RuntimeException('Archivo inválido.');
        $path=$kind==='letter'?'/emissions/'.$record['id'].'/letter':'/billing/'.(int)$record['invoice_id'].'/file/'.$kind;
        $body=pilot_request('GET',$path,null,true);
        $extension=$kind==='XML'?'xml':($kind==='ZIP'?'zip':'pdf');
        header('Content-Type: '.($extension==='pdf'?'application/pdf':($extension==='xml'?'application/xml':'application/zip')));
        header('Content-Disposition: inline; filename="PRUEBA-'.$kind.'.'.$extension.'"');echo $body;exit;
    } else { http_response_code(404);exit; }
    echo json_encode($result,JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
} catch(Throwable $error) {
    http_response_code(422);echo json_encode(['error'=>$error->getMessage()]);
}
