-- M5a SSH: `migration_jobs.status` ga `fetching` qo'shiladi (replica/m5a-contract.md §3
-- `/ssh/fetch` — 202 qaytargandan tugaguncha job "step=ssh_fetch" bilan, lekin status
-- ham "uploaded"dan FARQLI bo'lishi kerak, chunki to'plam hali tasdiqlanmagan/tortilmagan).

alter table migration_jobs drop constraint if exists migration_jobs_status_check;
alter table migration_jobs add constraint migration_jobs_status_check
  check (status in ('uploaded', 'fetching', 'analyzing', 'analyzed', 'applying', 'ok', 'failed'));
