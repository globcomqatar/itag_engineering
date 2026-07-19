"""File checksum computation and validation (roadmap Section 11.7)."""

import hashlib

import frappe


def compute_file_checksum_from_content(content):
	"""SHA-256 hex digest of raw file bytes."""
	return hashlib.sha256(content).hexdigest()


def validate_checksum(content, expected_checksum):
	return compute_file_checksum_from_content(content) == expected_checksum


def get_file_content(file_url):
	"""Read a Frappe-managed (private or public) file's raw bytes given its
	file_url, using the standard File doctype resolution so this works
	regardless of the underlying storage path.

	File.get_content() (frappe/core/doctype/file/file.py) is not guaranteed
	to return bytes: when reading a file back off disk it does
	`content.decode()` and only leaves the result as bytes if that raises
	UnicodeDecodeError (i.e. only for genuinely binary content like
	.png/.jpg). Any plain-text file - which most drawing/document uploads in
	a test suite, and plenty in real use, actually are - comes back as a
	`str`. Verified empirically against this Frappe version: a File created
	with content="test content" and re-fetched by file_url returns
	`str` ('test content'), not bytes. Passing that straight into
	hashlib.sha256() (via compute_file_checksum_from_content) raises
	`TypeError: Unicode-objects must be encoded before hashing` - so this
	must normalize to bytes here rather than trust get_content()'s return
	type."""
	file_doc = frappe.get_doc("File", {"file_url": file_url})
	content = file_doc.get_content()
	if isinstance(content, str):
		content = content.encode("utf-8")
	return content


def sync_drawing_checksum(doc, method=None):
	"""Populates Engineering Drawing.file_checksum from the approved_file's
	content whenever a file is attached and no checksum has been recorded yet
	- never overwrites an existing checksum (that would defeat its purpose
	once Released; Engineering Drawing's own validate() separately blocks
	replacing the file after a checksum exists at all, released or not).

	This is called directly from EngineeringDrawing.validate() (as the second
	statement, right after the release_status/workflow_state sync and before
	validate_release_requires_checksum()) rather than wired only as a
	`doc_events.before_save` hook. Frappe's own
	Document.run_before_save_methods() (frappe/model/document.py) always runs
	`validate` before `before_save` for the "save" action - never the other
	way around - so a `before_save`-only hook would populate file_checksum
	one step too late: validate_release_requires_checksum() (which runs
	inside validate()) would already have inspected file_checksum and thrown
	on the very save that is supposed to compute it, blocking a drawing with
	a real approved_file attached from ever reaching Released on its first
	checksum-computing save. Calling this function directly from validate(),
	before that guard runs, is what actually makes checksum population
	automatic for the release-gating path; it is also still safe to reuse as
	a `doc_events` hook body for other trigger points since it is idempotent
	(a no-op whenever file_checksum is already set).
	"""
	if doc.doctype != "Engineering Drawing":
		return
	if doc.approved_file and not doc.file_checksum:
		content = get_file_content(doc.approved_file)
		doc.file_checksum = compute_file_checksum_from_content(content)
