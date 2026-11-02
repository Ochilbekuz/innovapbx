import { useState } from 'react';
import { Download, Phone, Plus, Save, Search, Trash2, Upload } from 'lucide-react';
import { Button } from '@/ui/Button';
import { Field, Input, Segmented, Select, Textarea } from '@/ui/Field';
import { Checkbox, Toggle } from '@/ui/Toggle';
import { Tabs } from '@/ui/Tabs';
import { Drawer, DialogClose, Modal } from '@/ui/Dialog';
import { ToastCard, useToast, type ToastInput } from '@/ui/Toast';
import { Badge, LiveDot, LiveTag, StatusPill, type Status } from '@/ui/Status';
import { HealthList, HealthStrip } from '@/ui/Health';
import { Kpi } from '@/ui/Kpi';
import { DataTable, type Column, type TableState } from '@/ui/Table';
import { extensions, health, type ExtRow } from './demo';
import { Panel, Section, Specimen } from './Section';

export function ButtonSection() {
  return (
    <Section id="tugma" index="04" title="Tugma" lead="Bitta asosiy amal — bitta toʻq sariq tugma. Qolgani ikkinchi darajali yoki shaffof. Yuklanayotganda yozuv saqlanadi, kenglik sakramaydi." used="hammasi">
      <Panel className="grid gap-6 md:grid-cols-2">
        <Specimen label="Variantlar">
          <Button variant="primary" icon={<Save />}>Saqlash</Button>
          <Button variant="secondary" icon={<Upload />}>CSV import</Button>
          <Button variant="ghost">Bekor qilish</Button>
          <Button variant="danger" icon={<Trash2 />}>Oʻchirish</Button>
          <Button variant="danger-ghost">Bloklash</Button>
        </Specimen>
        <Specimen label="Oʻlchamlar · 28 / 32 / 40">
          <Button variant="primary" size="sm">Kichik</Button>
          <Button variant="primary" size="md">Oʻrta</Button>
          <Button variant="primary" size="lg" icon={<Phone />}>Katta</Button>
          <Button size="md" iconOnly icon={<Download />} aria-label="Yuklab olish" />
        </Specimen>
        <Specimen label="Holatlar">
          <Button variant="primary" loading>Saqlanmoqda</Button>
          <Button variant="primary" disabled>Oʻchirilgan</Button>
          <Button variant="secondary" loading>Tekshirilmoqda</Button>
          <Button variant="secondary" className="outline outline-2 outline-offset-2 outline-focus-ring">Fokus (klaviatura)</Button>
        </Specimen>
        <Specimen label="Panel boshida">
          <Button variant="primary" icon={<Plus />}>Ichki raqam</Button>
          <Button variant="secondary">Ommaviy qoʻshish</Button>
        </Specimen>
      </Panel>
    </Section>
  );
}

export function FormSection() {
  const [codec, setCodec] = useState('opus');
  return (
    <Section id="forma" index="05" title="Forma maydonlari" lead="Yorliq har doim tepada, izoh pastda; xato izoh oʻrnini egallaydi va ikon bilan keladi. Raqamli maydonlar — mono shriftda." used="S01, S02, S05, S06, S32">
      <Panel className="grid gap-x-6 gap-y-5 md:grid-cols-2 xl:grid-cols-3">
        <Field label="Ism (CallerID nomi)" hint="Ichki qoʻngʻiroqda ekranda chiqadi">
          {(a) => <Input {...a} defaultValue="Dilnoza Karimova" />}
        </Field>
        <Field label="Ichki raqam" required error="101 band — «Dilnoza Karimova»ga tegishli">
          {(a) => <Input {...a} mono defaultValue="101" />}
        </Field>
        <Field label="Tashqi IP" hint="NAT ortida boʻlsa majburiy" aside="ixtiyoriy">
          {(a) => <Input {...a} mono placeholder="203.0.113.10" />}
        </Field>
        <Field label="Asosiy kodek">
          {(a) => (
            <Select {...a} value={codec} onValueChange={setCodec} options={[
              { value: 'opus', label: 'Opus', hint: '48 kHz' },
              { value: 'g722', label: 'G.722', hint: 'HD' },
              { value: 'alaw', label: 'G.711 A-law', hint: 'trunk' },
              { value: 'g729', label: 'G.729', hint: 'litsenziya', disabled: true },
            ]} />
          )}
        </Field>
        <Field label="SIP parol" hint="Qurilmaga avtoprovizioning orqali yuboriladi">
          {(a) => <Input {...a} mono type="password" defaultValue="placeholder-pass" readOnly />}
        </Field>
        <Field label="Qidiruv (kichik)">
          {(a) => <Input {...a} size="sm" leading={<Search />} placeholder="Raqam yoki nom" />}
        </Field>
        <Field label="Oʻchirilgan maydon" hint="Faqat «Tizim» roli oʻzgartiradi">
          {(a) => <Input {...a} mono defaultValue="10000–20000" disabled />}
        </Field>
        <Field label="Izoh" className="md:col-span-2" hint="Faqat adminlar koʻradi">
          {(a) => <Textarea {...a} rows={2} defaultValue="Qabulxona telefoni, tushlikda 115 ga yoʻnaltiriladi." />}
        </Field>
      </Panel>
    </Section>
  );
}

