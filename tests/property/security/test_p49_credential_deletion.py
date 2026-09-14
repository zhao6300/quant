from hypothesis import given, settings
from hypothesis import strategies as st

from mmqp.application.security import CredentialManager
from mmqp.domain.security import (
    CredentialDeletionChoiceV1,
)
from tests.unit.security.test_credentials import MemoryKeychain, credential


@given(
    repository_id=st.sampled_from(("folder-empty", "folder-selected")),
    remaining_ids=st.sets(
        st.sampled_from(("first", "second", "third", "fourth", "fifth")),
        min_size=0,
        max_size=5,
    ),
)
@settings(max_examples=32, deadline=None)
def test_folder_empty_and_backend_shows_unchanged(repository_id: str, remaining_ids: set[str]) -> None:
    ordered_ids = tuple(sorted(remaining_ids))
    snapshot_keychain = MemoryKeychain()
    snapshot_manager = CredentialManager(snapshot_keychain)
    for item_id in ordered_ids:
        snapshot_manager.set(credential(repository_id, item_id, "secret"), 0)

    selected_subset: set[str] = {item_id for item_id in ordered_ids if item_id.startswith("first")}
    choices = tuple(
        CredentialDeletionChoiceV1(credential_id=item_id, delete=item_id in selected_subset)
        for item_id in ordered_ids
    )
    result = snapshot_manager.delete_selected(choices)

    preserved_backend = tuple(item_id for item_id in ordered_ids if item_id not in selected_subset)
    assert result.deleted == tuple(sorted(selected_subset))
    assert result.preserved == preserved_backend
    assert result.failures == ()
    assert snapshot_keychain.items.keys() == set(preserved_backend)
    assert all(item.value == "secret" for item in snapshot_keychain.items.values())
