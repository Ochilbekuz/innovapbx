<?php
/**
 * Innova PBX — haqiqiy FreePBX 17 stendini namuna konfiguratsiya bilan to'ldirish skripti.
 *
 * MUHIM: bu skript FAQAT sinov/fixture maqsadida ishlatiladi (tests/freepbx-fixture/).
 * Hech qanday maxfiy/haqiqiy parol ishlatilmaydi — barcha parol/PIN "Sinov..." yoki
 * raqamli test qiymatlar.
 *
 * Ishlatish usuli: FreePBX'ning o'z ICHKI PHP API'laridan (Core/Ringgroups/Queues/...
 * class'lari va procedural functions.inc.php funksiyalari) to'g'ridan-to'g'ri
 * foydalaniladi — xuddi GUI forma yuborilganda ishlaydigan HAQIQIY kod yo'li.
 * Bu usul /root/devteam/workspaces/6199793291/pbx-klon/tests/freepbx-fixture/ ichida
 * amalga oshirilgan tadqiqot asosida tanlandi (Core.class.php, Queues geters_seters.php,
 * Outboundrouting.php va boshqalarni o'qib chiqib).
 */

define('FREEPBX_IS_AUTH_ADMIN', true);
require_once('/etc/freepbx.conf');
require_once('/var/www/html/admin/modules/core/functions.inc.php');
require_once('/var/www/html/admin/modules/queues/functions.inc.php');
require_once('/var/www/html/admin/modules/miscdests/functions.inc.php');

global $astman, $db;

// FreePBX 17 + PHP 8.x kombinatsiyasida ichki kodda ko'plab E_DEPRECATED/E_WARNING
// chiqadi (masalan, ctype_digit(int) chaqiruvi) — bular haqiqiy xato emas, lekin
// FreePBX'ning umumiy xato-ishlov beruvchisi ularni istisno (exception)ga aylantirib,
// butun skriptni to'xtatib qo'yadi. Shu sababli bu YERDA, aniq va tor doirada
// (faqat deprecated/warning/notice darajalarini) bostirib qo'yamiz — bu FAQAT
// ushbu sinov seed skripti uchun, FreePBX manba kodini o'zgartirmaymiz.
set_error_handler(function ($errno, $errstr, $errfile, $errline) {
    $suppress = E_DEPRECATED | E_WARNING | E_NOTICE | E_USER_DEPRECATED | E_USER_WARNING | E_USER_NOTICE | E_STRICT;
    return ($errno & $suppress) ? true : false;
});

if (!class_exists('agi_asteriskmanager')) {
    require_once('/var/www/html/admin/common/php-asmanager.php');
}
if (empty($astman)) {
    $astman = new agi_asteriskmanager();
    $astman->connect('127.0.0.1:5038', FreePBX::Config()->get('AMPMGRUSER'), FreePBX::Config()->get('AMPMGRPASS'));
}
if (!$astman->connected()) {
    fwrite(STDERR, "AMI ulanmadi — to'xtatildi\n");
    exit(1);
}

function step($title) {
    echo "\n==== $title ====\n";
}

function safe($label, callable $fn) {
    try {
        $r = $fn();
        echo "OK  $label => " . (is_scalar($r) ? $r : json_encode($r)) . "\n";
        return $r;
    } catch (\Throwable $e) {
        echo "ERR $label => " . $e->getMessage() . "\n";
        return null;
    }
}

/* ------------------------------------------------------------------
 * 1) EXTENSIONLAR (101,102,103,105,106,107 — PJSIP; 104/chan_sip
 *    Asterisk 22'da chan_sip olib tashlangani uchun BU STENDDA
 *    imkonsiz — pastda alohida izoh, freepbx-source-notes.md'da
 *    ham batafsil hujjatlashtiriladi).
 * ------------------------------------------------------------------ */
step('EXTENSIONLAR');

