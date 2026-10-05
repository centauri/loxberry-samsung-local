<?php
declare(strict_types=1);
require_once 'loxberry_system.php';
require_once 'loxberry_web.php';

ini_set('session.use_strict_mode', '1');
session_name('samsunglocal');
session_set_cookie_params(['httponly' => true, 'samesite' => 'Strict',
    'secure' => !empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off']);
session_start();
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: SAMEORIGIN');
$_SESSION['csrf'] = $_SESSION['csrf'] ?? bin2hex(random_bytes(32));

function h($value): string {
    return htmlspecialchars((string)$value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}
function readObject(string $path): array {
    if (!is_file($path)) return [];
    $value = json_decode((string)file_get_contents($path), true);
    return is_array($value) ? $value : [];
}
function csrf(): void {
    echo '<input data-role="none" type="hidden" name="csrf" value="' . h($_SESSION['csrf']) . '">';
}
function perform(array $request): array {
    global $lbpbindir, $lbpconfigdir, $lbpdatadir, $lbplogdir;
    $command = ["$lbpdatadir/venv/bin/python", '-m', 'samsung_local', 'admin',
        '--config', $lbpconfigdir, '--data', $lbpdatadir, '--log', $lbplogdir];
    $pipes = [];
    $process = proc_open($command, [0 => ['pipe', 'r'], 1 => ['pipe', 'w'],
        2 => ['file', '/dev/null', 'a']], $pipes, $lbpbindir);
    if (!is_resource($process)) return ['ok' => false, 'message' => 'The plugin environment is unavailable. Check the installation log.'];
    fwrite($pipes[0], json_encode($request, JSON_THROW_ON_ERROR));
    fclose($pipes[0]);
    $output = stream_get_contents($pipes[1], 8192);
    fclose($pipes[1]);
    proc_close($process);
    return json_decode($output, true) ?: ['ok' => false, 'message' => 'The local helper could not complete the request.'];
}

require_once __DIR__ . '/i18n.php';
$notice = $_SESSION['notice'] ?? null;
unset($_SESSION['notice']);
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!isset($_POST['csrf']) || !is_string($_POST['csrf']) || !hash_equals($_SESSION['csrf'], $_POST['csrf'])) {
        http_response_code(403);
        exit(h(t('Your session expired. Reload the page and try again.')));
    }
    $action = $_POST['action'] ?? '';
    $request = ['action' => $action, 'device' => $_POST['device'] ?? ''];
    if ($action === 'language') {
        $request['language'] = $_POST['language'] ?? '';
    } elseif ($action === 'settings') {
        $request += ['enabled' => isset($_POST['enabled']),
            'poll_seconds' => (int)($_POST['poll_seconds'] ?? 30),
            'scan_seconds' => (int)($_POST['scan_seconds'] ?? 600),
            'networks' => preg_split('/[\s,]+/', trim((string)($_POST['networks'] ?? '')), -1, PREG_SPLIT_NO_EMPTY)];
    } elseif ($action === 'device') {
        $request += ['enabled' => isset($_POST['enabled']), 'control' => isset($_POST['control'])];
    } elseif ($action === 'import') {
        $request['credentials'] = ['mode' => $_POST['mode'] ?? '',
            'identity_hex' => trim((string)($_POST['identity_hex'] ?? '')),
            'key_hex' => trim((string)($_POST['key_hex'] ?? '')),
            'certificate' => trim((string)($_POST['certificate'] ?? '')),
            'key' => trim((string)($_POST['key'] ?? '')),
            'server_uuid' => trim((string)($_POST['server_uuid'] ?? ''))];
    }
    $_SESSION['notice'] = perform($request);
    header('Location: index.php', true, 303);
    exit;
}

$status = readObject("$lbpdatadir/status.json");
require_once __DIR__ . '/loxone_export.php';
$topicRows = samsungTopicRows($status);
require_once "$lbpbindir/loxone_http.php";
if (in_array($_GET['download'] ?? '', ['http-xml', 'outputs-xml'], true)) {
    $outputs = $_GET['download'] === 'outputs-xml';
    $auth = readObject($lbpconfigdir . ($outputs ? '/http-control.json' : '/http-poll.json'));
    $base = rtrim((string)($_GET['base_url'] ?? ''), '/');
    $url = parse_url($base);
    if (!$url || !in_array($url['scheme'] ?? '', ['http', 'https'], true) || empty($url['host']) || isset($url['user']) || isset($url['pass']) || isset($url['query']) || isset($url['fragment']) || !empty($url['path']) || preg_match('/[\x00-\x20<>"\\\\]/', $base)) {
        http_response_code(400); exit(h(t('Enter the LoxBerry base URL, for example http://loxberry.')));
    }
    if (!preg_match('/^[a-f0-9]{64}$/D', (string)($auth['token'] ?? ''))) {
        http_response_code(503); exit(h(t('Reinstall the updated plugin to initialize HTTP polling.')));
    }
    $folder = basename($lbpconfigdir);
    if ($outputs) {
        require_once "$lbpbindir/loxone_outputs.php";
        try {
            $xml = samsungOutputXml($status['devices'] ?? [], readObject("$lbpconfigdir/settings.json")['devices'] ?? [], $base, $folder, $auth['token']);
        } catch (InvalidArgumentException $ex) {
            http_response_code(409); exit(h(t($ex->getMessage())));
        }
        header('Content-Type: application/xml; charset=utf-8');
        header('Content-Disposition: attachment; filename="samsung-local-outputs.xml"');
        echo $xml;
        exit;
    }
    $address = $base . '/plugins/' . rawurlencode($folder) . '/poll.php?token=' . $auth['token'];
    header('Content-Type: application/xml; charset=utf-8');
    header('Content-Disposition: attachment; filename="samsung-local-http-inputs.xml"');
    echo samsungHttpXml(samsungHttpRows($status, time()), $address);
    exit;
}
if (($_GET['download'] ?? '') === 'topics-csv') {
    header('Content-Type: text/csv; charset=utf-8');
    header('Content-Disposition: attachment; filename="samsung-local-mqtt-topics.csv"');
    echo samsungTopicsCsv($topicRows);
    exit;
}

if (($_GET['download'] ?? '') === 'diagnostics') {
    if (!isset($status['support_report'])) { http_response_code(503); exit(h(t('Start the updated service before exporting diagnostics.'))); }
    header('Content-Type: application/json');
    header('Content-Disposition: attachment; filename="samsung-local-diagnostics.json"');
    echo json_encode($status['support_report'], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
    exit;
}
$settings = readObject("$lbpconfigdir/settings.json");
$fresh = isset($status['heartbeat']) && time() - $status['heartbeat'] < 30;
$devices = $status['devices'] ?? [];
$online = count(array_filter($devices, fn($d) => ($d['status'] ?? '') === 'online'));
// Feature detection also handles earlier LoxBerry 4 builds without the design system.
$hasDesignSystem = defined('LBSHTMLDIR') && is_file(LBSHTMLDIR . '/css/components.css') && is_file(LBSHTMLDIR . '/css/design-tokens.css');
LBWeb::lbheader('Samsung Local', '', '', $hasDesignSystem);
?>
<link rel="stylesheet" href="samsung-local.css?v=0.2.3">
<main lang="<?=h($uiLanguage)?>" class="sl lb-content <?=$hasDesignSystem ? 'sl-themed' : 'sl-legacy'?>" data-enhance="false">
<div class="sl-toolbar"><p class="sl-version">Samsung Local · <?=h(t((string)($status['version'] ?? 'Version unavailable')))?></p><a data-role="none" class="lb-btn" href="index.php"><?=h(t('Refresh status'))?></a></div>
<?php if ($notice): ?><p class="sl-notice" role="status"><?=h(t((string)($notice['message'] ?? '')))?></p><?php endif; ?>
<dl class="sl-status" aria-label="<?=h(t('Service status'))?>">
<div><dt><?=h(t('Service'))?></dt><dd><?=h(t($fresh ? (!empty($status['enabled']) ? 'Running' : 'Paused') : 'Not responding'))?></dd></div>
<div><dt>MQTT</dt><dd><?=h(t($fresh && !empty($status['mqtt_connected']) ? 'Connected' : 'Disconnected'))?></dd></div>
<div><dt><?=h(t('Appliances'))?></dt><dd><?=$fresh ? $online : 0?> <?=h(t('online /'))?> <?=count($devices)?></dd></div>
</dl>
<p class="sl-help"><?=h(!empty($status['scanning']) && $fresh ? t('Discovery in progress.') : sprintf(t('Automatic discovery every %s seconds.'), $settings['scan_seconds'] ?? 600))?> <?=h(t('MQTT settings come from LoxBerry. Status updates on page refresh.'))?></p>
<details id="loxone-export"><summary><?=h(t('Loxone input export'))?></summary>
<p><?=h(t('Import this XML using Virtual HTTP Input Templates in Loxone Config, then add the imported template to your project. The Miniserver polls this adapter every 30 seconds. MQTT remains available separately.'))?></p>
<form method="get"><input type="hidden" name="download" value="http-xml"><label><?=h(t('LoxBerry base URL reachable from the Miniserver'))?> <input data-role="none" type="url" name="base_url" required value="<?=h((!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off' ? 'https://' : 'http://') . ($_SERVER['HTTP_HOST'] ?? 'loxberry'))?>"></label><button data-role="none" class="lb-btn" type="submit"><?=h(t('Download HTTP inputs (XML)'))?></button></form>
<p class="sl-help"><?=h(t('The XML contains a private read-only access token. Keep it private. It imports numeric readings, availability (0=no, 1=yes), remaining time in seconds and supported state codes. Other text readings remain available through MQTT. Repeated imports may create duplicates.'))?></p>
<p class="sl-help"><?=h(t('State codes: -1=unknown, 0=ready, 1=running, 2=paused, 3=finished, 4=off, 5=idle, 6=error, 7=stopped. Check service and device availability and the HTTP input error output before using readings.'))?></p>
<p class="sl-help"><?=h(t('Wrinkle prevention: 0=off, 1=on, -1=unknown. Export a new XML to include newly supported inputs; existing imports do not gain inputs automatically.'))?></p>
<form method="get"><input type="hidden" name="download" value="outputs-xml"><label><?=h(t('LoxBerry base URL reachable from the Miniserver'))?> <input data-role="none" type="url" name="base_url" required value="<?=h((!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off' ? 'https://' : 'http://') . ($_SERVER['HTTP_HOST'] ?? 'loxberry'))?>"></label><button data-role="none" class="lb-btn" type="submit"><?=h(t('Download dryer outputs (XML)'))?></button></form>
<p><?=h(t('Enable controls on the dryer below before exporting outputs. Import under Virtual Output Templates. Use short pulses, with repeat disabled. The output XML contains a separate control token: keep it private. Start/Pause/Stop and wrinkle prevention require Smart Control on, child lock off and a powered, online dryer. Confirm execution from the readings.'))?></p>
<p><?=h(t('Keep MQTT Gateway HTTP forwarding enabled for your Miniserver and subscribe to samsunglocal/#. Use the exact HTTP virtual input names in the CSV: numeric values use ordinary virtual inputs with Digital input disabled; text values use virtual text inputs. These are not HTTP polling inputs.'))?></p>
<p><a data-role="none" class="lb-btn" href="?download=topics-csv"><?=h(t('Download all MQTT topics (CSV)'))?></a></p>
<p class="sl-help"><?=h(t('The CSV is a naming reference, not a Loxone import template. It includes known scalar readings and bridge/device availability. Check availability before using retained readings. Gateway custom value conversions may change the received type.'))?></p>
</details>
<details id="help"><summary><?=h(t('Help and support'))?></summary>
<h3><?=h(t('Getting started'))?></h3>
<p><?=h(t('Keep the appliance powered and connected to your LAN, then select Discover now. Supported appliances are checked automatically. On a routed VLAN, add the subnet under Advanced discovery networks and allow discovery and the advertised UDP secure port between LoxBerry and that network. MQTT uses your existing LoxBerry settings.'))?></p>
<h3><?=h(t('Understanding status'))?></h3>
<ul><li><strong><?=h(t('Online:'))?></strong> <?=h(t('the adapter successfully read mapped appliance values.'))?></li>
<li><strong><?=h(t('Auth required:'))?></strong> <?=h(t('access is not established. Read the device message; a read-only compatibility test may be available. Import only credentials the appliance already accepts.'))?></li>
<li><strong><?=h(t('Unsupported:'))?></strong> <?=h(t('read the reason. A skipped TV profile differs from an appliance that connects but has unmapped resources.'))?></li>
<li><strong><?=h(t('Offline or stale:'))?></strong> <?=h(t('check appliance power, network access and the service heartbeat. Retained MQTT readings may be old.'))?></li></ul>
<p><?=h(t('MQTT Connected confirms the bridge connection, not appliance access. In Loxone, check both bridge and appliance availability before using retained readings. Discovery alone does not prove authentication or readable capabilities.'))?></p>
<h3><?=h(t('Collect a useful report'))?></h3>
<ol><li><?=h(t('Open the affected device\'s Export device compatibility report.'))?></li>
<li><?=h(t('Review its collection reason and resource data. A discovery-only report cannot show which appliance capabilities work.'))?></li>
<li><?=h(t('Check all values for personal information, then download the report. Nothing is uploaded automatically.'))?></li>
<li><?=h(t('In your issue, include the retail model from the product label, adapter and LoxBerry versions, expected behavior, actual behavior and the appliance state when tested. Do not include its serial number or credentials.'))?></li></ol>
<p><?=h(t('The dashboard friendly name is deliberately omitted from reports because users can rename devices with personal information. A displayed name such as Samsung Q90 Series is not necessarily the full retail model. The fleet support report is a brief service summary; use the per-device report for capability investigation.'))?></p>
<h3><?=h(t('Choose the right support location'))?></h3><p><a data-role="none" href="https://github.com/centauri/loxberry-samsung-local/issues">Samsung Local — GitHub</a></p>
<ul><li><strong><?=h(t('Installation, updates, discovery, MQTT, UI or a capability already supported by LocalThings:'))?></strong> <?=h(t('use this adapter\'s GitHub repository.'))?></li>
<li><strong><?=h(t('A new shared appliance capability:'))?></strong> <?=h(t('search'))?> <a data-role="none" href="https://github.com/mbillow/localthings/issues"><?=h(t('LocalThings issues'))?></a><?=h(t(', then use its Device support / capability gap template if appropriate. Identify the JSON as a partial LoxBerry adapter capture.'))?></li>
<li><strong><?=h(t('Protocol/authentication:'))?></strong> <?=h(t('search'))?> <a data-role="none" href="https://github.com/QuiteYellow/SmartThings-Local/issues"><?=h(t('SmartThings-Local issues'))?></a><?=h(t('. If unsure whether the adapter or library is responsible, start in the adapter repository.'))?></li>
<li><strong><?=h(t('TV/audio profiles:'))?></strong> <?=h(t('this adapter currently skips their appliance connection. Start with adapter scope or a TV-specific integration; an empty TV capture is not evidence of missing LocalThings appliance mappings.'))?></li></ul>
<p><?=h(t('Search existing issues and link related reports rather than posting duplicates. Upstream acceptance of adapter reports is not yet confirmed.'))?></p>
<h3><?=h(t('How fixes reach your adapter'))?></h3>
<p><?=h(t('Maintainers can replay community JSON offline, add regression tests and adapt reviewed upstream fixes. Install the resulting adapter update to receive support. Diagnostic JSON is evidence, not a driver to import into a running plugin. Updates should preserve your settings and credentials; back up LoxBerry before updating.'))?></p>
</details>
<?php foreach (['mqtt_error', 'discovery_error', 'config_error'] as $error): if (!empty($status[$error])): ?><p class="sl-notice"><?=h(t((string)($status[$error])))?></p><?php endif; endforeach; ?>
<?php if (!$fresh): ?><p class="sl-notice"><?=h(t('No recent heartbeat. Check the installation log and the service journal. Displayed appliance data may be stale.'))?></p><?php endif; ?>
<section aria-labelledby="appliances-title"><h2 id="appliances-title" class="lb-section-title"><?=h(t('Appliances'))?></h2><div class="sl-toolbar"><a data-role="none" href="?download=diagnostics"><?=h(t('Download support report'))?></a><form method="post"><?php csrf(); ?><input data-role="none" type="hidden" name="action" value="scan"><button data-role="none" type="submit" class="lb-btn"><?=h(t('Discover now'))?></button></form></div>
<?php if (!$devices): ?><p><?=h(t('No appliances discovered yet. The first scan and automatic read-only compatibility check can take a few minutes. Keep appliances powered and connected to the same LAN.'))?></p><p class="sl-help"><?=h(t('For a routed VLAN, specify its network below and allow UDP discovery and the appliance’s advertised secure port. IPv6-only and cloud-only devices are not supported in this version.'))?></p><?php endif; ?>
<?php foreach ($devices as $key => $device): $options = $settings['devices'][$key] ?? []; $isMedia = in_array($device['kind'] ?? '', ['television', 'network_audio'], true); ?>
<article class="sl-appliance"><div class="sl-toolbar"><div><h3><?=h($device['name'] ?? 'Samsung appliance')?></h3><small><?=h(t((string)($device['kind'] ?? 'Type not yet identified')))?> · <?=h($device['model'] ?? '')?></small></div><span class="sl-device-status"><?=h(t('Status:'))?> <?=h(t($fresh ? str_replace('_', ' ', $device['status'] ?? 'discovered') : 'stale'))?></span></div>
<p><?=h(t((string)($device['diagnostic'] ?? '')))?></p>
<?php if (!empty($device['last_command'])): ?><p><?=h(t('Last command result:'))?> <?=h($device['last_command']['result'] ?? '')?> · <?=h(gmdate('Y-m-d H:i:s', (int)($device['last_command']['at'] ?? 0)))?> UTC</p><?php endif; ?>
<?php if ($isMedia && !empty($device['media_inventory'])): ?><details><summary><?=h(t('TV/audio public inventory'))?></summary><p><?=h(t('Public identity and advertised paths only. This does not prove authentication, readable TV state or remote-control support.'))?></p><pre><?=h(json_encode($device['media_inventory'], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES))?></pre><p><a data-role="none" href="https://github.com/QuiteYellow/SmartThings-Local/blob/main/docs/ocf-vd-devices.md"><?=h(t('Upstream TV/audio findings'))?></a></p></details><?php endif; ?>
<?php if (empty($device['samsung'])): ?><p class="sl-notice"><?=h(t('OCF candidate found, but Samsung manufacturer information is unavailable. No authentication attempted.'))?></p><?php endif; ?>
<p class="sl-help"><?=h(t('Address'))?> <?=h($device['host'] ?? '')?> <?=h(t('· secure port'))?> <?=h(t((string)($device['secure_port'] ?? 'not advertised or ambiguous')))?> <?=h(t('· last successful read'))?> <?=isset($device['last_success']) ? h(gmdate('Y-m-d H:i:s', (int)$device['last_success'])) . ' UTC' : h(t('not yet'))?></p>
<form method="post"><?php csrf(); ?><input data-role="none" type="hidden" name="action" value="device"><input data-role="none" type="hidden" name="device" value="<?=h($key)?>">
<label><input data-role="none" type="checkbox" name="enabled" <?=($options['enabled'] ?? true) ? 'checked' : ''?>><?=h(t('Read this appliance automatically'))?></label>
<?php if (!empty($device['control_available'])): ?><label><input data-role="none" type="checkbox" name="control" <?=!empty($options['control']) ? 'checked' : ''?>><?=h(t('Allow supported controls for this appliance'))?></label><small><?=h(t('Dryer HTTP controls require Smart Control on and child lock off. MQTT power control is limited to air conditioners and air purifiers.'))?></small><?php endif; ?>
<button data-role="none" type="submit" class="lb-btn lb-btn-primary"><?=h(t('Save appliance'))?></button></form>
<details><summary><?=h(t('Readings and MQTT topics'))?></summary><p><?=h(t('Base topic:'))?> <code><?=h(($status['topic_prefix'] ?? '') . '/' . $key)?></code></p>
<p class="sl-help"><?=h(t('Check both bridge and appliance availability before using retained readings.'))?></p>
<table class="lb-table"><caption class="sl-sr-only"><?=h(t('Appliance readings and MQTT topic suffixes'))?></caption><thead><tr><th scope="col"><?=h(t('Reading / topic suffix'))?></th><th scope="col"><?=h(t('Value'))?></th><th scope="col"><?=h(t('Unit'))?></th></tr></thead><tbody>
<?php foreach (($device['state'] ?? []) as $name => $value): ?><tr><td><code>state/<?=h($name)?></code></td><td><?=h(is_scalar($value) ? $value : '')?></td><td><?=h($device['sensors'][$name]['unit'] ?? '')?></td></tr><?php endforeach; ?>
</tbody></table></details>
<details><summary><?=h(t('Export device compatibility report'))?></summary>
<?php if ($isMedia): ?><p class="sl-notice"><?=h(t('Discovery-only report: this TV/audio profile is outside the adapter\'s appliance support. No appliance connection was attempted by this profile. The report cannot establish TV authentication or control support.'))?></p><?php endif; ?>
<p class="sl-help"><?=h(t('Friendly names are omitted for privacy. Include the retail model separately when requesting support. See'))?> <a data-role="none" href="#help"><?=h(t('Help and support'))?></a> <?=h(t('for report guidance.'))?></p>
<p><?=h(t('Review this report before sharing it. It includes redacted resource values, unknown fields, model/firmware and appliance state in the LocalThings resource format. Automatic redaction cannot recognize every personal value. Remove anything you do not want public. Exporting does not contact the appliance or upload anything.'))?></p>
<?php $compatReport = $status['compatibility_reports'][$key] ?? null; $reportId = 'compat-' . substr(hash('sha256', (string)$key), 0, 16); ?>
<?php if (is_array($compatReport)): ?>
<pre><?=h(json_encode($compatReport, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES))?></pre>
<script type="application/json" id="<?=h($reportId)?>"><?=json_encode($compatReport, JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT | JSON_PRETTY_PRINT)?></script>
<button data-role="none" type="button" class="lb-btn" data-compat-report="<?=h($reportId)?>"><?=h(t('Download this report'))?></button>
<?php if ($isMedia): ?><p class="sl-help"><?=h(t('Ask in the adapter repository about TV support or use a TV-specific integration. This report has no appliance resource capture to submit as a LocalThings mapping gap.'))?></p><?php else: ?>
<p class="sl-help"><?=h(t('Missing appliance capabilities: search'))?> <a data-role="none" href="https://github.com/mbillow/localthings/issues"><?=h(t('LocalThings issues'))?></a> <?=h(t('first. If this is a new shared capability gap, use its Device support / capability gap template and explain that this partial report comes from the LoxBerry adapter, not Home Assistant. Existing LocalThings support missing here is an adapter issue.'))?></p>
<p class="sl-help"><?=h(t('Protocol/authentication research: search'))?> <a data-role="none" href="https://github.com/QuiteYellow/SmartThings-Local/issues"><?=h(t('SmartThings-Local issues'))?></a><?=h(t('. Installation, discovery, MQTT and adapter-only problems belong in the adapter repository. Include versions and link related issues; avoid duplicate reports. Upstream acceptance of adapter reports is not yet confirmed.'))?></p>
<?php endif; ?>
<?php else: ?><p><?=h(t('No compatibility report yet. Refresh after the updated service starts.'))?></p><?php endif; ?>
</details>
<?php if (!empty($device['resource_diagnostics'])): ?>
<details><summary><?=h(t('Resource diagnostics'))?></summary><p><?=h(t('Log reference:'))?> <code><?=h(substr(hash('sha256', (string)$key), 0, 10))?></code></p><p><?=h(t('Read response codes, sizes and supported paths only. No private keys or raw appliance payloads.'))?></p><pre><?=h(json_encode($device['resource_diagnostics'], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES))?></pre></details>
<?php endif; ?>
<?php if (!$isMedia && in_array($device['status'] ?? '', ['auth_required', 'identity_mismatch', 'identity_conflict', 'unsupported'], true) && (($device['status'] ?? '') !== 'auth_required' || is_file($lbpconfigdir . '/credentials/' . $key . '.json'))): ?>
<form method="post"><?php csrf(); ?><input data-role="none" type="hidden" name="action" value="retry"><input data-role="none" type="hidden" name="device" value="<?=h($key)?>"><button data-role="none" type="submit" class="lb-btn"><?=h(t('Retry connection'))?></button></form>
<?php endif; ?>
<?php if (!$isMedia && in_array($device['status'] ?? '', ['auth_required', 'unsupported'], true)): ?>
<?php if (!is_file($lbpconfigdir . '/credentials/' . $key . '.json')): ?>
<p><?=h(t('A public ownership-method advertisement alone does not prove that this certificate will be rejected. You can run one read-only connection test. It does not change ownership, security resources or appliance settings.'))?></p>
<form method="post"><?php csrf(); ?><input data-role="none" type="hidden" name="action" value="compatibility"><input data-role="none" type="hidden" name="device" value="<?=h($key)?>"><button data-role="none" type="submit" class="lb-btn"><?=h(t('Test certificate compatibility (read-only)'))?></button></form>
<?php endif; ?>
<?php endif; ?>
<?php if (($device['status'] ?? '') === 'auth_required'): ?>
<details><summary><?=h(t('Advanced: import existing credentials'))?></summary>
<p><?=h(t('If this firmware requires a different credential, import one it already accepts. Importing stores them locally; it does not provision, reset, take ownership of, or alter security resources on the appliance. A legacy self-signed certificate cannot solve newer OCF-PKI authorization.'))?></p>
<p class="sl-help"><?=h(t('Use HTTPS for the LoxBerry web interface when importing secrets. Fields are never filled back into this page.'))?></p>
<form method="post" autocomplete="off"><?php csrf(); ?><input data-role="none" type="hidden" name="action" value="import"><input data-role="none" type="hidden" name="device" value="<?=h($key)?>">
<label><?=h(t('Credential type'))?><select data-role="none" class="lb-select" name="mode"><option value="psk"><?=h(t('Existing OCF PSK'))?></option><option value="certificate"><?=h(t('Existing client certificate and private key'))?></option></select></label>
<label><?=h(t('PSK identity — raw 16-byte UUID, 32 hex characters without NUL bytes'))?><input data-role="none" class="lb-input" type="text" name="identity_hex" maxlength="32" autocomplete="off"></label>
<label><?=h(t('PSK key — 32 or 64 hex characters'))?><input data-role="none" class="lb-input" type="password" name="key_hex" maxlength="64" autocomplete="new-password"></label>
<label><?=h(t('Certificate chain — PEM'))?><textarea data-role="none" class="lb-textarea" name="certificate" maxlength="65536" spellcheck="false"></textarea></label>
<label><?=h(t('Private key — unencrypted PEM'))?><textarea data-role="none" class="lb-textarea" name="key" maxlength="16384" spellcheck="false"></textarea></label>
<label><?=h(t('Samsung server certificate UUID (optional for imported certificate)'))?><input data-role="none" class="lb-input" type="text" name="server_uuid" maxlength="36"></label>
<small><?=h(t('A server certificate UUID is a separately verified hardware identity, which may differ from the OCF device ID. Supplying it enables upstream Samsung server verification.'))?></small><p><button data-role="none" type="submit" class="lb-btn"><?=h(t('Import and retry'))?></button></p></form></details>
<?php endif; ?>
</article><?php endforeach; ?></section>
<section aria-labelledby="settings-title"><h2 id="settings-title" class="lb-section-title"><?=h(t('Settings'))?></h2><form method="post" class="sl-toolbar"><?php csrf(); ?><input data-role="none" type="hidden" name="action" value="language"><label for="ui-language"><?=h(t('Language'))?></label><select id="ui-language" data-role="none" class="lb-select" name="language"><option value="en" <?=$uiLanguage === 'en' ? 'selected' : ''?>>English</option><option value="nl" <?=$uiLanguage === 'nl' ? 'selected' : ''?>>Nederlands</option></select><button data-role="none" class="lb-btn" type="submit"><?=h(t('Apply language'))?></button></form>
<form method="post"><?php csrf(); ?><input data-role="none" type="hidden" name="action" value="settings">
<label><input data-role="none" type="checkbox" name="enabled" <?=($settings['enabled'] ?? true) ? 'checked' : ''?>><?=h(t('Enable automatic discovery and appliance connections'))?></label>
<div class="sl-intervals"><label><?=h(t('Polling interval (seconds)'))?><input data-role="none" class="lb-input" type="number" name="poll_seconds" min="15" max="3600" value="<?=h($settings['poll_seconds'] ?? 30)?>"></label>
<label><?=h(t('Discovery interval (seconds)'))?><input data-role="none" class="lb-input" type="number" name="scan_seconds" min="120" max="86400" value="<?=h($settings['scan_seconds'] ?? 600)?>"></label></div>
<details><summary><?=h(t('Advanced discovery networks'))?></summary><label><?=h(t('Optional private IPv4 networks, separated by spaces'))?><input data-role="none" class="lb-input" type="text" name="networks" value="<?=h(implode(' ', $settings['networks'] ?? []))?>" placeholder="<?=h(t('Automatic connected-LAN discovery'))?>"></label><small><?=h(t('Blank uses connected networks. At most 1024 addresses, /22 or smaller. Large connected networks use multicast only unless narrowed here. No appliance IP or OCF port is required.'))?></small></details>
<button data-role="none" type="submit" class="lb-btn lb-btn-primary"><?=h(t('Save settings'))?></button></form></section>
<section aria-labelledby="log-title"><h2 id="log-title" class="lb-section-title"><?=h(t('Recent service log'))?></h2><p><?=h(t('Shows discovery results, connection changes and a health summary every 15 minutes. Successful polls are not logged individually. Refresh the page for new entries.'))?></p><p class="sl-help"><?=h(t('Logs rotate automatically. Private keys, PSKs and broker passwords are excluded.'))?></p><?php require_once __DIR__ . '/log_view.php'; $logView = samsungLogPage($lbplogdir, $_GET['logfile'] ?? 0, $_GET['logpage'] ?? 0); ?>
<p class="sl-help"><?=h(t('Rotation: about 1 MB per file, with three backups. Stored in the standard LoxBerry plugin log directory, normally RAM-backed. Pages show 16 KB from newest to oldest; lines may cross page boundaries. Active logs can change between requests.'))?></p>
<form method="get" action="index.php#log-title" class="sl-toolbar"><label><?=h(t('Log file'))?><select data-role="none" class="lb-select" name="logfile"><?php for ($n = 0; $n <= 3; $n++): ?><option value="<?=$n?>" <?=$logView['file'] === $n ? 'selected' : ''?>><?=h($n === 0 ? t('Current log') : sprintf(t('Backup %s'), $n))?></option><?php endfor; ?></select></label><button data-role="none" class="lb-btn" type="submit"><?=h(t('Show log'))?></button></form>
<nav class="sl-toolbar" aria-label="<?=h(t('Log pages'))?>">
<?php if ($logView['page'] > 0): ?><a data-role="none" href="?logfile=<?=$logView['file']?>&amp;logpage=<?=$logView['page'] - 1?>#log-title"><?=h(t('Newer'))?></a><?php endif; ?>
<span><?=h(sprintf(t('Page %s of %s'), $logView['pages'] ? $logView['page'] + 1 : 0, $logView['pages']))?></span>
<?php if ($logView['page'] + 1 < $logView['pages']): ?><a data-role="none" href="?logfile=<?=$logView['file']?>&amp;logpage=<?=$logView['page'] + 1?>#log-title"><?=h(t('Older'))?></a><?php endif; ?>
<a data-role="none" href="?logfile=<?=$logView['file']?>#log-title"><?=h(t('Latest entries'))?></a></nav>
<pre class="sl-log" tabindex="0" aria-label="<?=h(t('Recent service log'))?>"><?=h($logView['text'] !== '' ? $logView['text'] : t('No service log yet.'))?></pre></section>
</main>
<script>
document.querySelectorAll('a[href="#help"]').forEach(function(link) {
    link.addEventListener('click', function() { document.getElementById('help').open = true; });
});
document.querySelectorAll('[data-compat-report]').forEach(function(button) {
    button.addEventListener('click', function() {
        var report = document.getElementById(button.dataset.compatReport);
        var blob = new Blob([report.textContent], {type: 'application/json'});
        var url = URL.createObjectURL(blob);
        var link = document.createElement('a');
        link.href = url;
        link.download = 'samsung-local-compatibility.json';
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(function() { URL.revokeObjectURL(url); }, 1000);
    });
});
</script>
<?php LBWeb::lbfooter(); ?>
