import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from product_demo.roles.cli import main
from product_demo.roles.policy import AccessDenied, Action, Role, RoleStore


class RoleFragmentTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="s02-tests-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "accounts.json"
        self.store = RoleStore.initialize(self.path)
        self.store.assign("T-admin", "T-applicant", "applicant")
        self.store.assign("T-admin", "T-approver", "approver")

    def test_admin_assigns_every_role_and_reload_persists_it(self):
        for role in Role:
            with self.subTest(role=role.value):
                self.store.assign("T-admin", "T-applicant", role)
                self.assertEqual(RoleStore(self.path).role_for("T-applicant"), role)

    def test_eighteen_role_action_cells(self):
        expected = {
            "T-applicant": {Action.SEARCH, Action.SUBMIT_REQUEST,
                            Action.READ_OWN_REQUEST, Action.CANCEL_OWN_REQUEST},
            "T-approver": {Action.APPROVE_REQUEST},
            "T-admin": {Action.EDIT_CATALOG},
        }
        actions = [action for action in Action if action != Action.ASSIGN_ROLE]
        self.assertEqual(len(actions), 6)
        for account, allowed in expected.items():
            for action in actions:
                with self.subTest(account=account, action=action.value):
                    self.assertEqual(self.store.allows(account, action), action in allowed)

    def test_denied_business_callbacks_never_execute(self):
        for account, action in [("T-applicant", Action.APPROVE_REQUEST),
                                ("T-applicant", Action.EDIT_CATALOG),
                                ("T-approver", Action.EDIT_CATALOG)]:
            with self.subTest(account=account, action=action):
                callback = Mock()
                snapshot = self.path.read_bytes()
                with self.assertRaises(AccessDenied):
                    self.store.guarded(account, action, callback)
                callback.assert_not_called()
                self.assertEqual(self.path.read_bytes(), snapshot)

    def test_allowed_guard_runs_callback_once(self):
        for account, action in [("T-approver", Action.APPROVE_REQUEST),
                                ("T-admin", Action.EDIT_CATALOG)]:
            with self.subTest(account=account, action=action):
                callback = Mock(return_value="synthetic result")
                self.assertEqual(self.store.guarded(account, action, callback), "synthetic result")
                callback.assert_called_once_with()

    def test_non_admin_cannot_assign_roles_or_change_file(self):
        for actor in ["T-applicant", "T-approver", "T-unknown"]:
            with self.subTest(actor=actor):
                snapshot = self.path.read_bytes()
                with self.assertRaises(AccessDenied):
                    self.store.assign(actor, "T-applicant", "admin")
                self.assertEqual(self.path.read_bytes(), snapshot)

    def test_unknown_account_missing_or_unknown_role_denies_all_actions(self):
        for role in [None, "unknown", "", [], {}]:
            with self.subTest(role=role):
                data = {"accounts": {"T-bad": role}}
                self.path.write_text(json.dumps(data), encoding="utf-8")
                store = RoleStore(self.path)
                self.assertIsNone(store.role_for("T-bad"))
                for action in Action:
                    self.assertFalse(store.allows("T-bad", action))
                    self.assertFalse(store.allows("T-unknown", action))

    def test_unknown_operation_is_denied(self):
        for action in ["delete_everything", "", None]:
            self.assertFalse(self.store.allows("T-admin", action))

    def test_invalid_assigned_role_or_subject_does_not_mutate(self):
        for subject, role in [("T-applicant", "unknown"), ("T-missing", "applicant")]:
            with self.subTest(subject=subject, role=role):
                snapshot = self.path.read_bytes()
                with self.assertRaises(ValueError):
                    self.store.assign("T-admin", subject, role)
                self.assertEqual(self.path.read_bytes(), snapshot)

    def test_init_refuses_to_overwrite_existing_store(self):
        snapshot = self.path.read_bytes()
        with self.assertRaises(FileExistsError):
            RoleStore.initialize(self.path)
        self.assertEqual(self.path.read_bytes(), snapshot)

    def test_failed_atomic_save_keeps_memory_and_file_unchanged(self):
        snapshot = self.path.read_bytes()
        with patch("product_demo.roles.policy.os.replace", side_effect=OSError("test failure")):
            with self.assertRaises(OSError):
                self.store.assign("T-admin", "T-applicant", "admin")
        self.assertEqual(self.store.role_for("T-applicant"), Role.APPLICANT)
        self.assertEqual(self.path.read_bytes(), snapshot)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_malformed_store_is_not_treated_as_authorized(self):
        for body in ["not JSON", "[]", '{"accounts": []}', '{"accounts": {}, "other": true}']:
            self.path.write_text(body, encoding="utf-8")
            with self.assertRaises(ValueError):
                RoleStore(self.path)

    def test_cli_denial_exit_code_and_no_mutation(self):
        snapshot = self.path.read_bytes()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["--store", str(self.path), "probe", "--actor", "T-applicant",
                         "--action", "approve_request"])
        self.assertEqual(code, 3)
        self.assertFalse(json.loads(output.getvalue())["probe_executed"])
        self.assertEqual(self.path.read_bytes(), snapshot)

    def test_cli_assign_and_read_after_reload(self):
        for command in [["assign", "--actor", "T-admin", "--subject", "T-applicant", "--role", "approver"],
                        ["role", "--subject", "T-applicant"]]:
            with self.subTest(command=command):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(main(["--store", str(self.path), *command]), 0)
                self.assertEqual(json.loads(output.getvalue())["role"], "approver")


if __name__ == "__main__":
    unittest.main()
