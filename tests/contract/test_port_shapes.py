from mmqp.ports.stable import (
    BackupPort,
    ClockPort,
    ContentStorePort,
    DataSnapshotV1,
    ExperimentPort,
    SnapshotPort,
    WorkspacePort,
)


def test_stable_ports_and_artifact_ref_contract() -> None:
    snapshot = DataSnapshotV1(
        snapshot_id="snapshot-1",
        artifacts=(),
    )
    for port_type in (
        BackupPort,
        ClockPort,
        ContentStorePort,
        ExperimentPort,
        SnapshotPort,
        WorkspacePort,
    ):
        assert port_type is not None
    assert snapshot.snapshot_id == "snapshot-1"
