import anyio
import pytest

from app.metering import UsageRecord, current_action, current_meter, metering_scope, record


def rec(alias='open-default', purpose='main', i=10, o=5, estimated=False):
    return UsageRecord(alias=alias, purpose=purpose, input_tokens=i, output_tokens=o, estimated=estimated)


def test_record_outside_scope_is_noop():
    record(rec())
    assert current_meter() is None and current_action() is None


def test_scope_collects_records_in_order():
    with metering_scope('chat', 'req-1') as meter:
        record(rec(purpose='guard'))
        record(rec(purpose='main'))
        assert current_action() == ('chat', 'req-1')
    assert [r.purpose for r in meter.records] == ['guard', 'main']
    assert current_meter() is None


def test_scope_survives_threadpool():
    async def run():
        with metering_scope('chat', 'req-2') as meter:
            await anyio.to_thread.run_sync(record, rec())
        return meter

    meter = anyio.run(run)
    assert len(meter.records) == 1


def test_nested_scope_rejected():
    with metering_scope('chat', 'a'):
        with pytest.raises(RuntimeError):
            with metering_scope('chat', 'b'):
                pass


def test_on_add_hook_can_abort():
    class Stop(Exception):
        pass

    def hook(r):
        raise Stop

    with metering_scope('agent', 'req-3', on_add=hook) as meter:
        with pytest.raises(Stop):
            record(rec())
    assert len(meter.records) == 1  # the record that crossed the line is kept so it is still charged


def test_scope_resets_after_exception():
    with pytest.raises(ValueError):
        with metering_scope('chat', 'req-4'):
            raise ValueError
    assert current_meter() is None