export function ToggleSection() {
  const [rec, setRec] = useState(true);
  const [night, setNight] = useState(false);
  const [chk, setChk] = useState<boolean | 'indeterminate'>('indeterminate');
  const [view, setView] = useState<'day' | 'week' | 'month'>('week');
  return (
    <Section id="toggle" index="06" title="Toggle, belgilash, segment" lead="Toggle — darhol taʼsir qiladigan sozlama uchun. Forma ichida, «Saqlash»ni kutadigan joyda — belgilash katagi." used="S05, S08, S24">
      <Panel className="grid gap-6 md:grid-cols-3">
        <div className="space-y-4">
          <Toggle label="Suhbatni yozib olish" description="Hamma kiruvchi va chiquvchi" checked={rec} onCheckedChange={setRec} />
          <Toggle label="Tungi rejim (majburiy)" description="Ish vaqti jadvalidan ustun turadi" checked={night} onCheckedChange={setNight} />
          <Toggle label="Faqat admin yoqadi" description="Oʻchirilgan holat" disabled defaultChecked />
        </div>
        <div className="space-y-3">
          <span className="eyebrow block">Belgilash katagi</span>
          <label className="flex items-center gap-2 text-base"><Checkbox checked={chk} onCheckedChange={setChk} aria-label="Hammasi" />Hammasi (qisman)</label>
          <label className="flex items-center gap-2 text-base"><Checkbox checked onCheckedChange={() => undefined} aria-label="Opus" />Opus</label>
          <label className="flex items-center gap-2 text-base text-disabled"><Checkbox checked={false} disabled onCheckedChange={() => undefined} aria-label="G.729" />G.729</label>
        </div>
        <div className="space-y-3">
          <span className="eyebrow block">Segment</span>
          <Segmented label="Davr" size="md" value={view} onChange={setView} options={[{ value: 'day', label: 'Kun' }, { value: 'week', label: 'Hafta' }, { value: 'month', label: 'Oy' }]} />
        </div>
      </Panel>
    </Section>
  );
}

export function TabsSection() {
  return (
    <Section id="tablar" index="07" title="Tablar" lead="Ichki raqam kartasida bitta sahifa — koʻp boʻlim. Xato bor tab qizil nuqta oladi, screen reader «xato bor» deb oʻqiydi." used="S05, S06, S10">
      <Panel>
        <Tabs
          label="Ichki raqam 101"
          items={[
            { value: 'main', label: 'Asosiy', content: <p className="text-base text-muted">SIP login, parol, CallerID va ovozli pochta.</p> },
            { value: 'devices', label: 'Qurilmalar', count: 3, content: <p className="text-base text-muted">Yealink T54W, brauzer softfoni, Zoiper.</p> },
            { value: 'follow', label: 'Yoʻnaltirish', invalid: true, content: <p className="text-base text-danger">Tashqi raqam yaroqsiz.</p> },
            { value: 'codecs', label: 'Kodeklar', content: <p className="text-base text-muted">Opus, G.722, A-law.</p> },
            { value: 'nat', label: 'NAT', disabled: true, content: null },
          ]}
        />
      </Panel>
    </Section>
  );
}

export function StatusSection() {
  const [s, setS] = useState<Status>('online');
  return (
    <Section id="holat" index="08" title="Holat belgisi va nishonlar" lead="Holat shakl bilan ham ajraladi: toʻla doira, halqa, romb, chiziq. Oltin nuqta — «jonli maʼlumot», hech qachon ogohlantirish emas." used="S04, S06, S29">
      <Panel className="grid gap-6 md:grid-cols-3">
        <Specimen label="Status pill">
          <StatusPill status="online" />
          <StatusPill status="offline" />
          <StatusPill status="error">Registratsiya xato</StatusPill>
          <StatusPill status="disabled" />
        </Specimen>
        <Specimen label="Jonli yangilanadi">
          <StatusPill status={s} live />
          <Button size="sm" variant="ghost" onClick={() => setS((x) => (x === 'online' ? 'error' : x === 'error' ? 'offline' : 'online'))}>Holatni almashtirish</Button>
          <LiveTag />
          <span className="inline-flex items-center gap-1.5 text-sm text-muted"><LiveDot /> 18 ta faol kanal</span>
        </Specimen>
        <Specimen label="Nishon (badge)">
          <Badge>PJSIP</Badge>
          <Badge tone="accent" mono>r142</Badge>
          <Badge tone="success">TLS</Badge>
          <Badge tone="warning">Muddati 6 kun</Badge>
          <Badge tone="danger">Toʻqnashuv</Badge>
          <Badge tone="info">Import</Badge>
        </Specimen>
      </Panel>
    </Section>
  );
}

