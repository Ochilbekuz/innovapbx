import { useEffect, useMemo, useState } from 'react';
import { Badge, StatusPill } from '@/ui/Status';
import { Segmented } from '@/ui/Field';
import { DestinationPicker } from '@/pbx/DestinationPicker';
import { CallFlow } from '@/pbx/CallFlow';
import { WeekGrid } from '@/pbx/WeekGrid';
import { AudioPlayer } from '@/pbx/AudioPlayer';
import { PatternEditor, type PatternRow } from '@/pbx/PatternEditor';
import { SortableList } from '@/pbx/SortableList';
import { SoftphoneChip, SoftphonePanel, type CallState } from '@/pbx/Softphone';
import { LogViewer, type LogLine } from '@/pbx/LogViewer';
import { emptyWeek, paint } from '@/domain/week';
import type { Destination } from '@/domain/destination';
import { catalog, catalogFixed, flowRoot, makeLog, makeToneUrl, trunks } from './demo';
import { Section } from './Section';

export function PickerSection() {
  const [a, setA] = useState<Destination | null>({ kind: 'queue', targetId: 'q1' });
  const [b, setB] = useState<Destination | null>(null);
  const [c, setC] = useState<Destination | null>({ kind: 'extension', targetId: 'e1099' });
  const [d, setD] = useState<Destination | null>({ kind: 'external', number: '+998 90 318 42 07' });
  return (
    <Section
      id="manzil"
      index="13"
      title="Manzil tanlagich"
      lead="Qoʻngʻiroq qayerga boradi — PBXʼning markaziy savoli. Bitta komponent toʻqqiz turni biladi: chapda tur, oʻngda qidiruv. Obyekt oʻchirilgan boʻlsa havola «singan» koʻrinadi va saqlashga yoʻl qoʻymaydi."
      used="S07, S08, S09, S10, S21, S28"
    >
      <div className="grid gap-x-6 gap-y-5 rounded-lg border border-line bg-surface p-5 shadow-card md:grid-cols-2">
        <DestinationPicker label="DID +998 71 200 00 00 → manzil" value={a} onChange={setA} catalog={catalog} hint="Ish vaqtida shu yerga tushadi" />
        <DestinationPicker label="IVR: «3» tugmasi" value={b} onChange={setB} catalog={catalog} required />
        <DestinationPicker label="Texnik yordam: agent yoʻq boʻlsa" value={c} onChange={setC} catalog={catalog} />
        <DestinationPicker label="Tungi yoʻnaltirish" value={d} onChange={setD} catalog={catalog} />
      </div>
    </Section>
  );
}

export function FlowSection() {
  const [fixed, setFixed] = useState(false);
  return (
    <Section
      id="oqim"
      index="14"
      title="Qoʻngʻiroq yoʻli grafigi"
      lead="FreePBXʼda yoʻq: DIDʼdan boshlab qoʻngʻiroq qaysi tarmoqlardan oʻtishini bir qarashda koʻrsatadi. Halqa — uzuq chegara, singan manzil — qizil. Hozircha faqat koʻrish; tahrir keyingi bosqichda."
      used="S07, S09"
    >
      <div className="mb-3 flex items-center gap-3">
        <span className="text-sm text-muted">Holat:</span>
        <Segmented label="Oqim holati" value={fixed ? 'ok' : 'bad'} onChange={(v) => setFixed(v === 'ok')} options={[{ value: 'bad', label: 'Muammoli' }, { value: 'ok', label: 'Tuzatilgan' }]} />
      </div>
      <CallFlow did="+998 71 200 00 00" root={flowRoot} catalog={fixed ? catalogFixed : catalog} />
    </Section>
  );
}

export function WeekSection() {
  const [week, setWeek] = useState(() => {
    let w = emptyWeek();
    for (let d = 0; d < 5; d++) w = paint(w, d, 9, 18, true);
    w = paint(w, 4, 13, 14, false);
    return paint(w, 5, 10, 14, true);
  });
  return (
    <Section id="hafta" index="15" title="Hafta setkasi" lead="Bosib sudrab boʻyaysiz; klaviaturada strelka + Space, Shift+strelka — boʻyab yurish. Pastdagi qator — jadvalning soʻz bilan tavsifi, screen reader ham shuni oʻqiydi." used="S08">
      <WeekGrid value={week} onChange={setWeek} />
      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
        <span className="text-muted">Bayramlar:</span>
        {['01.01 Yangi yil', '08.03 Xotin-qizlar kuni', '21.03 Navroʻz', '09.05 Xotira kuni', '01.09 Mustaqillik'].map((h) => (
          <Badge key={h} mono>{h}</Badge>
        ))}
      </div>
    </Section>
  );
}

