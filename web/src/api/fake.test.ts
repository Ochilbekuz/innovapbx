import { beforeEach, describe, expect, it } from 'vitest';
import { createFakeClient } from './fake';
import { isApiError } from './errors';
import { SEED_ADMIN, SEED_ADMIN_PASSWORD, SEED_OPERATOR, SEED_OPERATOR_PASSWORD, SIM_ROLLBACK_MARK } from './fakeSeed';
import type { ApiClient } from './client';

async function asAdmin(client: ApiClient) {
  await client.login(SEED_ADMIN.login, SEED_ADMIN_PASSWORD);
}

async function asOperator(client: ApiClient) {
  await client.login(SEED_OPERATOR.login, SEED_OPERATOR_PASSWORD);
}

describe('fake client — setup va kirish', () => {
  it('boshida sozlash kerak, setup()dan keyin kerak emas', async () => {
    const client = createFakeClient();
    expect((await client.setupState()).needed).toBe(true);
    await client.setup({ admin: { login: 'boss', password: 'Parol12345!', full_name: 'Boss' }, language: 'uz', timezone: 'Asia/Tashkent', external_ip: null, local_nets: ['10.0.0.0/8'] });
    expect((await client.setupState()).needed).toBe(false);
  });

  it("noto'g'ri parol 5 marta — 423 locked", async () => {
    const client = createFakeClient();
    for (let i = 0; i < 4; i += 1) {
      await expect(client.login(SEED_ADMIN.login, 'notogri')).rejects.toMatchObject({ status: 401, code: 'bad_credentials' });
    }
    await expect(client.login(SEED_ADMIN.login, 'notogri')).rejects.toMatchObject({ status: 423, code: 'locked' });
    // Hatto to'g'ri parol bilan ham — bloklangan.
    await expect(client.login(SEED_ADMIN.login, SEED_ADMIN_PASSWORD)).rejects.toMatchObject({ status: 423, code: 'locked' });
  });

  it("to'g'ri login/parol — token va foydalanuvchi qaytadi", async () => {
    const client = createFakeClient();
    const res = await client.login(SEED_ADMIN.login, SEED_ADMIN_PASSWORD);
    if (res.status !== 'ok') throw new Error('2FA kutilmagan edi');
    expect(res.user.login).toBe('admin');
    expect(res.access).toBeTruthy();
    expect(res.refresh).toBeTruthy();
  });

  it('refresh token aylanadi — eskisi qayta ishlamaydi', async () => {
    const client = createFakeClient();
    const loginRes = await client.login(SEED_ADMIN.login, SEED_ADMIN_PASSWORD);
    if (loginRes.status !== 'ok') throw new Error('2FA kutilmagan edi');
    const { refresh } = loginRes;
    const rotated = await client.refresh(refresh);
    expect(rotated.refresh).not.toBe(refresh);
    await expect(client.refresh(refresh)).rejects.toMatchObject({ status: 401, code: 'bad_refresh' });
  });
});

