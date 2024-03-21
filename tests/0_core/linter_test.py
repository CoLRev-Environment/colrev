#!/usr/bin/env python
"""Test the custom CoLRev linter"""
import astroid
import pylint.testutils

import colrev.linter.colrev_direct_status_assign
import colrev.linter.colrev_records_variable_naming_convention


class TestDirectStatusAssignmentChecker(pylint.testutils.CheckerTestCase):
    """TestDirectStatusAssignmentChecker class"""

    CHECKER_CLASS = (
        colrev.linter.colrev_direct_status_assign.DirectStatusAssignmentChecker
    )

    def test_finds_direct_status_assignment(self) -> None:
        """Test whether the pylint checker finds direct colrev_status assignments"""

        assignment_node = astroid.extract_node(
            """
        record_dict["colrev_status"] = RecordState.md_imported

        """
        )

        with self.assertAddsMessages(
            pylint.testutils.MessageTest(
                msg_id="colrev-direct-status-assign",
                node=assignment_node,
                line=2,
                col_offset=0,
                end_line=2,
                end_col_offset=54,
            ),
        ):
            self.checker.visit_assign(assignment_node)

        call_node = astroid.extract_node(
            """
        record_dict.update(colrev_status= RecordState.md_imported)
        """
        )

        with self.assertAddsMessages(
            pylint.testutils.MessageTest(
                msg_id="colrev-direct-status-assign",
                node=call_node,
                line=2,
                col_offset=0,
                end_line=2,
                end_col_offset=58,
            ),
        ):
            self.checker.visit_call(call_node)

        assignment_node = astroid.extract_node(
            """
        test["stats"] = "news"

        """
        )

        self.checker.visit_assign(assignment_node)
        self.assertNoMessages()


class TestRecordsVariableNamingConventionChecker(pylint.testutils.CheckerTestCase):
    """RecordsVariableNamingConventionChecker class"""

    CHECKER_CLASS = (
        colrev.linter.colrev_records_variable_naming_convention.RecordsVariableNamingConventionChecker
    )

    def test_finds_records_variable_naming_convention(self) -> None:
        """Test whether the pylint checker finds violations of records variable naming convention"""

        # Header_only
        assignment_node = astroid.extract_node(
            """
        items = dataset.load_records_dict(header_only=True)

        """
        )

        with self.assertAddsMessages(
            pylint.testutils.MessageTest(
                msg_id="colrev-records-variable-naming-convention",
                node=assignment_node,
                line=2,
                col_offset=0,
                end_line=2,
                end_col_offset=51,
            ),
        ):
            self.checker.visit_assign(assignment_node)

        assignment_node = astroid.extract_node(
            """
        items = dataset.load_records_dict(header_only=False)

        """
        )

        with self.assertAddsMessages(
            pylint.testutils.MessageTest(
                msg_id="colrev-records-variable-naming-convention",
                node=assignment_node,
                line=2,
                col_offset=0,
                end_line=2,
                end_col_offset=52,
            ),
        ):
            self.checker.visit_assign(assignment_node)

        assignment_node = astroid.extract_node(
            """
        records_headers = self.review_manager.dataset.load_records_dict(
            header_only=True
        )

        """
        )

        self.checker.visit_assign(assignment_node)
        self.assertNoMessages()

        # Records
        assignment_node = astroid.extract_node(
            """
        items = dataset.load_records_dict()

        """
        )

        with self.assertAddsMessages(
            pylint.testutils.MessageTest(
                msg_id="colrev-records-variable-naming-convention",
                node=assignment_node,
                line=2,
                col_offset=0,
                end_line=2,
                end_col_offset=35,
            ),
        ):
            self.checker.visit_assign(assignment_node)

        assignment_node = astroid.extract_node(
            """
        items = dataset.load_records_dict(verbose=True)

        """
        )

        with self.assertAddsMessages(
            pylint.testutils.MessageTest(
                msg_id="colrev-records-variable-naming-convention",
                node=assignment_node,
                line=2,
                col_offset=0,
                end_line=2,
                end_col_offset=47,
            ),
        ):
            self.checker.visit_assign(assignment_node)

        assignment_node = astroid.extract_node(
            """
        records = self.review_manager.dataset.load_records_dict()

        """
        )

        self.checker.visit_assign(assignment_node)
        self.assertNoMessages()

        assignment_node = astroid.extract_node(
            """
        var_1, var_2 = self.review_manager.dataset.load_records_dict()

        """
        )

        self.checker.visit_assign(assignment_node)
        self.assertNoMessages()

        assignment_node = astroid.extract_node(
            """
        var_1 = self.review_manager.dataset.load_records_dict

        """
        )

        self.checker.visit_assign(assignment_node)
        self.assertNoMessages()
