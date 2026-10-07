<?php
declare(strict_types=1);
// Only invoked over stdin by FastAPI. Never exposed as an HTTP endpoint.
require __DIR__ . '/vendor/autoload.php';
$input = json_decode(stream_get_contents(STDIN, 2097152), true, 16, JSON_THROW_ON_ERROR);
if (!in_array($input['kind'] ?? '', ['welcome','invoice','ticket'], true)) {
    throw new RuntimeException('Invalid print format');
}
$options = new Dompdf\Options();
$options->set('isRemoteEnabled', false);
$options->set('isPhpEnabled', false);
$options->set('isJavascriptEnabled', false);
$options->set('chroot', __DIR__);
$options->set('defaultFont', 'Helvetica');
$cache = dirname(__DIR__) . '/storage/pdf_renderer';
if (!is_dir($cache) && !mkdir($cache, 0700, true)) { throw new RuntimeException('Print cache unavailable'); }
$options->set('fontCache', $cache);
$options->set('tempDir', $cache);
$pdf = new Dompdf\Dompdf($options);
$pdf->loadHtml($input['html'], 'UTF-8');
$pdf->setPaper($input['kind'] === 'ticket' ? [0, 0, 226.77, 2400] : 'a4', 'portrait');
$pdf->render();
fwrite(STDOUT, $pdf->output());
