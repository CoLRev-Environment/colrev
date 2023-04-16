"""Test the custom CoLRev linter"""
import astroid
import pylint.testutils

import colrev.linter.colrev_lint


class TestDirectStatusAssignmentChecker(pylint.testutils.CheckerTestCase):
    """TestDirectStatusAssignmentChecker class"""

    CHECKER_CLASS = colrev.linter.colrev_lint.DirectStatusAssignmentChecker

    def test_finds_direct_status_assignment(self) -> None:
        """Test whether the pylint checker finds direct colrev_status assignments"""

        assignment_node = astroid.extract_node(
            """
        def test(record_dict):
            record_dict["colrev_status"] = colrev.record.RecordState.md_imported #@

        """
        )

        with self.assertAddsMessages(
            pylint.testutils.MessageTest(
                msg_id="direct-status-assign",
                node=assignment_node,
                line=3,
                col_offset=4,
                end_line=3,
                end_col_offset=72,
            ),
        ):
            self.checker.visit_assign(assignment_node)