export function HealthKpiSection() {
  return (
    <Section id="soglik" index="09" title="Sogʻlik indikatori va KPI" lead="Sariq va qizil yolgʻiz kelmaydi — yonida doim sabab yoziladi. KPI oʻzgarishi «yaxshi/yomon» rangiga boʻyalmaydi: kiruvchi qoʻngʻiroq oshishi yaxshimi — biznesga bogʻliq." used="S03, S06, S13">
      <div className="grid gap-4 xl:grid-cols-[1fr_1.15fr]">
        <div className="space-y-3">
          <HealthList items={health} />
          <div className="flex items-center gap-3 text-sm text-muted">
            <HealthStrip items={health} /> ixcham koʻrinish — yon menyu pastida
          </div>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Kpi label="Bugungi qoʻngʻiroqlar" value="1 284" delta={12} series={[22, 30, 28, 41, 38, 52, 49, 61, 58, 66]} />
          <Kpi label="Javobsiz" value="37" delta={-8} series={[9, 7, 8, 6, 7, 5, 6, 4, 5, 3]} />
          <Kpi label="Oʻrtacha kutish" value="00:41" unit="daq" delta={0} />
          <Kpi label="SLA (20 s ichida)" value={null} emptyText="Navbat hali qoʻngʻiroq olmagan" />
          <Kpi label="Faol kanallar" value="" loading />
          <Kpi label="Trunk bandligi" value="18" unit="/ 50" delta={4} series={[8, 10, 14, 12, 16, 18]} />
        </div>
      </div>
    </Section>
  );
}

const columns: Column<ExtRow>[] = [
  { key: 'num', header: 'Raqam', width: '96px', sortValue: (r) => r.num, cell: (r) => <span className="num font-medium">{r.num}</span> },
  { key: 'name', header: 'Ism', sortValue: (r) => r.name, cell: (r) => r.name },
  { key: 'dept', header: 'Boʻlim', sortValue: (r) => r.dept, cell: (r) => <span className="text-muted">{r.dept}</span> },
  { key: 'status', header: 'Holat', sortValue: (r) => r.status, cell: (r) => <StatusPill status={r.status} /> },
  { key: 'device', header: 'Qurilma', cell: (r) => <span className="text-muted">{r.device}</span> },
  { key: 'calls', header: 'Bugun', align: 'right', sortValue: (r) => r.calls, cell: (r) => <span className="num">{r.calls}</span> },
];

export function TableSection() {
  const [state, setState] = useState<TableState | 'empty'>('ready');
  return (
    <Section id="jadval" index="10" title="Jadval" lead="Admin kunini jadvalda oʻtkazadi: qidiruv, saralash, ommaviy tanlash, sahifalash. Qator 44 px — zich, lekin koʻz adashmaydi. Raqam ustuni mono, oʻngga tekislangan son." used="S04, S06, S12, S22">
      <div className="mb-3 flex items-center gap-3">
        <span className="text-sm text-muted">Holat:</span>
        <Segmented
          label="Jadval holati"
          value={state}
          onChange={setState}
          options={[{ value: 'ready', label: 'Maʼlumot' }, { value: 'loading', label: 'Yuklanmoqda' }, { value: 'empty', label: 'Boʻsh' }, { value: 'error', label: 'Xato' }]}
        />
      </div>
      <DataTable
        caption="Ichki raqamlar"
        rows={state === 'empty' ? [] : extensions}
        columns={columns}
        rowId={(r) => r.num}
        searchText={(r) => `${r.num} ${r.name} ${r.dept}`}
        state={state === 'empty' ? 'ready' : state}
        pageSize={6}
        onRetry={() => setState('ready')}
        empty={{ title: 'Hali ichki raqam yoʻq', body: 'Birinchisini qoʻshing yoki eski PBXʼdan CSV import qiling.', action: <Button variant="primary" size="sm" icon={<Plus />}>Ichki raqam</Button> }}
        toolbar={<><Button size="sm" variant="ghost" icon={<Download />}>Eksport</Button><Button size="sm" variant="primary" icon={<Plus />}>Qoʻshish</Button></>}
        bulkActions={(ids) => (
          <>
            <Button size="sm" variant="secondary">Boʻlimga koʻchirish</Button>
            <Button size="sm" variant="danger-ghost" icon={<Trash2 />}>Oʻchirish ({ids.length})</Button>
          </>
        )}
      />
    </Section>
  );
}

