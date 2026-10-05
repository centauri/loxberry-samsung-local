<?php
declare(strict_types=1);
function samsungOutputXml(array $devices, array $options, string $base, string $folder, string $token): string {
    $e = function ($v) { return htmlspecialchars((string)$v, ENT_XML1 | ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); };
    $xml = '<?xml version="1.0" encoding="utf-8"?>' . "\n";
    $xml .= '<VirtualOut Title="Samsung Local dryer controls" Address="' . $e($base) . '" CmdSep="" CloseAfterSend="true">' . "\n";
    $labels = ['start'=>'Start or resume', 'pause'=>'Pause', 'stop'=>'Stop cycle', 'wrinkle_on'=>'Wrinkle prevention on', 'wrinkle_off'=>'Wrinkle prevention off'];
    $index = 0;
    foreach ($devices as $id => $d) {
        if (($d['kind'] ?? '') !== 'dryer' || empty($d['control_available']) || empty($options[$id]['control']) || !preg_match('/^[a-z0-9-]{1,80}$/D', (string)$id)) continue;
        foreach ($labels as $operation => $label) {
            if (strpos($operation, 'wrinkle_') === 0 && !in_array('/washer/vs/0', $d['resources'] ?? [], true)) continue;
            $body = http_build_query(['token'=>$token, 'device'=>$id, 'operation'=>$operation], '', '&', PHP_QUERY_RFC3986);
            $xml .= '<VirtualOutCmd ID="' . $index++ . '" Title="' . $e(($d['name'] ?? 'Dryer') . ': ' . $label) . '" Comment="Pulse only. Smart Control on, child lock off. Accepted is not verified execution." CmdOnMethod="POST" CmdOn="/plugins/' . $e(rawurlencode($folder)) . '/control.php" CmdOnHTTP="Content-Type: application/x-www-form-urlencoded" CmdOnPost="' . $e($body) . '" CmdOffMethod="GET" CmdOff="" CmdOffHTTP="" CmdOffPost="" Analog="false" Repeat="0" RepeatRate="0"/>' . "\n";
        }
    }
    if (!$index) throw new InvalidArgumentException('Enable controls for a supported dryer first.');
    return $xml . "</VirtualOut>\n";
}
