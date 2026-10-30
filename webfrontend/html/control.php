<?php
declare(strict_types=1);
require_once 'loxberry_system.php';
header('Content-Type: application/json');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') { http_response_code(405); exit('{"ok":false}'); }
if ((int)($_SERVER['CONTENT_LENGTH'] ?? 0) > 2048) { http_response_code(413); exit('{"ok":false}'); }
$auth = json_decode((string)@file_get_contents("$lbpconfigdir/http-control.json"), true);
$token = $_POST['token'] ?? '';
if (!is_string($token) || !preg_match('/^[a-f0-9]{64}$/D', (string)($auth['token'] ?? '')) || !hash_equals($auth['token'], $token)) {
    http_response_code(403); exit('{"ok":false}');
}
$device = $_POST['device'] ?? '';
$operation = $_POST['operation'] ?? '';
$profile = $_POST['profile'] ?? 'dryer';
require_once "$lbpbindir/loxone_outputs.php";
$allowed = $profile === 'tv' ? array_keys(samsungTvCommands()) : ['start','pause','stop','wrinkle_on','wrinkle_off'];
if (!is_string($device) || !preg_match('/^[a-z0-9-]{1,80}$/D', $device) || !is_string($operation) || !in_array($profile, ['dryer','tv'], true) || !in_array($operation, $allowed, true)) {
    http_response_code(400); exit('{"ok":false}');
}
$process = proc_open(["$lbpdatadir/venv/bin/python", '-m', 'samsung_local', 'admin',
    '--config', $lbpconfigdir, '--data', $lbpdatadir, '--log', $lbplogdir],
    [0 => ['pipe','r'], 1 => ['pipe','w'], 2 => ['file','/dev/null','a']], $pipes, $lbpbindir);
if (!is_resource($process)) { http_response_code(503); exit('{"ok":false}'); }
fwrite($pipes[0], json_encode(['action'=>$profile === 'tv' ? 'tv_http_command' : 'dryer_command', 'device'=>$device, 'operation'=>$operation]));
fclose($pipes[0]);
$response = stream_get_contents($pipes[1], 8192);
fclose($pipes[1]);
proc_close($process);
$result = json_decode($response, true);
http_response_code(!empty($result['ok']) ? 202 : 409);
echo json_encode($result ?: ['ok'=>false]);
