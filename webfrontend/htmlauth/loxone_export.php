<?php
declare(strict_types=1);

function samsungTopicRows(array $status): array {
    $prefix = $status['topic_prefix'] ?? '';
    if (!is_string($prefix) || !preg_match('~^samsunglocal/[A-Za-z0-9_-]+$~D', $prefix)) return [];
    $rows = [[$prefix . '/bridge/availability', 'Bridge availability', 'text', '']];
    foreach (($status['devices'] ?? []) as $id => $device) {
        if (!preg_match('/^[A-Za-z0-9_-]+$/D', (string)$id)) continue;
        $base = $prefix . '/' . $id;
        $label = (string)($device['name'] ?? $id);
        $rows[] = [$base . '/availability', $label . ' availability', 'text', ''];
        foreach (($device['state'] ?? []) as $key => $value) {
            if (!preg_match('/^[A-Za-z0-9_-]+$/D', (string)$key) || !is_scalar($value)) continue;
            // Use actual JSON number types; numeric-looking text may be an enum or identifier.
            $numeric = is_int($value) || (is_float($value) && is_finite($value));
            $rows[] = [$base . '/state/' . $key, $label . ': ' . $key,
                $numeric ? 'number' : 'text', (string)($device['sensors'][$key]['unit'] ?? '')];
        }
    }
    return $rows;
}

function samsungTopicsCsv(array $rows): string {
    $stream = fopen('php://temp', 'r+');
    fputcsv($stream, ['MQTT topic', 'HTTP virtual input name', 'Description', 'Type', 'Unit'], ',', '"', '');
    foreach ($rows as $r) {
        $cells = [$r[0], str_replace(['/', ' ', '%'], '_', $r[0]), $r[1], $r[2], $r[3]];
        foreach ($cells as &$cell) {
            if (preg_match('/^[\s]*[=+@-]|^[\t\r\n]/', $cell)) $cell = "'" . $cell;
        }
        unset($cell);
        fputcsv($stream, $cells, ',', '"', '');
    }
    rewind($stream);
    $result = stream_get_contents($stream);
    fclose($stream);
    return $result;
}

