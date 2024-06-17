import pytest

import colrev.exceptions as colrev_exceptions
import colrev.process.operation
from colrev.constants import OperationsType


def test_check_precondition_load(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:

    load_operation = colrev.process.operation.Operation(
        review_manager=base_repo_review_manager, operations_type=OperationsType.load
    )

    base_repo_review_manager.settings.project.title = "test modification"
    base_repo_review_manager.save_settings()

    base_repo_review_manager.paths.readme.write_text("test modification")
    with pytest.raises(colrev_exceptions.UnstagedGitChangesError):
        load_operation.check_precondition()

    base_repo_review_manager.dataset.add_changes(base_repo_review_manager.paths.readme)
    with pytest.raises(colrev_exceptions.CleanRepoRequiredError):
        load_operation.check_precondition()

    helpers.reset_commit(base_repo_review_manager, commit="prep_commit")
    dedupe_operation = colrev.process.operation.Operation(
        review_manager=base_repo_review_manager, operations_type=OperationsType.dedupe
    )
    dedupe_operation.check_precondition()

    base_repo_review_manager.paths.readme.write_text("test modification")
    with pytest.raises(colrev_exceptions.UnstagedGitChangesError):
        load_operation.check_precondition()

    # passes with force mode
    base_repo_review_manager.force_mode = True
    load_operation.check_precondition()


# def test_conclude(self):
#     docker_mock = MagicMock()
#     container_mock = MagicMock()
#     container_mock.image.tags = ['image1', 'image2']
#     docker_mock.from_env.return_value.containers.list.return_value = [container_mock]
#     self.operation.docker_images_to_stop = ['image1']

#     with patch('colrev.process.operation.docker', docker_mock):
#         self.operation.conclude()

#     docker_mock.from_env.assert_called_once()
#     docker_mock.from_env.return_value.containers.list.assert_called_once()
#     container_mock.stop.assert_called_once()
