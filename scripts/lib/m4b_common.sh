# shellcheck shell=bash
# M4b (zaxira/tiklash) isbot yordamchilari — m2a_common.sh/m3b_common.sh ustiga
# (PASS/FAIL, api/jget/jcode/sql/wait_until shu yerda allaqachon bor, qayta yozilmaydi).
# Talab qilinadi: API_BASE, PG, APICONT, NET o'zgaruvchilari.

# ------------------------------------------------------------------ zaxira ish/holat
job_wait() { # job_id [max_s] -> stdout: oxirgi status (running/ok/partial/failed/not_found)
  local id="$1" max="${2:-180}" i=0 st=""
  while (( i < max * 2 )); do
    st=$(jget "$(jbody "$(api GET "/backups/jobs/$id")")" status)
    [[ -n "$st" && "$st" != "running" ]] && { echo "$st"; return 0; }
    sleep 0.5; i=$((i + 1))
  done
  echo "${st:-timeout}"
}

# ------------------------------------------------------------------ zaxira maydonlari (job_wait'dan KEYIN —
# BackupJobState.status "partial"ni "ok"ga tenglashtiradi, haqiqiy holat uchun GET /backups/{id} kerak)
backup_status() { jget "$(jbody "$(api GET "/backups/$1")")" item status; }
backup_file_name() { jget "$(jbody "$(api GET "/backups/$1")")" item file_name; }
backup_final_status() { # backup_id [max_s] -> ish tugagach HAQIQIY holat (ok/partial/failed/timeout)
  local id="$1" max="${2:-180}" js
  js=$(job_wait "$id" "$max")
  [[ "$js" == "timeout" ]] && { echo timeout; return; }
  backup_status "$id"
}
copy_status() { # backup_id target -> shu nishon nusxasi holati (pending/ok/failed/deleted/bo'sh)
  jbody "$(api GET "/backups/$1")" | python3 -c "
import json, sys
c = next((c for c in json.load(sys.stdin)['item']['copies'] if c['target'] == sys.argv[1]), None)
print((c or {}).get('status') or '')" "$2"
}
copy_error() { # backup_id target -> shu nishon nusxasi xato matni (yoki bo'sh)
  jbody "$(api GET "/backups/$1")" | python3 -c "
import json, sys
c = next((c for c in json.load(sys.stdin)['item']['copies'] if c['target'] == sys.argv[1]), None)
print((c or {}).get('error') or '')" "$2"
}

# ------------------------------------------------------------------ multipart yuklash/yuklab olish
api_upload() { # path file -> body + "\n" + http_code
  curl -s -w '\n%{http_code}' -X POST "$API_BASE$1" "${AUTH[@]}" -F "file=@$2"
}
api_download() { # path outfile -> stdout: http_code (tanani outfile'ga yozadi)
  curl -s -o "$2" -w '%{http_code}' "$API_BASE$1" "${AUTH[@]}"
}
upload_audio_file() { # name wavfile -> body + "\n" + http_code
  curl -s -w '\n%{http_code}' -X POST "$API_BASE/audio" "${AUTH[@]}" -F "name=$1" -F "file=@$2"
}

# ------------------------------------------------------------------ .ibk buzish (§4.2)
corrupt_flip_byte() { # in out -> o'rtadagi bitta baytni (sarlavhadan keyin, GCM teg ichida) teskari
  python3 -c "
import sys
data = bytearray(open(sys.argv[1], 'rb').read())
mid = len(data) // 2
data[mid] ^= 0xFF
open(sys.argv[2], 'wb').write(data)" "$1" "$2"
}
corrupt_truncate() { # in out -> oxiridan 1 KiB kesilgan (oxirgi bo'lak tugallanmagan)
  local size
  size=$(stat -c%s "$1")
  head -c $(( size - 1024 )) "$1" > "$2"
}

# ------------------------------------------------------------------ S3 (zenko/cloudserver, MinIO o'rnida —
# minio/minio Docker Hub'dan o'chirilgan, quay.io/minio/minio 401 beradi, 2026-10-29 tekshirilgan)
S3_HOST="m4b-proof-s3"
S3_ACCESS="m4bAccessKey1"
S3_SECRET="m4bSecretKey12345678"
S3_WRONG_SECRET="WrongSecretKeyXXXXX"
S3_BUCKET="m4b-backups"
# shellcheck disable=SC2016 — ichidagi $-lar Python kodi, bash kengaytirilmasin
S3_PY='
import sys, boto3
from botocore.config import Config
cmd, endpoint, access, secret, bucket = sys.argv[1:6]
c = boto3.client("s3", endpoint_url=endpoint, aws_access_key_id=access, aws_secret_access_key=secret,
                 config=Config(s3={"addressing_style": "path"}))
if cmd == "ready":
    c.list_buckets()