describe('fake client — ichki raqamlar', () => {
  let client: ApiClient;
  beforeEach(async () => { client = createFakeClient(); await asAdmin(client); });

  it('number_taken — band raqam bilan yaratib bo\'lmaydi', async () => {
    await expect(client.createExtension({ number: '101', name: 'Yangi odam' })).rejects.toMatchObject({ status: 409, code: 'number_taken', field: 'number' });
  });

  it('raqam ko\'rsatilmasa — bo\'sh birinchisi avtomatik beriladi', async () => {
    const res = await client.createExtension({ name: 'Avtomatik' });
    expect(res.item.number).toBe('100');
    expect(res.sip.username).toBe('100');
    expect(res.apply.status).toBe('applied');
  });

  it('stale — boshqa joyda o\'zgargan yozuvni saqlab bo\'lmaydi', async () => {
    const { items } = await client.listExtensions({});
    const ext = items.find((e) => e.id === 'e-102')!;
    await expect(client.updateExtension(ext.id, { name: 'Yangi nom', updated_at: '2000-01-01T00:00:00Z' }))
      .rejects.toMatchObject({ status: 409, code: 'stale' });
  });

  it('in_use — kiruvchi marshrutda ishlatilayotgan raqamni o\'chirib bo\'lmaydi', async () => {
    await expect(client.deleteExtension('e-101')).rejects.toMatchObject({ status: 409, code: 'in_use' });
  });

  it('ishlatilmayotgan raqam muammosiz o\'chadi', async () => {
    await expect(client.deleteExtension('e-102')).resolves.toBeUndefined();
    const { items } = await client.listExtensions({});
    expect(items.find((e) => e.id === 'e-102')).toBeUndefined();
  });

  it('nom SIMULYATSIYA_XATO belgisini o\'z ichiga olsa — rolled_back qaytadi', async () => {
    const res = await client.createExtension({ name: `Test ${SIM_ROLLBACK_MARK}` });
    expect(res.apply.status).toBe('rolled_back');
  });

  it('operator huquqisiz yaratishga urinsa — 403 forbidden', async () => {
    const op = createFakeClient();
    await op.login(SEED_OPERATOR.login, SEED_OPERATOR_PASSWORD);
    await expect(op.createExtension({ name: 'Ruxsatsiz' })).rejects.toMatchObject({ status: 403, code: 'forbidden' });
  });

  it('parol berilmasa — siyosatga mos tasodifiy parol generatsiya qilinadi', async () => {
    const res = await client.createExtension({ name: 'Avtomatik parol' });
    expect(res.sip.password.length).toBeGreaterThanOrEqual(8);
    expect(res.sip.domain).toBeTruthy();
    expect(res.sip.port).toBe(5060);
  });

  it('o\'z parolini kiritib yaratish — xuddi shu parol qaytadi, login=raqam', async () => {
    const res = await client.createExtension({ number: '150', name: 'Qo\'lda parol', password: 'Secret123' });
    expect(res.sip.username).toBe('150');
    expect(res.sip.password).toBe('Secret123');
  });

  it('weak_password — zaif parol bilan yaratib bo\'lmaydi (422, field=password)', async () => {
    await expect(client.createExtension({ number: '151', name: 'Zaif', password: '1234567' }))
      .rejects.toMatchObject({ status: 422, code: 'weak_password', field: 'password' });
    await expect(client.createExtension({ number: '151', name: 'Zaif', password: 'onlyletters' }))
      .rejects.toMatchObject({ status: 422, code: 'weak_password', field: 'password' });
    await expect(client.createExtension({ number: '151', name: 'Zaif', password: 'abc151xyz' }))
      .rejects.toMatchObject({ status: 422, code: 'weak_password', field: 'password' });
  });

  it('yaratishda outbound_allowed/outbound_callerid/dnd saqlanadi', async () => {
    const res = await client.createExtension({
      number: '152', name: 'Sozlangan', dnd: true, outbound_allowed: false, outbound_callerid: '998712345678',
    });
    expect(res.item.dnd).toBe(true);
    expect(res.item.outbound_allowed).toBe(false);
    expect(res.item.outbound_callerid).toBe('998712345678');
  });

  it('rotate-secret — yangi tasodifiy parol, login o\'zgarmaydi', async () => {
    const before = await client.listExtensions({});
    const ext = before.items.find((e) => e.id === 'e-101')!;
    const res = await client.rotateExtensionSecret(ext.id);
    expect(res.sip.username).toBe(ext.number);
    expect(res.sip.password.length).toBeGreaterThanOrEqual(8);
  });

  it('setExtensionSecret — o\'z parolini o\'rnatish, weak_password rad etiladi', async () => {
    const before = await client.listExtensions({});
    const ext = before.items.find((e) => e.id === 'e-101')!;
    await expect(client.setExtensionSecret(ext.id, 'bad')).rejects.toMatchObject({ status: 422, code: 'weak_password', field: 'password' });
    const res = await client.setExtensionSecret(ext.id, 'MyNewPass9');
    expect(res.sip.username).toBe(ext.number);
    expect(res.sip.password).toBe('MyNewPass9');
    expect(res.apply.status).toBe('realtime');
  });
});

