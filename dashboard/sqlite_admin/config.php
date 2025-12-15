<?php
/**
 * phpLiteAdmin Configuration
 * สำหรับ Transcription Service
 */

// Database directory (parent directory of database.db)
$directory = '/workspace/transcription-service/storage';

// Password protection (optional - แนะนำให้ตั้ง password)
$password = ''; // ใส่ password ตรงนี้ถ้าต้องการ (เช่น 'your_password_here')

// Allowed extensions
$allowed_extensions = array('db','db3','sqlite','sqlite3');

// Theme
$theme = 'phpliteadmin.css';

// Language
$language = 'en';

// Rows per page
$rowsNum = 30;

// Max rows for export
$maxrows = 1000;

// Max upload size (MB)
$max_upload_size = 10;
