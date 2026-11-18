"""Runs the safety-net jobs on a schedule inside one small container (no host cron needed)."""
import logging
import time
from datetime import datetime, time as clock, timezone

from billing import jobs

logger = logging.getLogger('billing.scheduler')
INTERVALS = {'sweep': 300, 'expire': 3600}                      # seconds
DAILY_UTC = {'reconcile': clock(2, 0), 'check-prices': clock(2, 10)}
TICK = 30


def due(now: datetime, last_run: dict[str, datetime]) -> list[str]:
    ready = [name for name, every in INTERVALS.items()
             if name not in last_run or (now - last_run[name]).total_seconds() >= every]
    for name, at in DAILY_UTC.items():
        today_at = datetime.combine(now.date(), at, tzinfo=timezone.utc)
        if now >= today_at and (name not in last_run or last_run[name] < today_at):
            ready.append(name)
    return ready


def run_forever() -> None:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    last_run: dict[str, datetime] = {}
    while True:
        now = datetime.now(timezone.utc)
        for name in due(now, last_run):
            last_run[name] = now
            try:
                code = jobs.main([name])
                (logger.warning if code else logger.info)('job %s finished with code %s', name, code)
            except SystemExit as exc:
                logger.error('job %s could not start: %s', name, exc)
            except Exception:  # noqa: BLE001 - one failing job must not stop the others
                logger.exception('job %s crashed', name)
        time.sleep(TICK)


if __name__ == '__main__':
    run_forever()