describe('fake client — kiruvchi marshrutlar', () => {
  let client: ApiClient;
  beforeEach(async () => { client = createFakeClient(); await asAdmin(client); });

  it('did_conflict — bir xil DID+CID kombinatsiyasi qaytarilmaydi', async () => {
    await expect(client.createInboundRoute({ name: 'Nusxa', did: '998712000000', cid: null, target_id: 'e-102', enabled: true }))
      .rejects.toMatchObject({ status: 409, code: 'did_conflict', field: 'did' });
  });

  it('yangi DID — muvaffaqiyatli qo\'shiladi', async () => {
    const res = await client.createInboundRoute({ name: 'Yangi', did: '998712009999', cid: null, target_id: 'e-102', enabled: true });
    expect(res.item.target.broken).toBe(false);
    expect(res.apply.status).toBe('applied');
  });

  it('listTargets — faqat joriy (buzilmagan) ichki raqamlardan iborat', async () => {
    const { items } = await client.listTargets({ kind: 'extension' });
    expect(items.every((t) => !t.broken)).toBe(true);
    expect(items.find((t) => t.id === 'e-199')).toBeUndefined();
  });
});

describe('fake client — chiquvchi marshrut naqsh shartnomasi (backend bilan bir xil)', () => {
  let client: ApiClient;
  beforeEach(async () => { client = createFakeClient(); await asAdmin(client); });
  const route = (pattern: Record<string, unknown>) => ({
    name: 'Sinov', enabled: true, patterns: [pattern] as never, trunk_ids: ['t-1'], callerid: null,
    override_extension_callerid: false, international: false, extensions: 'all' as const, pin: null,
  });

  it('bo\'sh ixtiyoriy maydon null bo\'lsa — 422 (backend pydantic str kutadi)', async () => {
    await expect(client.createOutboundRoute(route({ strip_prefix: null, pattern: '7XXX', add_prefix: '', callerid_match: '' })))
      .rejects.toMatchObject({ status: 422, field: 'patterns.0.strip_prefix' });
  });

  it('bo\'sh ixtiyoriy maydon \'\' — qabul qilinadi', async () => {
    const trunk = (await client.listTrunks()).items[0]!;
    const res = await client.createOutboundRoute({ ...route({ strip_prefix: '', pattern: '7XXX', add_prefix: '', callerid_match: '' }), trunk_ids: [trunk.id] });
    expect(res.item.patterns[0]).toEqual({ strip_prefix: '', pattern: '7XXX', add_prefix: '', callerid_match: '' });
  });

  it.each(['_7XXX', '7xxx'])('normallashmagan naqsh %s — 422 bad_pattern (backend faqat 0-9XZN.[]*#+-! qabul qiladi)', async (pattern) => {
    await expect(client.createOutboundRoute(route({ strip_prefix: '', pattern, add_prefix: '', callerid_match: '' })))
      .rejects.toMatchObject({ status: 422, code: 'bad_pattern' });
  });
});

