# Innova PBX — veb konteyner (m3a-contract.md §3): SPA + yagona kelib chiqish (origin).
# nginx: `/` SPA, `/api/` -> api:8000, `/sip-ws` -> (ticket darvozasi) -> asterisk:8088/ws.
#
# Build konteksti — LOYIHA ILDIZI (compose: `context: ..`, `dockerfile: web/Dockerfile`):
# `web/` dizayn tokenlarini `../replica/design`dan oladi (scripts/gen-tokens.mjs, tsconfig/vite
# `@design` taxallusi) — shu sabab ikkala katalog ham bir xil nisbiy joylashuvda ko'chiriladi.
# Nima ko'chirilishi ildizdagi `.dockerignore`da (faqat shu build ildiz kontekstidan foydalanadi).

FROM node:20-slim AS build
WORKDIR /src/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY replica/design /src/replica/design
# Qo'llanma (yon menyudagi «Qo'llanma» — `@docs` taxallusi, `src/docs/content.ts`).
COPY docs/qollanma /src/docs/qollanma
COPY web/ ./
# Haqiqiy backend (`src/api/index.ts`: VITE_API=real bo'lmasa — soxta API).
ENV VITE_API=real
RUN npm run build

FROM nginx:1.27-alpine
# 1.0.4: `openssl` — zaxira TLS sertifikati uchun (`web-tls-wait.sh`, faqat `api`
# ulgurmagan noodatiy holatda; odatiy holatda `api` certs hajmiga allaqachon yozgan bo'ladi).
RUN apk add --no-cache openssl
# Shablon: ishga tushishda faqat `INNOVA_*` o'zgaruvchilari almashtiriladi (nginx `$var`lar tegilmaydi).
ENV NGINX_ENVSUBST_FILTER=^INNOVA_ \
    INNOVA_ASTERISK_WS=http://asterisk:8088/ws
COPY deploy/web-nginx.conf /etc/nginx/templates/default.conf.template
COPY deploy/web-tls-wait.sh /docker-entrypoint.d/10-innova-tls.sh
RUN chmod +x /docker-entrypoint.d/10-innova-tls.sh
COPY --from=build /src/web/dist /usr/share/nginx/html
EXPOSE 80 443
