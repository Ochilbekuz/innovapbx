"""Umumiy (`dialplan`/`certs`) docker hajmiga atomik yozish — `.tmp` + `rename`
(architecture.md qadam 4). `apply.py` (dialplan), `moh.py` (musiconhold) VA
`tls_cert.py` (sertifikat/kalit) BIR XIL qolipni ishlatadi (dryer: nusxalanish
shu yerga chiqarildi, bir-biridan import qilmasin deb mustaqil kichik modulga).

Standart `mode=0o644` — dunyoga ochiq (sirlar bu faylda yo'q, Asterisk har
qanday UID bilan o'qiy olishi SHART). TLS kaliti kabi sir fayllar uchun
`mode=0o640` + `chown_gid` beriladi (egasi o'zgarmaydi — faqat guruh)."""
from __future__ import annotations

import os
import tempfile


def atomic_write(directory: str, filename: str, text_content: str, *, tmp_prefix: str,
                 mode: int = 0o644, chown_gid: int | None = None) -> None:
    os.makedirs(directory, exist_ok=True)
    target = os.path.join(directory, filename)
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=tmp_prefix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text_content)
        # `mkstemp` fayllarni 0600 (faqat egasi) bilan yaratadi. API konteyneri
        # root sifatida ishlaydi, Asterisk esa `asterisk` (uid 1000) sifatida —
        # ikkisi umumiy hajmni ulashadi, lekin egasi/UID bo'yicha mos kelmaydi.
        # Shu sabab Asterisk `#include`ni jim o'tkazib yuborgan (kontekst
        # umuman yuklanmagan) — sinovda topilgan (apply.py). Oddiy fayl har
        # doim dunyoga o'qish uchun ochiq (sirlar bu faylda yo'q); sir fayl
        # bo'lsa chaqiruvchi `mode`/`chown_gid` bilan toraytiradi.
        os.chmod(tmp_path, mode)
        if chown_gid is not None:
            os.chown(tmp_path, -1, chown_gid)
        os.replace(tmp_path, target)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