function addExt($ext, $name, $secret) {
    $_REQUEST = [
        'display' => 'extensions', 'action' => 'add', 'extension' => $ext, 'name' => $name,
        'tech' => 'pjsip', 'extdisplay' => '', 'devinfo_dial' => '',
        'devinfo_secret' => $secret, 'devinfo_qualifyfreq' => '60',
        'devinfo_context' => 'from-internal', 'devinfo_dtmfmode' => 'rfc2833',
        'devinfo_canreinvite' => 'no', 'devinfo_port' => '', 'devinfo_host' => 'dynamic',
        'devinfo_type' => 'friend', 'devinfo_disallow' => 'all', 'devinfo_allow' => 'ulaw,alaw,g722',
    ];
    $ok = core_devices_add($ext, 'pjsip', '', 'fixed', $ext, $name, '', '');
    if (!$ok) {
        throw new Exception("core_devices_add($ext) false qaytardi");
    }

    $vars = FreePBX::Core()->generateDefaultUserSettings($ext, $name);
    $vars['extension'] = $ext;
    $vars['name'] = $name;
    $vars['noanswer_dest'] = '';
    $vars['busy_dest'] = '';
    $vars['chanunavail_dest'] = '';
    return $vars;
}

$extensions = [
    '101' => 'Sinov Bir',
    '102' => 'Sinov Ikki (CF)',
    '103' => 'Sinov Uch',
    '105' => 'Sinov Besh (VM)',
    '106' => 'Sinov Olti (CID+DND)',
    '107' => 'Sinov Yetti (FollowMe)',
];

foreach ($extensions as $ext => $name) {
    // MUHIM: $extensions massivining kalitlari raqamli ko'rinishda ('101' kabi) bo'lgani
    // uchun PHP ularni avtomatik INTga aylantiradi. ctype_digit(int) PHP 8.1+'da
    // butunlay boshqacha ishlaydi (raqamni ASCII kod deb talqin qiladi, masalan
    // 101 -> chr(101)='e'), shu sababli Core::convertRequest2Array() "Account must
    // be set!" bilan yiqiladi. Shuning uchun aniq STRINGga qaytaramiz.
    $ext = (string) $ext;

    // MUHIM HAQIQIY KOD TAFSILOTI (Core::addUser(), Core.class.php ~3233-qator):
    // addUser() users.voicemail ustunini O'ZI $settings['voicemail']'dan EMAS,
    // balki ICHKARIDA FreePBX::Voicemail()->getMailbox($extension) natijasidan
    // hisoblab yozadi ("novm" agar topilmasa). Demak, mailbox addUser()'DAN OLDIN
    // Voicemail::addMailbox() orqali yaratilishi SHART — aks holda users.voicemail
    // doim "novm" bo'lib qoladi va voicemail.conf'da yozuv paydo bo'lmaydi (bu —
    // birinchi urinishda topilgan haqiqiy xato: 105'da mailbox yaratilmagan edi).
    if ($ext === '105') {
        safe('105 Voicemail::addMailbox (avval, addUser\'dan OLDIN)', function () {
            return FreePBX::Voicemail()->addMailbox('105', [
                'vm' => 'enabled',
                'vmpwd' => '1105',          // ovozli xat PIN (sinov)
                'name' => 'Sinov Besh (VM)',
                'email' => 'sinov105@example.test',
                'vmcontext' => 'default',
                'pager' => '',
            ]);
        });
    }

    safe("extension $ext/$name", function () use ($ext, $name) {
        $vars = addExt($ext, $name, "SinovSecret{$ext}!");
        if ($ext === '105') {
            $vars['password'] = '1105'; // VM PIN (sinov) — 'voicemail' kalitini ATAYLAB bermaymiz,
                                         // chunki addUser() uni getMailbox() orqali o'zi aniqlaydi.
        }
        if ($ext === '106') {
            $vars['outboundcid'] = '+998901110106';
        }
        return FreePBX::Core()->addUser($ext, $vars, false);
    });
}

// 104/chan_sip — IMKONSIZ: Asterisk 22'da chan_sip to'liq olib tashlangan
// (tasdiqlangan: `module show like sip` faqat chan_pjsip* ko'rsatadi).
// Buyurtma shartiga ko'ra bu shart emas ("agar modul bor bo'lsa").
echo "SKIP 104/chan_sip: Asterisk 22'da chan_sip yo'q (haqiqiy tekshirilgan fakt)\n";

/* Ext 105 — qo'shimcha VM sozlamalarini saveVMSettingsByExtension orqali ham
 * tasdiqlaymiz (mailbox allaqachon addMailbox() bilan yaratilgan, bu endi
 * shunchaki mavjud mailbox ustida tahrir — funksiya nomidan farqli o'laroq
 * u YARATMAYDI, faqat mavjudini TAHRIRLAYDI). */
