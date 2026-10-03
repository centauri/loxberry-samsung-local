<?php
declare(strict_types=1);
// English source strings are the fallback. Translate only UI text, never payloads.
$uiSettings = readObject("$lbpconfigdir/settings.json");
$uiLanguage = ($uiSettings['language'] ?? 'en') === 'nl' ? 'nl' : 'en';
$uiTranslations = $uiLanguage === 'nl' ? array_merge(readObject(__DIR__ . '/lang/nl.json'), readObject(__DIR__ . '/lang/nl-status.json')) : [];
function t(string $text): string {
    global $uiTranslations;
    if (isset($uiTranslations[$text])) return $uiTranslations[$text];
    foreach (['Connection/read failed: ', 'Read-only compatibility test inconclusive: '] as $prefix) {
        // LoxBerry hosts may still use PHP 7.4; avoid PHP 8-only helpers.
        if (strncmp($text, $prefix, strlen($prefix)) === 0) {
            $rest = substr($text, strlen($prefix));
            $suffix = '. No automatic retry; check connectivity before trying again.';
            if (substr($rest, -strlen($suffix)) === $suffix) {
                $rest = substr($rest, 0, -strlen($suffix)) . ($uiTranslations[$suffix] ?? $suffix);
            }
            return ($uiTranslations[$prefix] ?? $prefix) . $rest;
        }
    }
    return $text;
}