describe('fake client — M1a', () => {
  let client: ApiClient;
  beforeEach(async () => { client = createFakeClient(); await asAdmin(client); });

  it('range_order — tugash boshlanishdan oldin bo\'lsa 422', async () => {
    await expect(client.createTimeGroup({ name: 'Notoʻgʻri', ranges: [{ weekdays: [1], start: '18:00', end: '09:00' }] }))
      .rejects.toMatchObject({ status: 422, code: 'range_order' });
  });

  it('stale — boshqa joyda oʻzgargan ish vaqti guruhini saqlab boʻlmaydi', async () => {
    await expect(client.updateTimeGroup('tg-ish-kunlari', { name: 'Yangi', updated_at: '2000-01-01T00:00:00Z' }))
      .rejects.toMatchObject({ status: 409, code: 'stale' });
  });

  it('in_use — ish vaqti shartida ishlatilayotgan guruhni oʻchirib boʻlmaydi, kim ishlatayotgani koʻrsatiladi', async () => {
    await expect(client.deleteTimeGroup('tg-ish-kunlari')).rejects.toMatchObject({
      status: 409, code: 'in_use',
      details: { usages: [{ kind: 'time_condition', id: 'tc-ish-vaqti' }] },
    });
  });

  it('number_taken — IVR va navbat bitta raqamlar hovuzini ulashadi', async () => {
    await expect(client.createQueue({
      name: 'Nusxa', number: '700', strategy: 'ringall', agent_ring_seconds: 20, retry_seconds: 5, wrapup_seconds: 5,
      max_wait_seconds: 120, max_callers: null, announce_position: false, announce_frequency_seconds: 30, sla_seconds: 20,
      join_empty: true, record: false, members: [], timeout_target_id: 'sys-hangup',
    })).rejects.toMatchObject({ status: 409, code: 'number_taken', field: 'number' });
  });

  it('duplicate_digit — IVR\'da bitta tugma ikki marta ishlatilsa 422', async () => {
    await expect(client.createIvr({
      name: 'Nusxa menyu', greeting_audio_id: 'au-greeting', timeout_seconds: 10, repeats: 2, direct_dial: false,
      options: [{ digit: '1', target_id: 'e-101' }, { digit: '1', target_id: 'e-102' }],
      timeout_target_id: 'sys-hangup', invalid_target_id: 'sys-hangup',
    })).rejects.toMatchObject({ status: 422, code: 'duplicate_digit', field: 'options' });
  });

  it('loop — IVR oʻz vaqti tugashida (chiqishsiz) oʻziga qaytsa 422, yoʻl nomlar bilan', async () => {
    const cur = (await client.listIvrs()).items.find((v) => v.id === 'ivr-asosiy')!;
    await expect(client.updateIvr('ivr-asosiy', { timeout_target_id: 'ivr-asosiy', updated_at: cur.updated_at }))
      .rejects.toMatchObject({ status: 422, code: 'loop', details: { path: ['Asosiy menyu', 'Asosiy menyu'] } });
  });

  it('bad_format — wav/mp3/ogg dan boshqa kengaytma rad etiladi', async () => {
    const file = new File(['x'], 'ovoz.txt', { type: 'text/plain' });
    await expect(client.uploadAudio(file, 'Test')).rejects.toMatchObject({ status: 415, code: 'bad_format' });
  });

  it('too_large — 20 MB dan katta fayl rad etiladi', async () => {
    const file = new File([new Uint8Array(21 * 1024 * 1024)], 'katta.wav', { type: 'audio/wav' });
    await expect(client.uploadAudio(file, 'Test')).rejects.toMatchObject({ status: 413, code: 'too_large' });
  });
});

describe('fake client — M1c (ovozli pochta, bildirishnoma, TLS)', () => {
  let client: ApiClient;
  beforeEach(async () => { client = createFakeClient(); await asAdmin(client); });

  it('bad_pin — notoʻgʻri formatdagi PIN bilan quti yaratib boʻlmaydi', async () => {
    await expect(client.createVoicemailBox({ extension_id: 'e-102', pin: '12ab' }))
      .rejects.toMatchObject({ status: 422, code: 'bad_pin', field: 'pin' });
  });

  it('mailbox_taken — allaqachon qutisi bor ichki raqamga ikkinchi quti ochib boʻlmaydi', async () => {
    await expect(client.createVoicemailBox({ extension_id: 'e-101', pin: '1234' }))
      .rejects.toMatchObject({ status: 409, code: 'mailbox_taken' });
  });

  it('boʻsh ichki raqamga quti muvaffaqiyatli ochiladi', async () => {
    const res = await client.createVoicemailBox({ extension_id: 'e-102', pin: '1234' });
    expect(res.item.mailbox).toBe('102');
    expect(res.apply.status).toBe('applied');
  });

  it('markVoicemailMessageHeard — xabar "old" jildiga oʻtadi', async () => {
    await client.markVoicemailMessageHeard('vm-101', 'INBOX/msg0001');
    const { items } = await client.listVoicemailMessages('vm-101');
    expect(items.find((m) => m.id === 'INBOX/msg0001')?.folder).toBe('old');
  });

  it('deleteVoicemailMessage — xabar roʻyxatdan yoʻqoladi', async () => {
    await client.deleteVoicemailMessage('vm-101', 'INBOX/msg0000');
    const { items } = await client.listVoicemailMessages('vm-101');
    expect(items.find((m) => m.id === 'INBOX/msg0000')).toBeUndefined();
  });

  it('notify_failed — NOTIFY_XATO belgisi SMTP ulanish xatosini keltirib chiqaradi', async () => {
    await expect(client.testNotify({ channel: 'email', to: 'NOTIFY_XATO@mail.test' }))
      .rejects.toMatchObject({ status: 502, code: 'notify_failed', details: { reason: 'smtp_connection_failed' } });
  });

  it('notify_failed — Telegram kanalida notoʻgʻri token sababi qaytadi', async () => {
    await expect(client.testNotify({ channel: 'telegram', to: 'NOTIFY_XATO' }))
      .rejects.toMatchObject({ status: 502, code: 'notify_failed', details: { reason: 'telegram_bad_token' } });
  });

  it('bad_certificate — boʻsh fayllar PEM emasligi sababli rad etiladi', async () => {
    const cert = new File([], 'cert.pem', { type: 'application/x-pem-file' });
    const key = new File([], 'key.pem', { type: 'application/x-pem-file' });
    await expect(client.uploadSipTlsCertificate(cert, key))
      .rejects.toMatchObject({ status: 422, code: 'bad_certificate', details: { reason: 'not_pem' } });
  });

  it('createSelfSignedSipTls — oʻz-oʻzidan imzolangan sertifikat yaratadi va restart_required belgilaydi', async () => {
    const tls = await client.createSelfSignedSipTls({ common_name: 'pbx.test.local' });
    expect(tls.certificate?.self_signed).toBe(true);
    expect(tls.restart_required).toBe(true);
  });
});

