from prometheus_client import Counter, Gauge

CHARGED = Counter('billing_charged_micros', 'Micro-dollars charged to learners', ['alias', 'action'])
MARGIN = Counter('billing_margin_micros', 'Charged minus provider cost, micro-dollars', ['alias'])
WRITTEN_OFF = Counter('billing_written_off_micros', 'Usage the balance could not cover')
INSUFFICIENT = Counter('billing_insufficient', 'Reservations refused for lack of credits', ['reason'])
STARTER_GRANTS = Counter('billing_starter_grants', 'Starter grant attempts', ['result'])
UNKNOWN_ALIAS = Counter('billing_unknown_alias', 'Settles or reservations naming an unpriced alias')
OPEN_RESERVATIONS = Gauge('billing_reservations_open', 'Reservations currently holding funds')
JOB_LAST_RUN = Gauge('billing_job_last_run_timestamp', 'Unix time the job last finished', ['job'])
JOB_PROBLEM = Gauge('billing_job_problem', '1 when the latest run of the job found a problem', ['job'])
RECONCILE_DRIFT = Gauge('billing_reconcile_drift_micros', 'Usage the ledger had missed at the last reconcile')
PRICE_DRIFT = Gauge('billing_price_drift', 'Aliases whose gateway price differs from ours at the last check')