safe('105 voicemail saveVMSettingsByExtension (tahrir)', function () {
    return FreePBX::Voicemail()->saveVMSettingsByExtension('105', '1105', 'sinov105@example.test', '1', '1', '1', '0', '0');
});

/* Ext 102 — CF (unconditional/busy/noanswer) astdb orqali (haqiqiy FreePBX astdb oilalari: CF/CFB/CFU) */
safe('102 CF unconditional -> 106', fn() => $GLOBALS['astman']->database_put('CF', '102', '106'));
safe('102 CFB busy -> 106', fn() => $GLOBALS['astman']->database_put('CFB', '102', '106'));
safe('102 CFU noanswer -> 105', fn() => $GLOBALS['astman']->database_put('CFU', '102', '105'));

/* Ext 106 — DND yoqilgan */
safe('106 DND=YES', fn() => $GLOBALS['astman']->database_put('DND', '106', 'YES'));

/* Ext 107 — Follow Me: tashqi a'zo bilan */
safe('107 findmefollow add', function () {
    require_once('/var/www/html/admin/modules/findmefollow/functions.inc.php');
    return FreePBX::Findmefollow()->add('107', [
        'grplist' => "107-0991234567#",
        'strategy' => 'hunt',
        'grptime' => 25,
        'ringing' => 'Ring',
    ]);
});

/* ------------------------------------------------------------------
 * 2) TRUNKLAR
 * ------------------------------------------------------------------ */
step('TRUNKLAR');

$trunk1 = safe('trunk1 registered pjsip', function () {
    $settings = [
        'channelid' => 'sinov-registered-trunk',
        'trunk_name' => 'Sinov-Registered-Trunk',
        'outcid' => '+998901112233',
        'keepcid' => 'off',
        'maxchans' => '10',
        'dialoutprefix' => '',
        'registration' => 'send',
        'authentication' => 'outbound',
        'sip_server' => 'sip.sinov-provider.test',
        'sip_server_port' => '5060',
        'username' => 'sinovuser1',
        'auth_username' => 'sinovuser1',
        'secret' => 'SinovTrunkSecret1!',
        'context' => 'from-trunk',
        'dtmfmode' => 'auto',
        'transport' => '0.0.0.0-udp',
        'qualify_frequency' => '60',
        'from_domain' => 'sip.sinov-provider.test',
    ];
    // Core::checkPJSIPsettings($ignored1, $posts) — MUHIM HAQIQIY KOD TAFSILOTI:
    // ichkarida `$imports = $posts["imports"] ?? '';` qatori bor — ya'ni bizning
    // qiymatlarimiz $posts'ning TO'G'RIDAN-TO'G'RI o'zi emas, balki $posts['imports']
    // ICHIDA bo'lishi kerak. Aks holda $imports='' bo'lib, hech narsa ustidan
    // yozilmaydi va faqat standart (bo'sh/send/outbound) qiymatlar qoladi — bu birinchi
    // urinishda sip_server/trunk_name/registration kabilar jim bo'sh qolib ketishiga
    // sabab bo'lgan xato edi (haqiqiy GUI POST yo'lida $_POST['imports'] shu tarzda keladi).
    $settings = FreePBX::Core()->checkPJSIPsettings([], ['imports' => $settings]);
    return FreePBX::Core()->addTrunk('Sinov-Registered-Trunk', 'pjsip', $settings);
});

$trunk2 = safe('trunk2 ip-auth pjsip (ro\'yxatdan o\'tmagan)', function () {
    $settings = [
        'channelid' => 'sinov-ipauth-trunk',
        'trunk_name' => 'Sinov-IPAuth-Trunk',
        'outcid' => '+998901112244',
        'keepcid' => 'off',
        'maxchans' => '5',
        'dialoutprefix' => '',
        'registration' => 'none',
        'authentication' => 'none',
        'identify_by' => 'ip',
        'match' => '203.0.113.10/32', // RFC5737 TEST-NET-3 — hujjat uchun xavfsiz IP
        'context' => 'from-trunk',
        'dtmfmode' => 'auto',
        'transport' => '0.0.0.0-udp',
    ];
    // Yuqoridagi izohdagi bilan bir xil sabab — qiymatlar 'imports' kaliti ichida.
    $settings = FreePBX::Core()->checkPJSIPsettings([], ['imports' => $settings]);
    return FreePBX::Core()->addTrunk('Sinov-IPAuth-Trunk', 'pjsip', $settings);
});

