<?php
declare(strict_types=1);

// Append-only public codebook: never change an existing numeric meaning.
function samsungHttpStates(): array {
    return ['ready' => 0, 'run' => 1, 'running' => 1, 'pause' => 2, 'paused' => 2,
        'finished' => 3, 'completed' => 3, 'complete' => 3, 'end' => 3,
        'off' => 4, 'idle' => 5, 'error' => 6, 'stopped' => 7, 'stop' => 7];
}

function samsungHttpRows(array $status, int $now): array {
    $heartbeat = (float)($status['heartbeat'] ?? 0);
    $fresh = $heartbeat <= $now + 5 && $heartbeat > $now - 30 && !empty($status['enabled']);
    $rows = [];
    $add = function ($source, $label, $value, $unit, $mapping) use (&$rows) {
        $id = 'sl_' . substr(hash('sha256', $source), 0, 24);
        $rows[$id] = ['label' => $label, 'value' => $value, 'unit' => $unit, 'mapping' => $mapping];
    };
    $add('bridge/availability', 'Samsung Local service available', (int)$fresh, '', '0=unavailable; 1=available');
    foreach (($status['devices'] ?? []) as $id => $device) {
        if (!preg_match('/^[A-Za-z0-9_-]+$/D', (string)$id) || !is_array($device)) continue;
        $label = (string)($device['name'] ?? $id) . ' [' . $id . ']';
        $online = $fresh && ($device['status'] ?? '') === 'online';
        $add($id . '/availability', $label . ' available', (int)$online, '', '0=unavailable; 1=available');
        if (($device['kind'] ?? '') === 'dryer') {
            $result = ['none'=>0, 'accepted'=>1, 'device_rejected'=>2, 'rejected'=>2, 'uncertain'=>3, 'busy'=>4, 'disabled_or_offline'=>2][$device['last_command']['result'] ?? 'none'] ?? -1;
            $add($id . '/command_result', $label . ' last command result', $result, '', '-1=unknown; 0=none; 1=device accepted (verify state); 2=rejected; 3=uncertain; 4=busy');
            $add($id . '/command_time', $label . ' last command Unix time', $device['last_command']['at'] ?? 0, 's', 'Timestamp of last command result; compare to request time');
        }
        foreach (($device['state'] ?? []) as $key => $value) {
            if (!preg_match('/^[A-Za-z0-9_-]+$/D', (string)$key)) continue;
            $unit = (string)($device['sensors'][$key]['unit'] ?? '');
            $mapping = 'Numeric reading';
            if (is_bool($value)) { $value = (int)$value; $mapping = '0=false; 1=true'; }
            elseif (is_string($value) && preg_match('/(?:^|_)currentMachineState$/i', $key)) {
                $value = ['active'=>1, 'pause'=>2, 'idle'=>5][strtolower(trim($value))] ?? -1;
                $mapping = '-1=unknown; 1=active; 2=paused; 5=idle'; $unit = '';
            }
            elseif (is_string($value) && preg_match('/(?:^|_)(?:progress|currentJobState)$/i', $key)) {
                $value = strtolower(trim($value)) === 'drying' ? 1 : -1;
                $mapping = '-1=unmapped phase; 1=drying'; $unit = '';
            }
            elseif (is_string($value) && preg_match('/(?:^|_)wrinklePrevent$/i', $key)) {
                $value = ['off' => 0, 'on' => 1][strtolower(trim($value))] ?? -1;
                $mapping = '-1=unknown; 0=wrinkle prevention off; 1=wrinkle prevention on';
                $unit = '';
            }
            elseif (is_string($value) && preg_match('/(?:^|_)state$/i', $key)) {
                $value = samsungHttpStates()[strtolower(trim($value))] ?? -1;
                $mapping = '-1=unknown; 0=ready; 1=running; 2=paused; 3=finished; 4=off; 5=idle; 6=error; 7=stopped';
                $unit = '';
            } elseif (is_string($value) && preg_match('/(?:remaining_?time|dryTime)$/i', $key)) {
                if (!preg_match('/^(\d{1,4}):([0-5]\d):([0-5]\d)$/D', $value, $parts)) continue;
                $value = (int)$parts[1] * 3600 + (int)$parts[2] * 60 + (int)$parts[3];
                $unit = 's'; $mapping = 'Duration in seconds';
            }
            if (!(is_int($value) || is_float($value)) || !is_finite((float)$value)) continue;
            // Retain the row in exports but never serve stale appliance readings.
            $add($id . '/state/' . $key, $label . ': ' . $key, $online ? $value : null, $unit, $mapping);
        }
    }
    return $rows;
}

function samsungHttpBody(array $rows): string {
    $body = '';
    foreach ($rows as $id => $row) {
        if ($row['value'] !== null) $body .= $id . '=' . json_encode($row['value'], JSON_THROW_ON_ERROR) . "\n";
    }
    return $body;
}

function samsungHttpXml(array $rows, string $address): string {
    $escape = function (string $s): string {
        $s = preg_replace('/[^\x{9}\x{A}\x{D}\x{20}-\x{D7FF}\x{E000}-\x{FFFD}\x{10000}-\x{10FFFF}]/u', '', $s) ?? '';
        return htmlspecialchars($s, ENT_XML1 | ENT_QUOTES, 'UTF-8');
    };
    $xml = '<?xml version="1.0" encoding="utf-8"?>' . "\n";
    $xml .= '<VirtualInHttp Title="Samsung Local HTTP" Address="' . $escape($address) . '" PollingTime="30" Comment="Use service and device availability before using readings. Read-only polling.">' . "\n";
    foreach ($rows as $id => $r) {
        $xml .= '<VirtualInHttpCmd Title="' . $escape($r['label']) . '" Comment="' . $escape($r['mapping'] . ($r['unit'] !== '' ? '; unit=' . $r['unit'] : '')) . '" Check="' . $id . '=\v" Signed="true" Analog="true" SourceValLow="0" DestValLow="0" SourceValHigh="100" DestValHigh="100" DefVal="0" MinVal="-1000000000000" MaxVal="1000000000000"/>' . "\n";
    }
    return $xml . "</VirtualInHttp>\n";
}
