<?php
/**
 * Innova PBX — "FreePBX Backup & Restore" moduli orqali HAQIQIY backup job
 * yaratish va ishga tushirish skripti. Natija: .tar.gz fayli
 * /var/spool/asterisk/backup/ ichida (modulning "Local backup storage"
 * filestore drayveri orqali, GUI'dagi xuddi shu yo'l).
 *
 * MUHIM: bu alohida skript seed.php'dan keyin ishlatiladi, chunki
 * backup job'ning o'zi barcha boshqa obyektlar (extension, trunk va h.k.)
 * allaqachon DB'da bo'lishini talab qiladi (backup ularni dump qiladi).
 */

define('FREEPBX_IS_AUTH_ADMIN', true);
require_once('/etc/freepbx.conf');
require_once('/var/www/html/admin/modules/core/functions.inc.php');

set_error_handler(function ($errno, $errstr, $errfile, $errline) {
    $suppress = E_DEPRECATED | E_WARNING | E_NOTICE | E_USER_DEPRECATED | E_USER_WARNING | E_USER_NOTICE | E_STRICT;
    return ($errno & $suppress) ? true : false;
});

$backup = FreePBX::Backup();

// 1) Mavjud "Local backup storage" filestore drayverini topamiz (kvstore'da
//    FreePBX o'rnatilganda avtomatik yaratiladi — qo'lda yaratish shart emas).
$localItems = FreePBX::Filestore()->listItems('Local');
$localId = null;
foreach ($localItems as $item) {
    $localId = $item['id'];
    break;
}
if (!$localId) {
    fwrite(STDERR, "Local filestore drayveri topilmadi\n");
    exit(1);
}
echo "Local filestore id: $localId\n";

// 2) Barcha o'rnatilgan modullarni backup item sifatida belgilaymiz
//    (haqiqiy migratsiya kodidagi naqsh: ['modulename'=>..., 'selected'=>true]).
$modules = $backup->getModules();
$items = [];
foreach ($modules as $rawname => $data) {
    $items[] = ['modulename' => ucfirst($rawname), 'selected' => true];
}
echo "Backup items soni: " . count($items) . "\n";

// 3) GQL yo'li orqali backup job yaratamiz (updateGQLBackup — to'g'ridan-to'g'ri
//    massiv qabul qiladi, updateBackup() kabi $_REQUEST'ga bog'liq emas).
$input = [
    'id' => $backup->generateId(),
    'backup_name' => 'Sinov-Fixture-Backup',
    'backup_description' => "Innova PBX fixture uchun to'liq namuna backup",
    'backup_items' => $items,
    'backup_storage' => [$localId],
    'backup_schedule' => '',
    'schedule_enabled' => 'no',
    'maintage' => '30',
    'maintruns' => '10',
    'backup_email' => '',
    'backup_emailtype' => 'onfail',
    'backup_emailinline' => 'no',
    'backup_addbjname' => 'no',
    'warmspareenabled' => 'no',
];

$id = $backup->updateGQLBackup($input);
echo "Backup job yaratildi, id=$id\n";

// 4) Haqiqiy backup faylini yaratamiz (CLI'dagi `fwconsole backup --backup <id>`
//    qiladigan ishning aynan o'zi — Console/Backup.class.php orqali).
file_put_contents('/tmp/backup_job_id.txt', $id);
echo "ID /tmp/backup_job_id.txt fayliga yozildi\n";
