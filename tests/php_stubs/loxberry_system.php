<?php
// Test-only SDK facade. Never included in the installation ZIP.
$runtime = getenv('SAMSUNG_TEST_RUNTIME');
if (!$runtime) throw new RuntimeException('Test runtime missing');
$lbpconfigdir = "$runtime/config";
$lbpdatadir = "$runtime/data";
$lbplogdir = "$runtime/log";
$lbpbindir = dirname(__DIR__, 2) . '/bin';
$_SERVER['REQUEST_METHOD'] = 'GET';
if (getenv('SAMSUNG_TEST_SYSTEM_HTML')) define('LBSHTMLDIR', getenv('SAMSUNG_TEST_SYSTEM_HTML'));
