<?php
// Included inside a device card. Values are service snapshots, not broker acknowledgements.
$tvBase = ($status['topic_prefix'] ?? '') . '/' . $key;
$tvReady = $fresh && !empty($status['enabled']) && ($device['status'] ?? '') === 'online'
    && !empty($device['tv_paired']) && !empty($options['control']) && ($options['enabled'] ?? true);
$rows = [
    ['Power', 'state/power', $fresh && ($device['status'] ?? '') === 'online' ? ($device['state']['power'] ?? null) : null],
    ['Connection', 'availability', $fresh ? ($device['status'] === 'online' ? 'online' : 'offline') : 'stale'],
    ['Paired', 'remote/paired', $fresh ? (int)!empty($device['tv_paired']) : null],
    ['Controls enabled', 'remote/enabled', (int)!empty($options['control'])],
    ['Remote ready', 'remote/available', (int)$tvReady],
];
?>
<details class="sl-integration" data-copied="<?=h(t('Topic copied.'))?>" data-copy-failed="<?=h(t('Copy unavailable. Select the topic in Advanced MQTT commands.'))?>"><summary><?=h(t('Loxone and MQTT'))?></summary>
<p class="sl-help"><?=h(t('Live adapter values. Power: 1 = on, 0 = off, unknown when unreachable. Check bridge and device availability when using MQTT.'))?></p>
<table class="lb-table"><thead><tr><th><?=h(t('Reading'))?></th><th><?=h(t('Value'))?></th><th><?=h(t('MQTT topic'))?></th></tr></thead><tbody>
<?php foreach ($rows as [$label, $suffix, $value]): ?>
<tr><td><?=h(t($label))?></td><td><?=h($value === null ? t('Unknown') : (is_string($value) ? t($value) : $value))?></td><td><code><?=h($suffix)?></code> <button data-role="none" type="button" class="lb-btn" data-copy-text="<?=h($tvBase . '/' . $suffix)?>"><?=h(t('Copy topic'))?></button></td></tr>
<?php endforeach; ?></tbody></table>
<h4><?=h(t('Use in Loxone Config'))?></h4>
<form method="get" data-ajax="false">
<input type="hidden" name="download" value="outputs-xml"><input type="hidden" name="device" value="<?=h($key)?>">
<label><?=h(t('LoxBerry base URL reachable from the Miniserver'))?><input data-role="none" class="lb-input" name="base_url" type="url" required value="<?=h((!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off' ? 'https://' : 'http://') . ($_SERVER['HTTP_HOST'] ?? 'loxberry'))?>"></label>
<button data-role="none" type="submit" class="lb-btn" <?=empty($device['tv_paired']) || empty($options['control']) || empty($device['control_available']) ? 'disabled' : ''?>><?=h(t('Download TV outputs (XML)'))?></button></form>
<p><?=h(t('Pair and enable controls first. Import the XML as a Virtual Output template. Use pulses; disable repeats. The adapter generates command IDs and timestamps. The XML contains a private control token.'))?></p>
<p><a data-role="none" href="#loxone-export"><?=h(t('Export HTTP inputs or MQTT topic CSV'))?></a></p>
<details><summary><?=h(t('Advanced MQTT commands'))?></summary>
<p><?=h(t('Command topic'))?>: <code><?=h($tvBase . '/set/remote')?></code> <button data-role="none" type="button" class="lb-btn" data-copy-text="<?=h($tvBase . '/set/remote')?>"><?=h(t('Copy topic'))?></button></p>
<pre>{"id":"&lt;new UUID&gt;","timestamp":&lt;current Unix seconds&gt;,"value":"volume_up"}</pre>
<p><?=h(t('Generate the UUID and timestamp when sending. Commands expire after 30 seconds. Retain must be off. Duplicate IDs are ignored and commands are limited to one every three seconds. Pair the TV in this page first; pairing over MQTT is disabled.'))?></p>
<p><code>volume_up, volume_down, mute, home, source, up, down, left, right, enter, back, play, pause, power_off</code></p>
<p><?=h(t('Command results'))?>: <code><?=h($tvBase . '/command_result')?></code> <button data-role="none" type="button" class="lb-btn" data-copy-text="<?=h($tvBase . '/command_result')?>"><?=h(t('Copy topic'))?></button></p>
<p><?=h(t('sent_unconfirmed means sent, not verified. Mute toggles sound; source opens the source menu. Volume, mute and input feedback and power-on are not implemented.'))?></p>
</details></details>
