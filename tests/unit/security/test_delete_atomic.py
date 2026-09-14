import pytest

from mmqp.application.security import CredentialManager
from mmqp.domain.security import CredentialDeletionChoiceV1
from tests.unit.security.test_credentials import MemoryKeychain, credential


class TestCredentialDeletion:
    @pytest.mark.parametrize("delete_first,delete_second", [(True, False), (False, True)])
    def test_deletion_preserves_complement_and_reports_failure_without_content(
        self,
        delete_first: bool,
        delete_second: bool,
    ) -> None:
        keychain = MemoryKeychain()
        manager = CredentialManager(keychain)
        manager.set(credential("provider", "first"), 0)
        manager.set(credential("provider", "second"), 0)
        failure_target = "first" if delete_first else "second"
        keychain.failing_on_delete = failure_target
        choices = (
            CredentialDeletionChoiceV1(credential_id="first", delete=delete_first),
            CredentialDeletionChoiceV1(credential_id="second", delete=delete_second),
        )

        result = manager.delete_selected(choices)

        assert result.deleted == ()
        assert set(result.preserved) == {"first", "second"}
        assert result.failures
        assert result.failures[0].credential_id == failure_target

    def test_deletion_preserves_complement_when_subset_failure_rolls_back(self) -> None:
        keychain = MemoryKeychain()
        manager = CredentialManager(keychain)
        manager.set(credential("provider-a", "first"), 0)
        manager.set(credential("provider-b", "second"), 0)
        keychain.failing_on_delete = "first"

        result = manager.delete_selected(
            (
                CredentialDeletionChoiceV1(credential_id="first", delete=True),
                CredentialDeletionChoiceV1(credential_id="second", delete=True),
            ),
        )

        assert result.deleted == ()
        assert set(result.preserved) == {"first", "second"}
        assert result.failures[0].credential_id == "first"
