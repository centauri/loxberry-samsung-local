<?php
declare(strict_types=1);
// Fixed filenames only: query parameters never become filesystem paths.
function samsungLogPage(string $directory, $requestedFile, $requestedPage): array {
    $file = filter_var($requestedFile, FILTER_VALIDATE_INT);
    $file = $file !== false && $file >= 0 && $file <= 3 ? $file : 0;
    $path = $directory . '/samsung-local.log' . ($file ? '.' . $file : '');
    $page = filter_var($requestedPage, FILTER_VALIDATE_INT);
    $page = $page !== false && $page >= 0 ? $page : 0;
    $stream = is_file($path) ? @fopen($path, 'rb') : false;
    if (!$stream) return ['file' => $file, 'page' => 0, 'pages' => 0, 'text' => ''];
    $size = (int)(fstat($stream)['size'] ?? 0);
    $chunk = 16384;
    $pages = max(1, (int)ceil($size / $chunk));
    $page = min($page, $pages - 1);
    $end = max(0, $size - $page * $chunk);
    $start = max(0, $end - $chunk);
    fseek($stream, $start);
    $text = $end > $start ? stream_get_contents($stream, $end - $start) : '';
    fclose($stream);
    return ['file' => $file, 'page' => $page, 'pages' => $pages, 'text' => $text];
}