elif cmd == "mkbucket":
    try:
        c.create_bucket(Bucket=bucket)
    except Exception as exc:
        if "BucketAlready" not in str(exc):
            raise
elif cmd == "count":
    names = [o["Key"].rsplit("/", 1)[-1] for o in c.list_objects_v2(Bucket=bucket).get("Contents", [])]
    print(sum(1 for n in names if n.startswith("innova-") and n.endswith(".ibk")))
elif cmd == "has":
    names = [o["Key"].rsplit("/", 1)[-1] for o in c.list_objects_v2(Bucket=bucket).get("Contents", [])]
    print("yes" if sys.argv[6] in names else "no")
elif cmd == "put_foreign":
    c.put_object(Bucket=bucket, Key=sys.argv[6], Body=b"begona-fayl-tegilmasin")
'
s3_py() { # cmd [extra] -> stdout
  local cmd="$1"; shift
  docker exec "$APICONT" python3 -c "$S3_PY" "$cmd" "http://$S3_HOST:8000" "$S3_ACCESS" "$S3_SECRET" "$S3_BUCKET" "$@"
}
s3_ready() { s3_py ready >/dev/null 2>&1; }
s3_up() {
  # ENDPOINT=$S3_HOST -> cloudserver o'z restEndpoints.json'iga shu xost nomini
  # qo'shadi (aks holda konteyner nomi bilan so'rov "InvalidURI" bilan rad etiladi —
  # standart config faqat localhost/127.0.0.1/cloudserver-front/s3.docker.test'ni biladi).
  docker run -d --name "$S3_HOST" --network "$NET" \
    -e SCALITY_ACCESS_KEY_ID="$S3_ACCESS" -e SCALITY_SECRET_ACCESS_KEY="$S3_SECRET" \
    -e ENDPOINT="$S3_HOST" \
    zenko/cloudserver:latest >/dev/null
  wait_until 40 s3_ready || return 1
  s3_py mkbucket >/dev/null
}
s3_down() { docker rm -f "$S3_HOST" >/dev/null 2>&1 || true; }
s3_count() { s3_py count; }
s3_has() { [[ "$(s3_py has "$1")" == "yes" ]]; }
s3_put_foreign() { s3_py put_foreign "$1" >/dev/null; }

# ------------------------------------------------------------------ SFTP (atmoz/sftp)
SFTP_HOST="m4b-proof-sftp"
SFTP_USER="m4buser"
SFTP_PASS="M4bSftpPass123"
SFTP_DIR="upload"           # SftpTarget.folder = "/upload" (chroot ichida)
SFTP_HOME="/home/$SFTP_USER/$SFTP_DIR"
sftp_ready() { # papka TAYYOR bo'lishi YETARLI EMAS -- sshd ALI tinglashni boshlamagan bo'lishi
  # mumkin (/entrypoint papkani sshd'dan OLDIN yaratadi) -> qisqa "Connection refused" oynasi.
  # :0016 = port 22 (hex) /proc/net/tcp'da -- sshd haqiqatan tinglayotganini isbotlaydi.
  docker exec "$SFTP_HOST" sh -c "test -d '$SFTP_HOME' && grep -q ':0016 ' /proc/net/tcp" >/dev/null 2>&1
}
sftp_up() { # HAR CHAQIRILGANDA konteyner qayta yaratiladi -> YANGI host kaliti
  # ("kalit almashsa host_key_mismatch" ssenariysi uchun shart — doim shu funksiya).
  docker rm -f "$SFTP_HOST" >/dev/null 2>&1 || true
  docker run -d --name "$SFTP_HOST" --network "$NET" \
    atmoz/sftp "$SFTP_USER:$SFTP_PASS:1001:100:$SFTP_DIR" >/dev/null
  wait_until 30 sftp_ready
}
sftp_down() { docker rm -f "$SFTP_HOST" >/dev/null 2>&1 || true; }
sftp_stop() { docker stop "$SFTP_HOST" >/dev/null 2>&1 || true; }     # "SFTP o'chirilgan" (server ishdan chiqdi)
sftp_start() { docker start "$SFTP_HOST" >/dev/null 2>&1 || true; wait_until 30 sftp_ready; }
sftp_count() { docker exec "$SFTP_HOST" sh -c "find '$SFTP_HOME' -maxdepth 1 -name 'innova-*.ibk' 2>/dev/null | wc -l" | tr -d ' \t\n'; }
sftp_has() { docker exec "$SFTP_HOST" test -f "$SFTP_HOME/$1" >/dev/null 2>&1; }
sftp_put_foreign() { docker exec "$SFTP_HOST" sh -c "echo begona > '$SFTP_HOME/$1'"; }

# ------------------------------------------------------------------ trunk siri (realtime view, re-key isboti)
trunk_secret_via_ps_auths() { docker exec "$PG" psql -U innova -d innova -tAc \
  "select password from ps_auths where id like '%-trunk-$1'" 2>/dev/null; }
