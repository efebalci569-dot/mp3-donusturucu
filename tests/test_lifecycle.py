from lifecycle import Lifecycle


def test_no_exit_during_grace():
    t = [0.0]
    lc = Lifecycle(clock=lambda: t[0])
    t[0] = 119
    assert not lc.should_exit(0)
    t[0] = 121
    assert lc.should_exit(0)


def test_background_tab_throttling_does_not_exit():
    t = [0.0]
    lc = Lifecycle(clock=lambda: t[0])
    for beat in (0, 70, 140, 210):
        t[0] = beat
        lc.heartbeat()
        t[0] = beat + 69
        assert not lc.should_exit(0)


def test_exit_after_idle_timeout():
    t = [10.0]
    lc = Lifecycle(clock=lambda: t[0])
    lc.heartbeat()
    t[0] = 189
    assert not lc.should_exit(0)
    t[0] = 191
    assert lc.should_exit(0)


def test_running_job_blocks_exit():
    t = [0.0]
    lc = Lifecycle(clock=lambda: t[0])
    t[0] = 1000
    assert not lc.should_exit(1)
