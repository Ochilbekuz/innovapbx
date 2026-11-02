# Innova PBX — komponentlar spetsifikatsiyasi

Manba tokenlar: `tokens.json` (light), `tokens.dark.json` (dark), CSS: `tokens.css`, Tailwind: `web/tailwind.config.ts`.
Kod: `web/src/ui/*` (primitivlar), `web/src/pbx/*` (telefoniya komponentlari), `web/src/shell/AppShell.tsx`.
Jonli namuna: `web/` → `npm run build && npm run preview` → `/design` (`?theme=dark`).

Umumiy qoidalar:
- Komponent faqat rol klassini yozadi (`bg-surface`, `text-muted`, `border-input`, `bg-accent`). Xom hex taqiqlanadi.
- `brand #D7621D` — belgi, grafik, faol chiziq, fokus halqasi. Tugma/havola foni — `accent` (light #AB4C17, dark #EA7A2E).
- `live` (oltin) — faqat «jonli maʼlumot» belgisi; ogohlantirish emas. Ogohlantirish — `warning` + uchburchak ikon + matn.
- `danger` hech qachon faqat rang bilan kelmaydi: ikon (OctagonX/CircleAlert/Link2Off) + matn.
- Focus-visible: 2px `focus-ring`, offset 2px (global `:focus-visible`). Sichqoncha bosganda halqa chiqmaydi.
- Harakat: 120/200/320 ms, `cubic-bezier(0.22,1,0.36,1)`. `prefers-reduced-motion` — barcha oʻtish va pulsatsiya oʻchadi.
- Raqamlar (ichki raqam, IP, vaqt, hisob) — `.num`: Plex Mono, `tabular-nums`, slashed zero.
- Matnda oʻzbek apostrofi: ʻ (U+02BB) oʻ/gʻ uchun, ʼ (U+02BC) tutuq uchun. `’`/`'` ishlatilmaydi.

---

```
Button                                                      web/src/ui/Button.tsx
  variants  primary (bitta ekranda bitta), secondary, ghost, danger, danger-ghost
  sizes     sm 28px (jadval qatori), md 32px (sukut), lg 40px (sehrgar, softfon); iconOnly — kvadrat
  states    default, hover (accent-hover / surface-2), active (translate-y 0.5px), focus-visible (ring),
            disabled (opacity, cursor-not-allowed), loading (LoaderCircle aylanadi, yozuv qoladi, kenglik sakramaydi)
  tokens    bg accent / on-accent; secondary bg surface + border-input; danger bg danger / on-danger;
            radius md; font sm-base/500; ikon 16px, gap 8px
  a11y      haqiqiy <button>; loading → aria-busy + disabled; iconOnly → aria-label TS darajasida majburiy;
            Kbd — klaviatura yorligʻi (aria-hidden emas, oʻqiladi)
  used on   hammasi; danger — S05, S06, S10, S21 (oʻchirish tasdigʻi)
```

```
Input / Textarea / Select / Combobox / Segmented            web/src/ui/Field.tsx
  variants  Input: oddiy, mono (raqam/IP/naqsh), leading ikon, trailing slot; Textarea; Select (Radix);
            Combobox — DestinationPicker ichida (qarang); Segmented — 2–4 variantli tanlov
  sizes     sm 28, md 32, lg 40
  states    default, hover (border fg/60), focus-visible (border focus-ring + 2px ring 30%),
            invalid (border danger + izoh oʻrnida xato matni + CircleAlert), disabled (surface-2, text-disabled),
            read-only (faqat input/textarea: surface-2), placeholder (text-muted), empty
  tokens    bg surface, border-input (3:1), shadow-inset, radius md, text base; label sm/600; izoh sm text-muted
  a11y      Field render-prop id beradi: <label for>, aria-describedby (izoh/xato), aria-invalid, aria-required;
            xato izohni almashtiradi (ikkalasi birga emas); «ixtiyoriy» yorligʻi oʻng burchakda;
            Select — Radix: Enter/Space ochadi, strelkalar, harf bilan qidirish, Esc yopadi;
            Segmented — role=radiogroup, strelkalar bilan tanlash, roving tabindex
  used on   S01, S02, S05, S06, S08–S10, S21, S22, S24, S32
```

```
Toggle / Checkbox                                           web/src/ui/Toggle.tsx
  variants  Toggle (darhol taʼsir qiladigan sozlama), Checkbox (formada, «Saqlash»ni kutadi; indeterminate)
  sizes     Toggle sm 16×28 (jadval qatori), md 20×36
  states    off, on (bg accent), hover, focus-visible, disabled (on/off ikkalasi), indeterminate (Checkbox)
  tokens    track border-input / accent, thumb surface + shadow-card, radius pill; label base/500, tavsif sm muted
  a11y      Radix Switch: role=switch, aria-checked, Space/Enter; <label for> bosilsa ham almashadi;
            tavsif aria-describedby; hideLabel — vizual yashirin, nom saqlanadi (testlangan: Toggle.test.tsx)
  used on   S05, S08, S24, S27
```

```
Tabs                                                        web/src/ui/Tabs.tsx
  variants  underline (sahifa ichidagi boʻlim), count bilan, invalid (xato bor)
  states    default, hover, active (2px brand chiziq + text-fg), focus-visible, disabled, invalid (qizil nuqta)
  tokens    border-b line, active border brand, text sm/500 muted → fg; count — Badge neutral
  a11y      Radix Tabs: role=tablist/tab/tabpanel, chap/oʻng strelka, Home/End; invalid → sr «(xato bor)»
  used on   S05, S06, S10
```

```
Modal / Drawer                                              web/src/ui/Dialog.tsx
  variants  Modal sm 420 (tasdiq), md 560 (qisqa forma); Drawer oʻngdan 480 (jadvaldan chiqmasdan tahrir)
  states    ochiq/yopiq (fade + pop-in / slide-in-right), dirty guard (saqlanmagan oʻzgarish — yopishdan oldin soʻraydi),
            loading (Button loading), xato (ichidagi Field xatolari)
  tokens    bg raised, shadow-modal, scrim 45%, radius lg, header xl font-display, footer border-t line
  a11y      Radix Dialog: role=dialog, aria-modal, aria-labelledby/describedby, fokus ichkarida qamaladi,
            Esc yopadi (onAttemptClose guard orqali), yopilganda fokus chaqirgan tugmaga qaytadi
  used on   hammasi (oʻchirish tasdigʻi), S04–S06 (Drawer)
```

```
Toast                                                       web/src/ui/Toast.tsx
  variants  success (4 s), error (yopilguncha), info (5 s), not-applied — «PBXʼga qoʻllanmadi» (yopilguncha)
  states    kirish/chiqish animatsiyasi, hover — taymer toʻxtaydi, harakat tugmasi (masalan «Halqani koʻrsatish»)
  tokens    bg raised, chap 3px chiziq: success / danger / info / danger; ikon CircleCheck / OctagonX / Info / RotateCcw;
            sarlavha base/600, matn sm muted, shadow-pop, z toast 70
  a11y      Radix Toast: region (F8), success/info — type=background (polite), error/not-applied — foreground (assertive);
            swipe va Esc yopadi; matn rang emas, sarlavhadan tushuniladi
  izoh      not-applied — bizga xos holat: maʼlumot bazada saqlangan, lekin dialplan kompilyatsiya/reload
            yiqilgan va Asterisk oldingi reviziyada qolgan (architecture.md: rolled_back)
  used on   hammasi
```

```
Table (DataTable)                                           web/src/ui/Table.tsx, domain/table.ts
  variants  qidiruv + filtr, ustun boʻyicha saralash, ommaviy tanlash, sahifalash; qator balandligi 44px
  states    data, loading (skeleton qatorlar, aria-busy), error (role=alert + «Qayta urinish»),
            empty (birinchi marta — harakatga chaqiruv), no-results (filtr — «Filtrni tozalash»),
            qator hover (surface-2), tanlangan (accent-soft), bulk bar (tanlanganlar soni + amallar)
  tokens    header 2xs/600 uppercase muted, bg surface-2/60; chiziq line; raqam ustuni mono, oʻngga tekis
  a11y      haqiqiy <table>; saralanadigan sarlavha — <button> + aria-sort; header checkbox indeterminate,
            har qator checkbox aria-label «Tanlash: 101»; sahifalash — nav + aria-label, joriy sahifa aria-current;
            «1–6 / 14» hisobi aria-live=polite (filtr/sahifa oʻzgarsa eʼlon qilinadi)
  used on   S04, S06, S10–S13, S17–S23, S25
```

```
Status pill / Badge / LiveDot                               web/src/ui/Status.tsx
  variants  online (toʻla doira, success), offline (halqa, status-offline), error (romb, danger),
            disabled (chiziq, uzuq chegara), warning; live — oltin pulsatsiyali nuqta; Badge tones: neutral,
            accent, success, warning, danger, info; mono
  sizes     22px (jadval), 20px (Badge)
  states    statik / live (pulsatsiya, reduced-motion'da toʻxtaydi)
  tokens    *-soft fon + on-*-soft matn; nuqta status-*; text xs/600
  a11y      holat shakl bilan ham farqlanadi (rangsiz koʻrishda ham); matn doim bor; LiveTag — «JONLI» soʻzi
  used on   S04, S06, S10, S16, S29
```

```
Health indicator                                            web/src/ui/Health.tsx
  variants  HealthList (dashboard kartasi: element, qiymat, sabab), HealthStrip (yon menyu pastida, ixcham)
  states    ok (CircleCheck, success), warn (TriangleAlert, warning, chap 3px chiziq), crit (OctagonX, danger, chiziq);
            sarlavhada eng yomon holat (worstLevel)
  tokens    bg surface, chiziq line, qiymat mono; sabab sm muted
  a11y      sariq/qizil hech qachon sababsiz emas; Strip — role=img + aria-label («1 ta ogohlantirish, 1 ta nosoz»)
  used on   S03, S06, S13
```

```
KPI card                                                    web/src/ui/Kpi.tsx
  variants  qiymat + birlik, oʻzgarish (delta), sparkline
  states    data, loading (skeleton, aria-busy), empty (null → «—» + izoh), delta 0 (Minus)
  tokens    label 2xs eyebrow, qiymat 2xl mono, delta sm; sparkline chart-1 + brand/10 maydon; min-h 112
  a11y      delta strelkasi neytral (fg) — «yaxshi/yomon» rangiga boʻyalmaydi; sparkline aria-hidden, raqam oʻqiladi
  used on   S03, S13, S16
```

```
Destination picker                                          web/src/pbx/DestinationPicker.tsx, domain/destination.ts
  variants  9 tur: extension, ringgroup, queue, ivr, timecondition, announcement, voicemail, external, hangup;
            kinds prop bilan cheklash mumkin
  states    empty, empty+required (xato), ok (tur belgisi + nom + raqam), broken (obyekt oʻchirilgan:
            Link2Off + «Oʻchirilgan: …» + #id, saqlashga yoʻl qoʻymaydi), invalid (tashqi raqam yaroqsiz),
            open (popover), disabled; popover ichida: qidiruv natijasi yoʻq, tur boʻsh
  tokens    trigger — controlBase (surface, border-input); popover raised + shadow-pop + radius lg, 560px;
            chap tur paneli w-44 surface-2/60; faol tur — brand ikon
  a11y      trigger <button> aria-haspopup=dialog, aria-invalid, aria-labelledby (yorliq + qiymat matni),
            aria-describedby (sabab/izoh); tur paneli role=radiogroup (strelkalar); qidiruv role=combobox +
            listbox + aria-activedescendant, ↑↓ Enter Esc; tashqi raqam — alohida input, Enter tasdiqlaydi
            (testlangan: DestinationPicker.test.tsx — broken, required, sichqoncha, klaviatura)
  used on   S07, S08, S09, S10, S21, S28
```

```
Call-flow graph (faqat koʻrish)                             web/src/pbx/CallFlow.tsx, domain/flow.ts
  variants  DID dan boshlanadigan vertikal daraxt + oʻngda «Tekshiruv» paneli
  states    toza (CircleCheck «Yoʻl toza»), loop (uzuq warning chegara, Repeat2), broken (danger-soft, Link2Off),
            end (hangup — surface-2), tanlanmagan; chuqurlik limiti 12
  tokens    tugun 44px, min 200 / max 320px, radius md; ulagich 1px border-strong; fon hairline-grid;
            tarmoq yorligʻi xs (raqam boʻlsa mono)
  a11y      <figure> + ichma-ich <ul> (screen reader daraxtni roʻyxat sifatida oʻqiydi); muammolar soni role=status;
            muammo yoʻli matn bilan («+998 71 200 00 00 → ochiq → 2 → agent yoʻq»)
  used on   S07, S09
```

```
Week grid (ish vaqti)                                       web/src/pbx/WeekGrid.tsx, domain/week.ts
  variants  7 kun × 24 soat; pastda soʻz bilan xulosa (summarizeWeek); bayramlar — alohida Badge roʻyxati
  states    ochiq (brand), yopiq (surface-2), hover, fokus katak (ring), boʻyash jarayoni (pointer drag)
  tokens    katak 26px, gap 2px, radius xs; soat yorligʻi 2xs mono
  a11y      role=grid, roving tabindex, strelkalar, Space almashtiradi, Shift+strelka boʻyab yuradi;
            har katak aria-label «Dushanba 09:00, ochiq»; xulosa aria-describedby
  used on   S08
```

```
Audio player                                                web/src/pbx/AudioPlayer.tsx
  variants  full (kutubxona, ovozli pochta), inline (qoʻngʻiroqlar tarixi qatori)
  states    idle, loading, playing, paused, error (fayl yoʻq / format — sabab matni), tezlik 1×/1.5×/2×
  tokens    play — accent kvadrat 40/28; toʻlqin 2px ustunlar line-strong → brand (oʻtgan qism); vaqt mono xs
  a11y      play — aria-label «Ijro etish/Pauza»; toʻlqin role=slider (aria-valuenow/valuetext «0:04 / 0:09»),
            ← → 5 s, Shift 15 s, Home/End; yuklab olish — <a download> aria-label
  used on   S11, S12, S23
```

```
Dial-pattern editor                                         web/src/pbx/PatternEditor.tsx, domain/pattern.ts
  variants  qoida qatori: oldiga qoʻsh, prefiks (kesiladi), naqsh, CallerID; qator qoʻshish/oʻchirish; sinov raqami
  states    toʻgʻri (pastda soʻz bilan tavsif: «12 xonali raqam, «998» bilan boshlanadi»), xato (xato belgi tagida
            toʻlqinli chiziq + matn: ochilmagan [, boʻsh sinf, notoʻgʻri oraliq, «.» oxirda emas, ruxsatsiz belgi),
            sinovga mos qator (accent-soft fon + chap brand chiziq), mos qoida yoʻq
  tokens    input mono; xato danger; mos qator accent-soft
  a11y      har input aria-invalid + aria-describedby (xato/tavsif); sinov natijasi aria-live polite
  used on   S22 (chiquvchi marshrut), S10 (trunk dial rules)
```

```
Drag-drop order list                                        web/src/pbx/SortableList.tsx, domain/reorder.ts
  variants  trunk ketma-ketligi, navbat agentlari, IVR variantlari
  states    default, hover (tutqich fg), sudralmoqda (raised + shadow-pop), tushish joyi (2px brand chiziq),
            klaviatura bilan koʻtarilgan (ring + «koʻtarilgan»)
  tokens    qator 48px, chiziq line, tartib raqami mono muted
  a11y      tutqich <button> aria-label «Uztelecom ni koʻchirish»; Space — koʻtarish, ↑↓ — koʻchirish,
            Space — qoʻyish, Esc — bekor; har qadam aria-live eʼlon qiladi («Uztelecom: 2-oʻrin, 3 tadan»)
  used on   S10, S21, S22
```

```
Softphone                                                   web/src/pbx/Softphone.tsx
  variants  SoftphoneChip (headerda), SoftphonePanel (popover): dialpad, kiruvchi, gaplashmoqda, ushlab turish
  states    idle (Tayyor), incoming (pulsatsiya, Rad etish / Javob berish), connecting, talking (taymer, oltin live),
            hold (warning-soft matn bilan), boʻsh raqam — Qoʻngʻiroq disabled
  tokens    panel 300px raised + shadow-pop; dialpad tugma 48px; javob — accent, rad/yakun — danger
  a11y      dialpad tugmalari <button> (raqam + harflar); klaviaturadan raqam yozish; holat — sarlavhada matn
            bilan (rang emas); taymer role=timer, aria-live=off (har soniya eʼlon qilinmaydi); mute/hold — aria-pressed
  used on   S16, S30
```

```
Log viewer                                                  web/src/pbx/LogViewer.tsx
  variants  Asterisk CLI oqimi (faqat oʻqish)
  states    jonli kuzatish (Kuzatish tugmasi, aria-pressed), pauza (yuqoriga aylantirilganda oʻzi toʻxtaydi +
            «Oxiriga oʻtish»), daraja filtri (chip, aria-pressed), qidiruv mosligi (live/oltin fon), boʻsh natija
  tokens    mono sm, qator 20px; ERROR — danger + danger-soft/40 qator; WARNING — warning; vaqt muted
  a11y      role=log + aria-live polite (faqat kuzatish yoqilganda); filtr chiplari <button aria-pressed>
  used on   S36
```

```
App shell                                                   web/src/shell/AppShell.tsx
  variants  desktop (sidebar 248 + header 52), mobil (sidebar Drawer, burger); embedded (dizayn sahifasi uchun)
  sidebar   ikkala rejimda koʻmir (sidebar-bg); guruhlar: Umumiy, Foydalanuvchilar, Ulanish, Marshrut, Ilovalar,
            Hisobotlar, Tizim; faol element — sidebar-active (qahva) + chap 2px brand chiziq; hisoblagich mono;
            pastda server nomi + HealthStrip
  header    qidiruv (Ctrl K), Dialplan reviziyasi nishoni, til UZ/RU/EN (Segmented), mavzu toggle, SoftphoneChip, avatar
  revision  «Apply Config» banneri YOʻQ — har saqlash darhol compile → reload. Nishon holatlari:
            applied (CircleCheck, «r143 qoʻllandi 12:04»), applying (LoaderCircle, aria-busy),
            rolled_back (RotateCcw, danger-soft, «r142 ga qaytarildi» — not-applied toast bilan birga)
  tokens    sidebar-*, header bg surface/85 + backdrop-blur, z sidebar 20 / header 30
  a11y      «Kontentga oʻtish» havolasi; <nav aria-label>, faol sahifa aria-current=page; til va mavzu —
            haqiqiy radiogroup/button; reviziya nishoni role=status (oʻzgarsa eʼlon qilinadi)
  used on   hammasi
```

---

Ochiq masalalar:
- IBM Plex Sans Condensed'da kirill yoʻq — ruscha sarlavhalar Plex Sans'ga tushadi (kengroq). Yechim: RU uchun `--font-display` ni Plex Sans 600 ga almashtirish (`:lang(ru)`).
- Plex'da ʻ/ʼ 600 birlik enli — `scripts/build-apostrof.py` Plex'ning tirnoq glifidan «Innova Apostrof» mini-shriftini yasaydi (unicode-range U+02BB-02BC). Mono'da almashtirilmadi (monospace ataylab).
- Kalendar (bayramlar) hozircha Badge roʻyxati — toʻliq oylik kalendar S08 build bosqichida.
