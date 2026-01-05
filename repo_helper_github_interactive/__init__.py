#!/usr/bin/env python3
#
#  __init__.py
"""
Interactive session for 'repo_helper_github'.
"""
#
#  Copyright © 2021 Dominic Davis-Foster <dominic@davis-foster.co.uk>
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all
#  copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
#  EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
#  MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
#  DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
#  OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE
#  OR OTHER DEALINGS IN THE SOFTWARE.
#
# Parts based on https://pymotw.com/2/readline/
#

# stdlib
import difflib
import readline
import sys
import traceback
from typing import List, Optional, Tuple

# 3rd party
import click  # type: ignore[import-untyped]
import platformdirs
import repo_helper_github
from consolekit.input import prompt
from consolekit.terminal_colours import ColourTrilean
from domdf_python_tools.paths import PathPlus
from repo_helper_github import GitHubManager
from repo_helper_github.cli import github

__author__: str = "Dominic Davis-Foster"
__copyright__: str = "2021 Dominic Davis-Foster"
__license__: str = "MIT License"
__version__: str = "0.0.0"
__email__: str = "dominic@davis-foster.co.uk"

__all__ = ["History", "InteractiveParser", "interactive_prompt"]


class History:
	"""
	Represents a readline history file.

	.. versionadded:: 0.6.0
	"""

	#: The underlying file.
	file: PathPlus

	def __init__(self):
		self.file = PathPlus(platformdirs.user_config_dir("github", "repo-helper")) / "interactive.hist"

	def read(self) -> None:
		"""
		Read the history file.
		"""

		if self.file.is_file():
			readline.read_history_file(str(self.file))

	def write(self) -> None:
		"""
		Read modified history file to disk.
		"""

		self.file.parent.maybe_make()
		readline.write_history_file(str(self.file))

	@staticmethod
	def get_history_items() -> List[str]:
		"""
		Returns a list of items in the readline history.
		"""

		return [readline.get_history_item(i) for i in range(1, readline.get_current_history_length() + 1)]


HISTORY_FILE = History()


def parse_command(command: str) -> Tuple[Optional[str], Tuple[str, ...]]:
	"""
	Given a ``command``, parse it and return the name of the actual command to run.

	:param command: The name of the command to run.

	:returns: The actual command name (or :py:obj:`None` if there is no matching command),
		and a tuple of any arguments to be passed to the command.
	"""

	command = command.lower().strip()
	command, *args = command.split(' ')

	if command in {'q', "quit"}:
		raise KeyboardInterrupt
	elif command in {'h', "help"}:
		longest_command = max(len(click_command.name) for click_command in github.commands.values())
		longest_command = max(4, longest_command)

		for click_command in github.commands.values():
			click.echo(f"  {click_command.name.rjust(longest_command)} -- {click_command.help}")
		click.echo(f"  {'help'.rjust(longest_command)} -- Show this help message.")
		click.echo(f"  {'quit'.rjust(longest_command)} -- Exit the interactive prompt.")
	elif command in github.commands:
		if command == "labels":
			return "create_labels", tuple(args)
		elif command == "protect_branch":
			return command, tuple(args)
		else:
			return command.replace('-', '_'), tuple(args)
	else:
		click.echo(f"Error: Unknown command {command!r}")
		matches = difflib.get_close_matches(command, github.commands.keys())
		if matches:
			click.echo(f"Did you mean {matches[0]!r}?")

	return None, ()


class InteractiveParser:
	"""
	Provides functionality for the interactive parser.
	"""

	def __init__(self):
		self.matches = []

	def complete(self, text: str, state: int) -> Optional[str]:
		"""
		Handles tab completion.

		:param text: The text to tab complete.
		:param state:

		:returns: The matching string, or :py:obj:`None` is no match is found.
		"""

		if state == 0:
			# This is the first time for this text, so build a match list.
			if text:
				self.matches = [s for s in github.commands if s and s.startswith(text)]
			else:
				self.matches = []

		# Return the state'th item from the match list, if we have that many.
		try:
			return self.matches[state]
		except IndexError:
			return None


def interactive_prompt(
		token: str,
		*,
		verbose: bool = False,
		colour: ColourTrilean = True,
		org: bool = True,
		) -> None:
	"""
	Start an interactive session.

	:param token: The token to authenticate with the GitHub API.
	:param verbose: Whether to show information on the GitHub API rate limit.
	:param colour: Whether to use coloured output.
	:param org: Indicates the repository belongs to the organisation configured as
		'username' in repo_helper.yml.
	"""

	click.echo("repo_helper_github interactive prompt.")
	click.echo(f"Version {repo_helper_github.__version__}")
	click.echo(f"Type 'help' for help or 'quit' to exit.")

	readline.set_history_length(-1)
	readline.set_auto_history(True)

	parser = InteractiveParser()
	manager = GitHubManager(token, PathPlus.cwd(), verbose=verbose, colour=colour)

	# This will catch a missing --org option error earlier
	manager.get_org_or_user(org)

	readline.parse_and_bind("tab: complete")
	readline.set_completer(parser.complete)
	HISTORY_FILE.read()

	HISTORY_FILE.get_history_items()

	try:
		while True:
			for command in prompt('>', prompt_suffix=' ').split("&&"):
				command = command.lower().strip()

				command, args = parse_command(command)
				if command is not None:
					try:
						getattr(manager, command)(*args, org=org)
					except Exception:
						click.echo(traceback.format_exc())

	except (KeyboardInterrupt, EOFError, click.Abort):
		click.echo("\nExiting...")
		sys.exit(0)
	finally:
		HISTORY_FILE.write()