export function AudioSection() {
  const url = useMemo(() => makeToneUrl(), []);
  useEffect(() => () => URL.revokeObjectURL(url), [url]);
  return (
    <Section id="audio" index="16" title="Audio pleer" lead="Toʻliq — audio kutubxona va ovozli pochtada; qator ichida — qoʻngʻiroqlar tarixida. Toʻlqin ustida strelkalar 5 s, Shift bilan 15 s suradi." used="S11, S12, S23">
      <div className="grid gap-3 lg:grid-cols-2">
        <AudioPlayer src={url} title="Salomlashuv — ish vaqti (uz)" meta="WAV · 8 kHz · 0:09" seed={11} />
        <AudioPlayer src={null} title="Eski kutish musiqasi" meta="MP3" />
        <div className="flex items-center gap-4 rounded-lg border border-line bg-surface px-3 py-2 shadow-card lg:col-span-2">
          <span className="num w-16 text-sm text-muted">10:42</span>
          <span className="num w-36 text-sm text-fg">+998 90 318 42 07</span>
          <span className="hidden w-24 text-sm text-muted md:block">→ 101</span>
          <div className="min-w-0 flex-1"><AudioPlayer src={url} variant="inline" seed={23} /></div>
        </div>
      </div>
    </Section>
  );
}

export function PatternSection() {
  const [rows, setRows] = useState<PatternRow[]>([
    { id: 'r1', prepend: '', prefix: '', pattern: '998XXXXXXXXX', callerId: '' },
    { id: 'r2', prepend: '998', prefix: '8', pattern: 'XXXXXXXXX', callerId: '712000000' },
    { id: 'r3', prepend: '', prefix: '9', pattern: '00[1-9].', callerId: '' },
    { id: 'r4', prepend: '', prefix: '', pattern: '9[2-7.', callerId: '' },
  ]);
  return (
    <Section id="naqsh" index="17" title="Terish naqshi muharriri" lead="Har qator — bitta qoida; tekshiruv yozayotganda ishlaydi va xato belgining tagiga chiziq tortadi. Pastdagi sinov raqami qaysi qoidaga tushishini va trunkka nima ketishini koʻrsatadi." used="S22">
      <PatternEditor rows={rows} onChange={setRows} />
    </Section>
  );
}

export function SortSection() {
  const [items, setItems] = useState(trunks);
  return (
    <Section id="tartib" index="18" title="Tartib roʻyxati" lead="Chiquvchi marshrutda trunklar ketma-ketligi: birinchisi band yoki oflayn boʻlsa — keyingisi. Tutqichdan sudrang yoki Space bilan koʻtarib, strelkalar bilan koʻchiring." used="S10, S21, S22">
      <div className="max-w-2xl">
        <SortableList
          label="Trunklar ketma-ketligi"
          items={items}
          onChange={setItems}
          itemId={(t) => t.id}
          itemLabel={(t) => t.name}
          render={(t) => (
            <>
              <span className="w-32 truncate font-medium text-fg">{t.name}</span>
              <span className="num hidden flex-1 truncate text-sm text-muted sm:block">{t.host}</span>
              <span className="num text-sm text-muted">{t.channels} kanal</span>
              <StatusPill status={t.status} />
            </>
          )}
        />
      </div>
    </Section>
  );
}

export function SoftphoneSection() {
  const [s1, setS1] = useState<CallState>('idle');
  const [s2, setS2] = useState<CallState>('incoming');
  const [s3, setS3] = useState<CallState>('hold');
  return (
    <Section id="softfon" index="19" title="Softfon paneli" lead="Headerʼda ixcham tugma, bosilganda panel. Suhbat paytida oltin «jonli» nuqta; ushlab turish — alohida, matn bilan." used="S16, S30">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <SoftphoneChip state="idle" />
        <SoftphoneChip state="incoming" />
        <SoftphoneChip state="talking" />
      </div>
      <div className="flex flex-wrap items-start gap-4">
        <SoftphonePanel state={s1} onState={setS1} />
        <SoftphonePanel state={s2} onState={setS2} />
        <SoftphonePanel state={s3} onState={setS3} />
      </div>
    </Section>
  );
}

export function LogSection() {
  const [lines, setLines] = useState<LogLine[]>(() => Array.from({ length: 18 }, (_, i) => makeLog(i)));
  const [live, setLive] = useState(false);
  useEffect(() => {
    if (!live) return;
    const t = setInterval(() => setLines((ls) => [...ls.slice(-400), makeLog(ls.length + 1000)]), 1200);
    return () => clearInterval(t);
  }, [live]);
  return (
    <Section id="log" index="20" title="Log koʻruvchi" lead="Asterisk CLI — faqat oʻqish. Daraja boʻyicha filtr, qidiruv mos joyni oltin bilan belgilaydi. Yuqoriga aylantirsangiz jonli kuzatish oʻzi toʻxtaydi." used="S36">
      <LogViewer lines={lines} live={live} onLiveChange={setLive} />
    </Section>
  );
}