echo "trunk1 id=" . var_export($trunk1, true) . " trunk2 id=" . var_export($trunk2, true) . "\n";
$trunk1 = $trunk1 ?: 1;
$trunk2 = $trunk2 ?: 2;

/* ------------------------------------------------------------------
 * 3) MISC/RECORDING/MOH/ANNOUNCEMENT/RINGGROUP/QUEUE/IVR/TIMEGROUP
 *    — bular routelardan OLDIN, chunki destination grammatikasida
 *    ularning ID'lari kerak bo'ladi.
 * ------------------------------------------------------------------ */
step('TOVUSH YOZUVLARI VA MOH');

// Haqiqiy audio fayllardan nusxa (image ichidagi demo tovushlar)
safe('custom recording fayli nusxalash', function () {
    if (!is_dir('/var/lib/asterisk/sounds/custom')) {
        mkdir('/var/lib/asterisk/sounds/custom', 0775, true);
    }
    foreach (['ulaw', 'gsm', 'g722'] as $fmt) {
        copy("/var/lib/asterisk/sounds/en/demo-congrats.$fmt", "/var/lib/asterisk/sounds/custom/sinov-tizim-yozuvi.$fmt");
    }
    return true;
});

$recordingId = safe('Recordings::addRecording', function () {
    return FreePBX::Recordings()->addRecording('sinov-tizim-yozuvi', "Sinov tizim e'loni (demo-congrats asosida)", 'custom/sinov-tizim-yozuvi', 0, '', '');
});
$recordingId = $recordingId ?: 1;

safe('MOH custom kategoriya papkasi + fayl', function () {
    $dir = '/var/lib/asterisk/moh/sinov-moh';
    if (!is_dir($dir)) {
        mkdir($dir, 0775, true);
    }
    copy('/var/lib/asterisk/moh/macroform-cold_day.wav', $dir . '/sinov-moh-track.wav');
    return true;
});
safe('Music::addCategoryById', function () {
    FreePBX::Music()->addCategoryById(null, 'sinov-moh', 'custom');
    return true;
});

$announcementId = safe('Announcement::addAnnouncement', function () use ($recordingId) {
    return FreePBX::Announcement()->addAnnouncement("Sinov yopiq vaqt e'loni", $recordingId, 0, 'app-blackhole,hangup,1', '', 0, 0);
});
$announcementId = $announcementId ?: 1;

step('RING GROUP');
$ringGroupNum = '600';
safe('Ringgroups::add', function () use ($ringGroupNum) {
    return FreePBX::Ringgroups()->add(
        $ringGroupNum, 'ringall', '20', "101-102-103-0991234567#",
        'ext-local,105,1', "Sinov qo'ng'iroq guruhi", '', '0', '', '', '', '', '', '', '',
        'default', '', '', 'dontcare', 'yes', '', ''
    );
});

step('NAVBAT (QUEUE)');
$queueNum = '700';
safe('queues_add (haqiqiy FreePBX queues_add() funksiyasi)', function () use ($queueNum) {
    $_REQUEST = [
        'maxlen' => '0', 'joinempty' => 'yes', 'leavewhenempty' => 'no', 'strategy' => 'ringall',
        'timeout' => '15', 'retry' => '5', 'wrapuptime' => '10', 'announcefreq' => '0',
        'min-announce' => '15', 'announceholdtime' => 'no', 'announceposition' => 'yes',
        'pannouncefreq' => '0', 'recording' => 'dontcare', 'weight' => '0', 'autofill' => '1',
        'reportholdtime' => 'no', 'autopause' => 'no', 'autopausedelay' => '0', 'servicelevel' => 60,
        'memberdelay' => '0', 'timeoutrestart' => 'no', 'answered_elsewhere' => '0',
        'timeoutpriority' => 'app', 'penaltymemberslimit' => '0', 'rvolume' => '', 'rvol_mode' => '',
        'music' => 'sinov-moh', 'action' => 'add',
    ];
    $members = ['Local/101@from-queue/n,0', 'Local/102@from-queue/n,0'];
    $dynmembers = ['103,0'];
    return queues_add(
        $queueNum, "Sinov navbati", '', '', 'ext-local,105,1', '', $members, '', '20',
        '', '0', '', '0', '0', $dynmembers, 'no'
    );
});