describe('fake client — M2a DND/yo\'naltirish (ichki raqam)', () => {
  let client: ApiClient;
  beforeEach(async () => { client = createFakeClient(); await asAdmin(client); });

  it('dnd/forward_always/forward_busy/pickup_group — to\'g\'ri qiymatlar realtime saqlanadi', async () => {
    const { items } = await client.listExtensions({});
    const ext = items.find((e) => e.id === 'e-102')!;
    const res = await client.updateExtension(ext.id, {
      dnd: true, forward_always: '+998901234567', forward_busy: '103', pickup_group: 'support', updated_at: ext.updated_at,
    });
    expect(res.item.dnd).toBe(true);
    expect(res.item.forward_always).toBe('998901234567'); // boshidagi `+` server tomonda olib tashlanadi
    expect(res.item.forward_busy).toBe('103');
    expect(res.item.pickup_group).toBe('support');
    expect(res.apply.status).toBe('applied');
  });

  it('bad_number — forward_always notoʻgʻri formatda bo\'lsa 422', async () => {
    const { items } = await client.listExtensions({});
    const ext = items.find((e) => e.id === 'e-102')!;
    await expect(client.updateExtension(ext.id, { forward_always: 'abc', updated_at: ext.updated_at }))
      .rejects.toMatchObject({ status: 422, code: 'bad_number', field: 'forward_always' });
  });

  it('bad_number — forward_busy notoʻgʻri formatda bo\'lsa 422', async () => {
    const { items } = await client.listExtensions({});
    const ext = items.find((e) => e.id === 'e-102')!;
    await expect(client.updateExtension(ext.id, { forward_busy: '1', updated_at: ext.updated_at }))
      .rejects.toMatchObject({ status: 422, code: 'bad_number', field: 'forward_busy' });
  });

  it('bad_pickup_group — notoʻgʻri belgilar bo\'lsa 422', async () => {
    const { items } = await client.listExtensions({});
    const ext = items.find((e) => e.id === 'e-102')!;
    await expect(client.updateExtension(ext.id, { pickup_group: 'Sales Team!', updated_at: ext.updated_at }))
      .rejects.toMatchObject({ status: 422, code: 'bad_pickup_group', field: 'pickup_group' });
  });

  it('aniq null — tozalaydi; berilmagan maydon — oʻzgarmaydi', async () => {
    const { items } = await client.listExtensions({});
    const e104 = items.find((e) => e.id === 'e-104')!; // forward_busy: '103', pickup_group: 'sales'
    const res = await client.updateExtension(e104.id, { forward_busy: null, updated_at: e104.updated_at });
    expect(res.item.forward_busy).toBeNull();
    expect(res.item.pickup_group).toBe('sales'); // berilmagan — oʻzgarmadi
  });

  it('yangi ichki raqam — dnd/forward/pickup_group boʻsh boshlanadi', async () => {
    const res = await client.createExtension({ name: 'Yangi odam' });
    expect(res.item.dnd).toBe(false);
    expect(res.item.forward_always).toBeNull();
    expect(res.item.forward_busy).toBeNull();
    expect(res.item.pickup_group).toBeNull();
  });

  it('700-720 — park uchun zahiralangan, ichki raqamga berib bo\'lmaydi', async () => {
    await expect(client.createExtension({ number: '705', name: 'Parkga urinish' }))
      .rejects.toMatchObject({ status: 409, code: 'number_taken', details: { reason: 'reserved' } });
  });

  it('bad_number — oʻz raqamiga yoʻnaltirib boʻlmaydi (forward_always)', async () => {
    const { items } = await client.listExtensions({});
    const ext = items.find((e) => e.id === 'e-102')!; // raqami 102
    await expect(client.updateExtension(ext.id, { forward_always: ext.number, updated_at: ext.updated_at }))
      .rejects.toMatchObject({ status: 422, code: 'bad_number', field: 'forward_always' });
  });

  it('bad_number — oʻz raqamiga yoʻnaltirib boʻlmaydi (forward_busy), `+` olib tashlangandan keyin ham', async () => {
    const { items } = await client.listExtensions({});
    const ext = items.find((e) => e.id === 'e-102')!;
    await expect(client.updateExtension(ext.id, { forward_busy: `+${ext.number}`, updated_at: ext.updated_at }))
      .rejects.toMatchObject({ status: 422, code: 'bad_number', field: 'forward_busy' });
  });

  it('"" — `null` kabi tozalaydi', async () => {
    const { items } = await client.listExtensions({});
    const e104 = items.find((e) => e.id === 'e-104')!; // forward_busy: '103'
    const res = await client.updateExtension(e104.id, { forward_busy: '', updated_at: e104.updated_at });
    expect(res.item.forward_busy).toBeNull();
  });

  it('faqat dnd/forward/pickup oʻzgarsa — apply revision/message berilmaydi (realtime)', async () => {
    const { items } = await client.listExtensions({});
    const ext = items.find((e) => e.id === 'e-102')!;
    const res = await client.updateExtension(ext.id, { dnd: true, updated_at: ext.updated_at });
    expect(res.apply).toEqual({ status: 'applied', revision: null, message: null });
  });

  it('nom/yoqilganlik bilan birga oʻzgarsa — oddiy apply (reviziya bilan)', async () => {
    const { items } = await client.listExtensions({});
    const ext = items.find((e) => e.id === 'e-102')!;
    const res = await client.updateExtension(ext.id, { name: 'Yangi nom', dnd: true, updated_at: ext.updated_at });
    expect(res.apply.revision).not.toBeNull();
  });
});

