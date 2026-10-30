<?php
declare(strict_types=1);
function samsungTvCommands(): array {
    return ['volume_up'=>'Volume up', 'volume_down'=>'Volume down', 'mute'=>'Toggle mute', 'home'=>'Home', 'source'=>'Source menu', 'up'=>'Up', 'down'=>'Down', 'left'=>'Left', 'right'=>'Right', 'enter'=>'OK', 'back'=>'Back', 'play'=>'Play', 'pause'=>'Pause', 'power_off'=>'Power off'];
}

function samsungOutputXml(array $devices, array $options, string $base, string $folder, string $token): string {
    $e = function ($v) { return htmlspecialchars((string)$v, ENT_XML1 | ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); };
    $xml = '<?xml version="1.0" encoding="utf-8"?>' . "\n";
    $xml .= '<VirtualOut Title="Samsung Local controls" Address="' . $e($base) . '" CmdSep="" CloseAfterSend="true">' . "\n";
    $labels = ['start'=>'Start or resume', 'pause'=>'Pause', 'stop'=>'Stop cycle', 'wrinkle_on'=>'Wrinkle prevention on', 'wrinkle_off'=>'Wrinkle prevention off'];
    $index = 0;
    foreach ($devices as $id => $d) {
        $tv = ($d['kind'] ?? '') === 'television';
        if ((!$tv && ($d['kind'] ?? '') !== 'dryer') || ($tv && empty($d['tv_paired'])) || empty($d['control_available']) || empty($options[$id]['control']) || !preg_match('/^[a-z0-9-]{1,80}$/D', (string)$id)) continue;
        foreach (($tv ? samsungTvCommands() : $labels) as $operation => $label) {
            if (strpos($operation, 'wrinkle_') === 0 && !in_array('/washer/vs/0', $d['resources'] ?? [], true)) continue;
            $body = http_build_query(['token'=>$token, 'device'=>$id, 'operation'=>$operation] + ($tv ? ['profile'=>'tv'] : []), '', '&', PHP_QUERY_RFC3986);
            $comment = $tv ? 'Pulse only; no repeats. Mute toggles; source opens menu. Sent is not verified execution.' : 'Pulse only. Smart Control on, child lock off. Accepted is not verified execution.';
            $xml .= '<VirtualOutCmd ID="' . $index++ . '" Title="' . $e(($d['name'] ?? 'Dryer') . ': ' . $label) . '" Comment="' . $e($comment) . '" CmdOnMethod="POST" CmdOn="/plugins/' . $e(rawurlencode($folder)) . '/control.php" CmdOnHTTP="Content-Type: application/x-www-form-urlencoded" CmdOnPost="' . $e($body) . '" CmdOffMethod="GET" CmdOff="" CmdOffHTTP="" CmdOffPost="" Analog="false" Repeat="0" RepeatRate="0"/>' . "\n";
        }
    }
    if (!$index) throw new InvalidArgumentException('Enable controls for a supported dryer or paired TV first.');
    return $xml . "</VirtualOut>\n";
}