step('IVR');
$ivrId = safe('Ivr::saveDetails', function () use ($recordingId) {
    $ivr = FreePBX::Ivr();
    $vals = [
        'id' => null,
        'name' => 'Sinov-IVR',
        'description' => "Sinov IVR menyusi",
        'announcement' => $recordingId,
        'directdial' => '',
        'invalid_loops' => '3',
        'invalid_retry_recording' => 'default',
        'invalid_destination' => 'app-blackhole,hangup,1',
        'invalid_recording' => 'default',
        'timeout_time' => '10',
        'timeout_recording' => 'default',
        'timeout_retry_recording' => 'default',
        'timeout_destination' => 'app-blackhole,hangup,1',
        'timeout_loops' => '3',
        'alertinfo' => '',
        'rvolume' => '',
    ];
    return $ivr->saveDetails($vals);
});
$ivrId = $ivrId ?: 1;

safe('Ivr::saveEntries', function () use ($ivrId, $ringGroupNum, $queueNum) {
    $ivr = FreePBX::Ivr();
    $entries = [
        'ext' => ['1', '2', '3'],
        'goto' => ['ext-local,101,1', "ext-group,$ringGroupNum,1", "ext-queues,$queueNum,1"],
        'ivr_ret' => ['0', '0', '0'],
    ];
    return $ivr->saveEntries($ivrId, $entries);
});

step('VAQT GURUHI VA VAQT SHARTI (TIME GROUP/CONDITION)');
$timeGroupId = safe('Timeconditions::addTimeGroup', function () {
    // Timeconditions::editTimes() har bir elementni assotsiativ massiv deb kutadi
    // (hour_start/minute_start/.../month_finish), '-' == "istalgan qiymat" (*).
    // Natijada hosil bo'ladigan matn formati: "09:00-18:00|mon-fri|*|*" (soat|hafta kuni|oy kuni|oy).
    $businessHours = [
        'hour_start' => 9, 'minute_start' => 0, 'hour_finish' => 18, 'minute_finish' => 0,
        'wday_start' => 'mon', 'wday_finish' => 'fri',
        'mday_start' => '-', 'mday_finish' => '-', 'month_start' => '-', 'month_finish' => '-',
    ];
    $holiday = [ // Sinov bayrami: 1-yanvar, kun bo'yi
        'hour_start' => '-', 'minute_start' => '-', 'hour_finish' => '-', 'minute_finish' => '-',
        'wday_start' => '-', 'wday_finish' => '-',
        'mday_start' => 1, 'mday_finish' => 1, 'month_start' => 'jan', 'month_finish' => 'jan',
    ];
    return FreePBX::Timeconditions()->addTimeGroup(
        "Sinov ish vaqti + bayram",
        [$businessHours, $holiday]
    );
});
$timeGroupId = $timeGroupId ?: 1;

$timeConditionId = safe('Timeconditions::addTimeCondition', function () use ($timeGroupId, $ivrId, $announcementId) {
    // MUHIM HAQIQIY KOD TAFSILOTI (Timeconditions.class.php::addTimeCondition(),
    // 531-qator): ichkarida ':falsegoto' => $post[$post['goto1'].'1'] VA
    // ':truegoto' => $post[$post['goto0'].'0'] — ya'ni 'goto1'/'truekey1'-uslubidagi
    // kalit nomlari TUSHUNARSIZ TARZDA teskari: "goto1"+"1" qo'shilgan qiymat
    // haqiqatda FALSEGOTO ustunига, "goto0"+"0" qiymati esa TRUEGOTO ustunига
    // yoziladi. Bu haqiqiy FreePBX kodidagi o'ziga xos chalkashlik (ehtimol GUI'dagi
    // radio-input nomlash tarixi bilan bog'liq) — birinchi urinishda biz buni teskari
    // qo'llagan edik va natijada ish-vaqti (true) -> e'lon, bayram/tashqi vaqt (false)
    // -> IVR bo'lib chiqdi (kutilganining aksi). Pastda TO'G'RI natija uchun kalit
    // nomlari ATAYLAB formula bo'yicha moslashtirilgan.
    $post = [
        'displayname' => "Sinov ish vaqti sharti",
        'time' => $timeGroupId,
        'invert_hint' => '0',
        // truegoto (ish vaqti, haftaning dush-juma 09:00-18:00) -> IVR:
        'goto0' => 'truekey', 'truekey0' => "ivr-$ivrId,s,1",
        // falsegoto (ish vaqtidan tashqari) -> tizim e'loni:
        'goto1' => 'falsekey', 'falsekey1' => "app-announcement-$announcementId,s,1",
        'fcc_password' => '', 'deptname' => '', 'mode' => 'time',
    ];
    return FreePBX::Timeconditions()->addTimeCondition($post);
});
$timeConditionId = $timeConditionId ?: 1;

