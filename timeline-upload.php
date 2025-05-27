<?php
/**
 * server side:
 * upload request processor, taking desktop timeline uploads
 */
$API_KEY = '';
$DEST = '';
$FILE_NAME = 'timeline.png';
$MAX_SIZE = 1*1024*1024; // 1MB; how big you want for an 800*480 img???

// check folder & permission
if (!is_dir($DEST)) {
    http_response_code(500);
    exit(json_encode(['error' => "Directory does not exist: $DEST"]));
}

if (!is_writable($DEST)) {
    http_response_code(500);
    exit(json_encode(['error' => "Directory not writable: $DEST"]));
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    exit(json_encode(['error' => 'POST Method not allowed']));  
}

$auth_header = $_SERVER['HTTP_AUTHORIZATION'] ?? '';
if (!preg_match('/^Bearer (.+)$/', $auth_header, $matches)) {
    http_response_code(401);
    exit(json_encode(['error' => 'Auth header not found'])); 
}

// parse token
$tkn = $matches[1];
$pts = explode(':', $tkn);
if (count($pts) !== 2) {
    http_response_code(401);
    exit(json_encode(['error' => 'Invalid token'])); 
}
[$timestamp, $signiture] = $pts;

// verify
$answer = hash('sha256', $API_KEY . $timestamp);
if (!hash_equals($answer, $signiture)) {
    http_response_code(401);
    exit(json_encode(['error' => 'Verification failed'])); 
}

// examine upload
if (!isset($_FILES['file']) || $_FILES['file']['error'] !== UPLOAD_ERR_OK) {
    http_response_code(400);
    exit(json_encode(['error' => 'File failed to upload'])); 
}

$file = $_FILES['file'];
if ($file['size'] > $MAX_SIZE) {
    http_response_code(400);
    exit(json_encode(['error' => 'File oversize'])); 
}

$file_type = $file['type'];
if (empty($file_type)) {
    $file_type = mime_content_type($file['tmp_name']);
} // fallback

if (!in_array($file_type, ['image/png'])) {
    http_response_code(400);
    exit(json_encode(['error' => "File type mismatch; expected png, got {$file['type']}"])); 
}

// finally i can save it
$dest_file = $DEST . $FILE_NAME;
if (move_uploaded_file($file['tmp_name'], $dest_file)) {
    header('Content-Type: application/json');
    echo json_encode(['status' => 'success', 'file' => $FILE_NAME]);
} else {
    http_response_code(500);
    exit(json_encode(['error' => 'Failed to save file']));
}
?>
