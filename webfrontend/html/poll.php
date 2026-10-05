<?php
declare(strict_types=1);
require_once 'loxberry_system.php';
header('Content-Type: text/plain; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');
$auth = json_decode((string)@file_get_contents("$lbpconfigdir/http-poll.json"), true);
$token = $_GET['token'] ?? '';
if (!is_string($token) || !preg_match('/^[a-f0-9]{64}$/D', (string)($auth['token'] ?? '')) || !hash_equals($auth['token'], $token)) {
    http_response_code(403);
    exit('Forbidden');
}
require_once "$lbpbindir/loxone_http.php";
$status = json_decode((string)@file_get_contents("$lbpdatadir/status.json"), true);
echo samsungHttpBody(samsungHttpRows(is_array($status) ? $status : [], time()));