/* ------------------------------------------------------------------
 * 4) INBOUND VA OUTBOUND ROUTE'LAR (yuqoridagi IVR/TC/RG/Queue ID'lari bilan)
 * ------------------------------------------------------------------ */
step('INBOUND ROUTE (DID)');

safe('DID1 -> IVR', function () use ($ivrId) {
    return FreePBX::Core()->addDID([
        'extension' => '998712345601', 'cidnum' => '', 'description' => 'Sinov DID -> IVR',
        'destination' => "ivr-$ivrId,s,1", 'mohclass' => 'default',
    ]);
});
safe('DID2 -> Time Condition', function () use ($timeConditionId) {
    return FreePBX::Core()->addDID([
        'extension' => '998712345602', 'cidnum' => '', 'description' => 'Sinov DID -> Time Condition',
        'destination' => "timeconditions,$timeConditionId,1", 'mohclass' => 'default',
    ]);
});
safe('DID3 (har qanday DID) -> Ring Group', function () use ($ringGroupNum) {
    return FreePBX::Core()->addDID([
        'extension' => '', 'cidnum' => '', 'description' => 'Sinov Har-qanday-DID -> RingGroup',
        'destination' => "ext-group,$ringGroupNum,1", 'mohclass' => 'default',
    ]);
});

step('OUTBOUND ROUTE');
safe('Outbound Route 1 (mobil, trunk ketma-ketlik + failover)', function () use ($trunk1, $trunk2) {
    $patterns = [[
        'match_pattern_prefix' => '0', 'match_pattern_pass' => 'XXXXXXXXX',
        'match_cid' => '', 'prepend_digits' => '+998',
    ]];
    // E'TIBOR: Core::__get() ichida komponent property nomi "routing" (Outboundrouting EMAS).
    return FreePBX::Core()->routing->add(
        'Sinov-Mobil', '+998901110000', 'ALLOW', 'SinovRoutePass1', 'off', 'off',
        'default', 0, $patterns, [$trunk1, $trunk2]
    );
});
safe('Outbound Route 2 (ichki xizmat, bitta trunk)', function () use ($trunk2) {
    $patterns = [[
        'match_pattern_prefix' => '1', 'match_pattern_pass' => 'XX',
        'match_cid' => '', 'prepend_digits' => '',
    ]];
    return FreePBX::Core()->routing->add(
        'Sinov-Xizmat', '', '', '', 'off', 'off', 'default', 0, $patterns, [$trunk2]
    );
});

/* ------------------------------------------------------------------
 * 5) KONFERENSIYA, BLACKLIST, MISC DESTINATION
 * ------------------------------------------------------------------ */
step('KONFERENSIYA');
safe('Conferences::addConference', function () {
    return FreePBX::Conferences()->addConference('8000', 'Sinov konferensiya', '1234', '4321', '', null, 'default', 0, '', 21600);
});

step('BLACKLIST');
safe('Blacklist::numberAdd', function () {
    return FreePBX::Blacklist()->numberAdd(['number' => '0998887766', 'description' => 'Sinov bloklangan raqam']);
});

step('MISC DESTINATION');
safe('miscdests_add', function () {
    return miscdests_add("Sinov qisqa raqam -> 101", '101');
});

echo "\n==== TUGADI ====\n";