describe('fake client — M2a xususiyat kodlari (S24)', () => {
  let client: ApiClient;
  beforeEach(async () => { client = createFakeClient(); await asAdmin(client); });

  it('standart kodlar roʻyxati toʻgʻri tartibda qaytadi', async () => {
    const { items } = await client.listFeatureCodes();
    expect(items.map((i) => i.feature)).toEqual([
      'voicemail', 'voicemail_other', 'dnd_toggle', 'cf_always_on', 'cf_always_off', 'cf_busy_on', 'cf_busy_off',
      'pickup_group', 'pickup_direct', 'park', 'echo_test', 'speaking_clock', 'followme_toggle',
    ]);
    expect(items.find((i) => i.feature === 'dnd_toggle')?.code).toBe('*76');
  });

  it('kodni tahrirlash — muvaffaqiyatli, apply=applied', async () => {
    const res = await client.updateFeatureCode('dnd_toggle', { code: '*77' });
    expect(res.item.code).toBe('*77');
    expect(res.apply.status).toBe('applied');
  });

  it('bad_code — notoʻgʻri formatdagi kod rad etiladi', async () => {
    await expect(client.updateFeatureCode('dnd_toggle', { code: 'x76' }))
      .rejects.toMatchObject({ status: 422, code: 'bad_code', field: 'code' });
  });

  it('code_taken — boshqa kod bilan toʻliq moslik, details.conflict toʻqnashgan kodni koʻrsatadi', async () => {
    await expect(client.updateFeatureCode('cf_always_off', { code: '*72' }))
      .rejects.toMatchObject({ status: 409, code: 'code_taken', field: 'code', details: { conflict: '*72' } });
  });

  it('code_taken — prefiks toʻqnashuvi (masalan *7 — *76 bilan)', async () => {
    await expect(client.updateFeatureCode('park', { code: '*7' }))
      .rejects.toMatchObject({ status: 409, code: 'code_taken', field: 'code', details: { conflict: '*76' } });
  });

  it('code_taken — vaqt sharti toggle_code bilan toʻqnashsa ham', async () => {
    // seed vaqt sharti toggle_code = '*21'
    await expect(client.updateFeatureCode('echo_test', { code: '*21' }))
      .rejects.toMatchObject({ status: 409, code: 'code_taken', field: 'code', details: { conflict: '*21' } });
  });

  it('not_found — mavjud bo\'lmagan feature', async () => {
    await expect(client.updateFeatureCode('unknown_feature', { code: '*99' }))
      .rejects.toMatchObject({ status: 404, code: 'not_found' });
  });

  it('oʻzgarishsiz PATCH — apply.status=unchanged', async () => {
    const { items } = await client.listFeatureCodes();
    const fc = items.find((i) => i.feature === 'dnd_toggle')!;
    const res = await client.updateFeatureCode('dnd_toggle', { code: fc.code, enabled: fc.enabled });
    expect(res.apply).toEqual({ status: 'unchanged', revision: null, message: null });
  });

  it('reset — standart kodga qaytaradi va enabled=true qiladi', async () => {
    await client.updateFeatureCode('dnd_toggle', { code: '*77', enabled: false });
    const res = await client.resetFeatureCode('dnd_toggle');
    expect(res.item.code).toBe('*76');
    expect(res.item.enabled).toBe(true);
  });
});

