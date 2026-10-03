import queue

from samsung_local.capabilities import batch_resources
from samsung_local.worker import DeviceWorker
from test_discovery_worker import DI, FakeSession, sample


# Representative shape from LocalThings dryer_dv6800n_device.json (MIT).
BATCH = [
    {"rt": ["x.com.samsung.devcol", "oic.wk.col"]},
    {"href": "/information/vs/0", "rep": {"x.com.samsung.da.description": "COMMON_DV6800N/board"}},
    {"href": "/power/vs/0", "rep": {"x.com.samsung.da.power": "On"}},
    {"href": "/operational/state/vs/0", "rep": {"x.com.samsung.da.state": "Run",
                                               "x.com.samsung.da.remainingTime": "00:32:00"}},
    {"href": "/oic/sec/cred", "rep": {"secret": "never-retain"}},
    {"href": "/mode/vs/0", "rep": {"href": "/mode/vs/0"}},
    {"href": "/humidity/0", "rep": {}},
]


def test_batch_parser_excludes_security_stubs_and_empty_representations():
    parsed = batch_resources(BATCH)
    assert set(parsed) == {"/information/vs/0", "/power/vs/0", "/operational/state/vs/0"}
    assert batch_resources(None) == {}


def test_unadvertised_collection_populates_dryer_readings(paths):
    events = queue.Queue()
    obj = DeviceWorker(sample(), {"_compatibility_probe": True}, 30, paths, events, ("192.0.2.10", 49161))
    obj.session = FakeSession({"/oic/d": {"di": DI, "rt": ["oic.d.dryer"]},
                               "/oic/res": {"links": [{"href": "/oic/d"}]}, "/device/0": BATCH})
    obj.monitor()
    messages = [events.get_nowait()[2] for _ in range(events.qsize())]
    assert messages[-1]["state"]["power"] == 1
    assert messages[-1]["state"]["operational_state_vs_0_remainingTime"] == "00:32:00"
    assert messages[-1]["legacy_verified"]
    assert "/oic/sec/cred" not in obj.session.reads
    assert "/power/vs/0" not in obj.session.reads  # The batch is the data source.
    assert "never-retain" not in str(messages)


def test_batch_is_refreshed_on_subsequent_polls(paths):
    events = queue.Queue()
    obj = DeviceWorker(sample(), {}, 0, paths, events, ("192.0.2.10", 49161))
    obj.session = FakeSession({"/oic/d": {"di": DI, "rt": ["oic.d.dryer"]},
                               "/oic/res": [], "/device/0": BATCH})
    readings = []
    def emit(**values):
        if values.get("status") == "online":
            readings.append(values["state"]["power"])
            obj.session.resources["/device/0"] = [{"href": "/power/vs/0", "rep": {"x.com.samsung.da.power": "Off"}}]
            if len(readings) == 2:
                obj.stop_event.set()
    obj.emit = emit
    obj.monitor()
    assert readings == [1, 0]
    assert obj.session.reads.count("/device/0") == 2


def test_empty_resources_are_not_reported_online(paths):
    events = queue.Queue()
    obj = DeviceWorker(sample(), {"_compatibility_probe": True}, 30, paths, events, ("192.0.2.10", 49161))
    obj.session = FakeSession({"/oic/d": {"di": DI}, "/oic/res": [], "/device/0": []})
    obj.monitor()
    messages = [events.get_nowait()[2] for _ in range(events.qsize())]
    assert messages[-1]["status"] == "unsupported"
    assert not any(m.get("legacy_verified") for m in messages)
