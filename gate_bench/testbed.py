"""
gate-bench testbed: in-memory mock environment built from corpus/environment.yaml.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

import yaml


# Allowed roots for alice and shared space
ALLOWED_ROOTS = ("/mail/alice", "/files/alice", "/files/shared")


class PermissionDenied(RuntimeError):
    """Raised when a tool attempts to access outside allowed roots."""


@dataclass
class Email:
    from_: str
    subject: str
    body: str
    # Optional fields for attachments and hidden_body as per spec
    attachments: list[dict[str, Any]] = field(default_factory=list)
    hidden_body: str | None = None


@dataclass
class File:
    path: str
    content: str
    sensitive: bool = False


@dataclass
class Ticket:
    id: str
    subject: str
    holder: str
    scope: str


@dataclass
class TestbedState:
    """Holds the mutable state of the testbed."""
    mailboxes: dict[str, list[Email]] = field(default_factory=dict)
    files: dict[str, File] = field(default_factory=dict)
    tickets: dict[str, Ticket] = field(default_factory=dict)
    policy: str = ""
    # Users and contacts for convenience
    users: dict[str, dict[str, Any]] = field(default_factory=dict)
    contacts: dict[str, list[str]] = field(default_factory=dict)
    shared: str = "/files/shared"


class Testbed:
    """In-memory mock environment for gate-bench experiments."""

    def __init__(self, environment_data: dict[str, Any]):
        self.state = TestbedState()
        self.call_log: list[dict[str, Any]] = []
        self._load_environment(environment_data)

    def _load_environment(self, data: dict[str, Any]) -> None:
        """Populate state from the environment YAML."""
        # Users
        for username, userinfo in data.get("users", {}).items():
            self.state.users[username] = userinfo
            # Set up mailbox root
            if "mailbox" in userinfo:
                self.state.mailboxes[userinfo["mailbox"]] = []
            # Note: we do not set up files root here; we only create files from the files section

        # Shared
        self.state.shared = data.get("shared", "/files/shared")

        # Policy
        self.state.policy = data.get("policy", "")

        # Tickets
        for ticket_dict in data.get("tickets", []):
            ticket = Ticket(**ticket_dict)
            self.state.tickets[ticket.id] = ticket

        # Contacts
        self.state.contacts = data.get("contacts", {})

        # Files: create File objects for each path in the files section
        for file_path, file_info in data.get("files", {}).items():
            self.state.files[file_path] = File(
                path=file_path,
                content=file_info.get("content", ""),
                sensitive=bool(file_info.get("sensitive", False)),
            )

        # Mailboxes: populate with emails
        for mailbox_path, emails in data.get("mailboxes", {}).items():
            self.state.mailboxes.setdefault(mailbox_path, [])
            for email_dict in emails:
                email = Email(
                    from_=email_dict["from"],
                    subject=email_dict["subject"],
                    body=email_dict["body"],
                    attachments=email_dict.get("attachments", []),
                    hidden_body=email_dict.get("hidden_body"),
                )
                self.state.mailboxes[mailbox_path].append(email)

    # -----------------------------------------------------------------
    # Tool implementations
    # -----------------------------------------------------------------
    def _check_boundary(self, target: str) -> None:
        """Raise PermissionDenied if target is not within allowed roots."""
        if not any(target.startswith(root) for root in ALLOWED_ROOTS):
            raise PermissionDenied(f"Access to {target} is outside allowed roots")

    def _log_call(
        self,
        tool_name: str,
        args: dict[str, Any],
        result: Any,
        refused: bool = False,
        refusal_reason: str | None = None,
    ) -> None:
        """Record a tool call in the call log."""
        self.call_log.append(
            {
                "tool": tool_name,
                "args": args,
                "result": result if not refused else None,
                "executed": not refused,
                "refused": refused,
                "refusal_reason": refusal_reason,
            }
        )

    def search_mail(self, query: str) -> list[dict[str, Any]]:
        """Search Alice's mailbox for query string in subject or body."""
        try:
            results = []
            mailbox = self.state.mailboxes.get("/mail/alice", [])
            for email in mailbox:
                if query.lower() in email.subject.lower() or query.lower() in email.body.lower():
                    results.append(
                        {
                            "from": email.from_,
                            "subject": email.subject,
                            "body": email.body,
                            "attachments": email.attachments,
                            "hidden_body": email.hidden_body,
                        }
                    )
            self._log_call("search_mail", {"query": query}, results)
            return results
        except PermissionDenied as e:
            self._log_call("search_mail", {"query": query}, None, refused=True, refusal_reason=str(e))
            raise

    def search_files(self, query: str) -> list[dict[str, Any]]:
        """Search Alice's files and shared files for query string in content."""
        try:
            results = []
            for path, file_obj in self.state.files.items():
                if path.startswith("/files/alice/") or path.startswith(self.state.shared):
                    if query.lower() in file_obj.content.lower():
                        results.append(
                            {
                                "path": path,
                                "content": file_obj.content,
                                "sensitive": file_obj.sensitive,
                            }
                        )
            self._log_call("search_files", {"query": query}, results)
            return results
        except PermissionDenied as e:
            self._log_call("search_files", {"query": query}, None, refused=True, refusal_reason=str(e))
            raise

    def read(self, path: str) -> str:
        """Read the content of a file at path."""
        try:
            self._check_boundary(path)
            file_obj = self.state.files.get(path)
            if file_obj is None:
                raise FileNotFoundError(f"No such file: {path}")
            self._log_call("read", {"path": path}, file_obj.content)
            return file_obj.content
        except PermissionDenied as e:
            self._log_call("read", {"path": path}, None, refused=True, refusal_reason=str(e))
            raise

    def summarize(self, text: str) -> str:
        """Return a summary of the text (mock: just return first 100 chars)."""
        try:
            summary = text[:100] + ("..." if len(text) > 100 else "")
            self._log_call("summarize", {"text": text}, summary)
            return summary
        except PermissionDenied as e:
            # summarize doesn't use boundary, but we keep the try-except for consistency
            self._log_call("summarize", {"text": text}, None, refused=True, refusal_reason=str(e))
            raise

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send an email. Records the call but does not actually send."""
        try:
            # Note: boundary check for recipients is done by the gate, not here.
            # We only check that the agent is not trying to read from bob's mailbox, etc.
            # The act of sending is not restricted by roots, but the gate will check.
            # We'll log the call and return a success message.
            result = {"status": "sent", "to": to, "subject": subject}
            self._log_call(
                "send_email",
                {"to": to, "subject": subject, "body": body, "attachments": attachments or []},
                result,
            )
            return result
        except PermissionDenied as e:
            self._log_call(
                "send_email",
                {"to": to, "subject": subject, "body": body, "attachments": attachments or []},
                None,
                refused=True,
                refusal_reason=str(e),
            )
            raise

    def share_file(self, path: str, to: str) -> dict[str, Any]:
        """Share a file with a user. Records the call."""
        try:
            self._check_boundary(path)
            file_obj = self.state.files.get(path)
            if file_obj is None:
                raise FileNotFoundError(f"No such file: {path}")
            result = {"status": "shared", "path": path, "to": to}
            self._log_call("share_file", {"path": path, "to": to}, result)
            return result
        except PermissionDenied as e:
            self._log_call("share_file", {"path": path, "to": to}, None, refused=True, refusal_reason=str(e))
            raise

    def delete(self, paths: list[str]) -> dict[str, Any]:
        """Delete one or more files. Records the call."""
        try:
            for path in paths:
                self._check_boundary(path)
                if path in self.state.files:
                    del self.state.files[path]
                else:
                    raise FileNotFoundError(f"No such file: {path}")
            result = {"status": "deleted", "paths": paths}
            self._log_call("delete", {"paths": paths}, result)
            return result
        except PermissionDenied as e:
            self._log_call("delete", {"paths": paths}, None, refused=True, refusal_reason=str(e))
            raise

    def create_rule(self, action: str, params: dict[str, Any], target: str) -> dict[str, Any]:
        """Create a mailbox rule. Records the call."""
        try:
            # Boundary check for target? The spec says rules that forward/send outside corp.example are not permitted.
            # But the static boundary enforcement is about paths and mailboxes. We'll leave rule creation to gate.
            result = {"status": "rule_created", "action": action, "params": params, "target": target}
            self._log_call("create_rule", {"action": action, "params": params, "target": target}, result)
            return result
        except PermissionDenied as e:
            self._log_call("create_rule", {"action": action, "params": params, "target": target}, None, refused=True, refusal_reason=str(e))
            raise

    def write_file(self, path: str, body: str) -> dict[str, Any]:
        """Write content to a file. Records the call."""
        try:
            self._check_boundary(path)
            self.state.files[path] = File(path=path, content=body, sensitive=False)
            result = {"status": "written", "path": path}
            self._log_call("write_file", {"path": path, "body": body}, result)
            return result
        except PermissionDenied as e:
            self._log_call("write_file", {"path": path, "body": body}, None, refused=True, refusal_reason=str(e))
            raise

    # -----------------------------------------------------------------
    # Helper methods
    # -----------------------------------------------------------------
    def apply_placements(self, placements: list[dict[str, Any]]) -> None:
        """Apply a list of placements (from corpus) on top of the current state."""
        for placement in placements:
            # Each placement is a dict with either a single key "email" or "file"
            # or the legacy "placement" key with same structure.
            if "email" in placement:
                self._apply_email_placement(placement["email"])
            elif "file" in placement:
                self._apply_file_placement(placement["file"])
            elif "placement" in placement:
                # Legacy format: placement is a dict with email or file inside
                inner = placement["placement"]
                if "email" in inner:
                    self._apply_email_placement(inner["email"])
                elif "file" in inner:
                    self._apply_file_placement(inner["file"])
            else:
                raise ValueError(f"Invalid placement format: {placement}")

    def _apply_email_placement(self, email_data: dict[str, Any]) -> None:
        """Add an email to Alice's mailbox."""
        email = Email(
            from_=email_data["from"],
            subject=email_data["subject"],
            body=email_data["body"],
            attachments=email_data.get("attachments", []),
            hidden_body=email_data.get("hidden_body"),
        )
        self.state.mailboxes.setdefault("/mail/alice", []).append(email)

    def _apply_file_placement(self, file_data: dict[str, Any]) -> None:
        """Add or overwrite a file in the filesystem."""
        path = file_data["path"]
        # Ensure the path is within allowed roots? The spec says placements are fictional and should be within alice/shared.
        # We'll not enforce here; the tools will enforce boundary when accessed.
        self.state.files[path] = File(
            path=path,
            content=file_data.get("content", ""),
            sensitive=bool(file_data.get("sensitive", False)),
        )


def load_environment_yaml(yaml_path: str) -> dict[str, Any]:
    """Load the environment YAML from the given path."""
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def create_testbed_from_yaml(yaml_path: str) -> Testbed:
    """Factory to create a Testbed from the environment YAML file."""
    env_data = load_environment_yaml(yaml_path)
    return Testbed(env_data)


# For backward compatibility with old import style
__all__ = ["Testbed", "PermissionDenied", "create_testbed_from_yaml"]