describe('fake client — M2a konferensiya (S25)', () => {
  let client: ApiClient;
  beforeEach(async () => { client = createFakeClient(); await asAdmin(client); });

  it('roʻyxat — seed qilingan 2 ta konferensiya', async () => {
    const { items } = await client.listConferences();
    expect(items).toHaveLength(2);
    expect(items[0]?.has_pin).toBe(true);
  });

  it('yaratish — raqam ko\'rsatilmasa avtomatik beriladi', async () => {
    const res = await client.createConference({ name: 'Yangi xona', record: false, max_members: null });
    expect(res.item.number).toBeTruthy();
    expect(res.item.has_pin).toBe(false);
    expect(res.apply.status).toBe('applied');
  });

  it('bad_pin — PIN notoʻgʻri formatda bo\'lsa 422', async () => {
    await expect(client.createConference({ name: 'X', pin: '12', record: false, max_members: null }))
      .rejects.toMatchObject({ status: 422, code: 'bad_pin', field: 'pin' });
  });

  it('bad_max_members — chegaradan tashqari 422', async () => {
    await expect(client.createConference({ name: 'X', record: false, max_members: 1 }))
      .rejects.toMatchObject({ status: 422, code: 'bad_max_members', field: 'max_members' });
  });

  it('number_taken — band raqam bilan yaratib bo\'lmaydi', async () => {
    await expect(client.createConference({ name: 'X', number: '101', record: false, max_members: null }))
      .rejects.toMatchObject({ status: 409, code: 'number_taken' });
  });

  it('tahrirlash — PATCH\'da berilmagan maydon o\'zgarmaydi, aniq null tozalaydi', async () => {
    const { items } = await client.listConferences();
    const conf = items.find((c) => c.id === 'conf-boss')!;
    const res = await client.updateConference(conf.id, { pin: null, updated_at: conf.updated_at });
    expect(res.item.has_pin).toBe(false);
    expect(res.item.has_admin_pin).toBe(true); // berilmagan — o'zgarmadi
  });

  it('in_use — boshqa joyda ishlatilayotgan konferensiyani o\'chirib bo\'lmaydi', async () => {
    const { items } = await client.listConferences();
    const conf = items[0]!;
    await client.createInboundRoute({ name: 'Konf marshrut', did: '998712000077', cid: null, target_id: conf.target_id, enabled: true });
    await expect(client.deleteConference(conf.id)).rejects.toMatchObject({ status: 409, code: 'in_use' });
  });

  it('ishlatilmayotgan konferensiya muammosiz oʻchadi', async () => {
    const { items } = await client.listConferences();
    const conf = items.find((c) => c.id === 'conf-sales')!;
    await client.deleteConference(conf.id);
    const after = await client.listConferences();
    expect(after.items.find((c) => c.id === conf.id)).toBeUndefined();
  });

  it('manzil tanlagichda konferensiya target sifatida ko\'rinadi', async () => {
    const { items } = await client.listTargets({ kind: 'conference' });
    expect(items.length).toBe(2);
    expect(items[0]?.kind).toBe('conference');
  });
});