export function DialogSection() {
  const [dirty, setDirty] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const [confirm, setConfirm] = useState(false);
  return (
    <Section id="modal" index="11" title="Modal va yon panel" lead="Modal — qisqa tasdiq. Yon panel — jadvaldan chiqmasdan tahrirlash. Saqlanmagan oʻzgarish bor boʻlsa, yopish soʻraladi. Fokus ichkarida qamaladi, Esc yopadi, fokus tugmaga qaytadi." used="hammasi">
      <Panel className="flex flex-wrap gap-2">
        <Modal
          size="sm"
          title="Trunkni oʻchirasizmi?"
          description="«Ucell zaxira» 2 ta chiquvchi marshrutda ishlatilmoqda."
          trigger={<Button variant="danger" icon={<Trash2 />}>Oʻchirish (tasdiq)</Button>}
          footer={<><DialogClose asChild><Button variant="ghost">Bekor qilish</Button></DialogClose><DialogClose asChild><Button variant="danger">Ha, oʻchirish</Button></DialogClose></>}
        >
          <p className="text-base text-muted">Marshrutlar keyingi trunkka oʻtadi. Bu amalni ortga qaytarib boʻlmaydi, lekin reviziya tarixida qoladi.</p>
        </Modal>
        <Button variant="secondary" onClick={() => { setDrawer(true); setDirty(false); }}>Ichki raqamni tahrirlash (panel)</Button>
        <Drawer
          open={drawer}
          onOpenChange={setDrawer}
          title="Ichki raqam 101"
          description="Dilnoza Karimova · Sotuv"
          onAttemptClose={() => { if (dirty) { setConfirm(true); return false; } return true; }}
          footer={<><Button variant="ghost" onClick={() => (dirty ? setConfirm(true) : setDrawer(false))}>Yopish</Button><Button variant="primary" onClick={() => setDrawer(false)}>Saqlash</Button></>}
        >
          <div className="space-y-4">
            <Field label="Ism">{(a) => <Input {...a} defaultValue="Dilnoza Karimova" onChange={() => setDirty(true)} />}</Field>
            <Field label="Ichki raqam" hint="Oʻzgartirsangiz, qurilma qayta registratsiya qiladi">{(a) => <Input {...a} mono defaultValue="101" onChange={() => setDirty(true)} />}</Field>
            {dirty && <p className="rounded-sm bg-warning-soft px-2.5 py-1.5 text-sm text-on-warning-soft">Saqlanmagan oʻzgarish bor</p>}
          </div>
        </Drawer>
        <Modal
          size="sm"
          open={confirm}
          onOpenChange={setConfirm}
          title="Oʻzgarishlar saqlanmadi"
          description="Panelni yopsangiz, kiritganingiz yoʻqoladi."
          footer={<><Button variant="ghost" onClick={() => setConfirm(false)}>Tahrirga qaytish</Button><Button variant="danger" onClick={() => { setConfirm(false); setDirty(false); setDrawer(false); }}>Yoʻqotib yopish</Button></>}
        />
      </Panel>
    </Section>
  );
}

const TOASTS: ToastInput[] = [
  { kind: 'success', title: 'Navbat saqlandi', description: 'Dialplan r143 qoʻllandi — 180 ms.' },
  { kind: 'not-applied', title: 'PBXʼga qoʻllanmadi', description: 'Baza saqlandi, lekin r143 tekshiruvdan oʻtmadi: «IVR 700 → IVR 700» halqasi. Asterisk r142 da ishlashda davom etyapti.', action: { label: 'Halqani koʻrsatish', altText: 'Qoʻngʻiroq yoʻlini ochish', onClick: () => undefined } },
  { kind: 'error', title: 'Trunk ulanmadi', description: 'sip.uztelecom.uz: 401 Unauthorized — login yoki parolni tekshiring.' },
  { kind: 'info', title: 'Import navbatda', description: '148 ta ichki raqam — tugagach xabar beramiz.' },
];

export function ToastSection() {
  const toast = useToast();
  return (
    <Section id="toast" index="12" title="Bildirishnoma (toast)" lead="Muvaffaqiyat oʻzi yoʻqoladi. Xato va «PBXʼga qoʻllanmadi» — yoʻq: admin oʻqib, harakat qilishi kerak. Oxirgisi bizga xos: maʼlumot saqlangan, lekin Asterisk eski reviziyada qolgan." used="hammasi">
      <div className="grid items-start gap-3 md:grid-cols-2">
        {TOASTS.map((t) => <ToastCard key={t.kind} item={t} static />)}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {TOASTS.map((t) => <Button key={t.kind} size="sm" variant="ghost" onClick={() => toast(t)}>Koʻrsatish: {t.title}</Button>)}
      </div>
    </Section>
  );
}