describe('fake client — M2a qora roʻyxat (S27)', () => {
  let client: ApiClient;
  beforeEach(async () => { client = createFakeClient(); await asAdmin(client); });

  it('roʻyxat — seed qilingan 2 ta yozuv', async () => {
    const { items } = await client.listBlacklist({});
    expect(items).toHaveLength(2);
  });

  it('qo\'shish — raqam normalizatsiya qilinadi (bo\'shliq/tire/parentez/boshidagi +)', async () => {
    const res = await client.createBlacklistEntry({ number: '+998 (90) 111-22-33', reason: 'Test' });
    expect(res.item.number).toBe('998901112233');
  });

  it('exists — normalizatsiyadan keyin bir xil raqam ikkinchi marta qoʻshilmaydi', async () => {
    await expect(client.createBlacklistEntry({ number: '998 998 88 77 66' }))
      .rejects.toMatchObject({ status: 409, code: 'exists', field: 'number' });
  });

  it('bad_number — notoʻgʻri raqam 422', async () => {
    await expect(client.createBlacklistEntry({ number: 'ab' }))
      .rejects.toMatchObject({ status: 422, code: 'bad_number', field: 'number' });
  });

  it('"Yashirin raqamlarni bloklash" — anonymous yozuviga olib keladi', async () => {
    await client.deleteBlacklistEntry('anonymous');
    const res = await client.createBlacklistEntry({ number: '' });
    expect(res.item.number).toBe('anonymous');
  });

  it('o\'chirish — mavjud bo\'lmagan raqam 404', async () => {
    await expect(client.deleteBlacklistEntry('999999999')).rejects.toMatchObject({ status: 404, code: 'not_found' });
  });

  it('o\'chirish — muvaffaqiyatli', async () => {
    await client.deleteBlacklistEntry('998998887766');
    const { items } = await client.listBlacklist({});
    expect(items.find((b) => b.number === '998998887766')).toBeUndefined();
  });
});

describe('fake client — M2a park (S26, faqat ko\'rish)', () => {
  it('GET /parking — lot/slots/parked ro\'yxati (admin)', async () => {
    const client = createFakeClient();
    await asAdmin(client);
    const res = await client.parking();
    expect(res.lot).toBe('700');
    expect(res.slots).toBe('701-720');
    expect(res.parked.length).toBeGreaterThan(0);
  });

  it('operator uchun 403 — /parking faqat admin uchun', async () => {
    const client = createFakeClient();
    await asOperator(client);
    await expect(client.parking()).rejects.toMatchObject({ status: 403, code: 'forbidden' });
  });
});

describe('isApiError', () => {
  it('ApiError ni to\'g\'ri taniydi', async () => {
    const client = createFakeClient();
    try {
      await client.login('notuser', 'notopass');
      throw new Error('kutilmagan muvaffaqiyat');
    } catch (e) {
      expect(isApiError(e)).toBe(true);
    }
  });
});
