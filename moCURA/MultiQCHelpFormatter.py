import argparse
import textwrap

class MultiQCHelpFormatter(argparse.HelpFormatter):
    """
    Custom argparse help formatter to match the style of MultiQC
    """
    def __init__(self, prog, indent_increment=2, max_help_position=24, width=None):
        if width is None:
            width = 120
        super().__init__(indent_increment, max_help_position, width)
        self._prog = prog

    def format_help(self):
        # The main help text
        help_text = super().format_help()

        # Split into sections
        help_sections = help_text.split('\n\n')
        
        # General usage
        usage = help_sections[0] if len(help_sections) > 0 else ""
        
        # Description (may not exist)
        description = help_sections[1] if len(help_sections) > 1 else ""

        # Epilog
        epilog = help_sections[-1] if len(help_sections) > 2 else ""

        # Build the new help string
        new_help_string = f"{usage}\n\n"
        if description:
            new_help_string += f"{description}\n\n"

        # Format and add the argument sections
        for group in self._parser._action_groups:
            if group._group_actions:
                line_width = self._width
                new_help_string += f"╭─ {group.title} {'─'*(line_width - len(group.title) - 5)}─╮\n"
                for action in group._group_actions:
                    if action.help != argparse.SUPPRESS:
                        long_option = max((opt for opt in action.option_strings if opt.startswith('--')), default='')
                        short_option = min((opt for opt in action.option_strings if not opt.startswith('--')), default='')
                        
                        help_text = action.help or ""
                        wrapped_help = textwrap.wrap(help_text, line_width - 35) or [""]
                        
                        line1 = f"│ {long_option:<20} {short_option:<5} {wrapped_help[0]}"
                        new_help_string += f"{line1}{' '*(line_width - len(line1) -1)} │\n"

                        for line in wrapped_help[1:]:
                            line = f"│ {'':<27} {line}"
                            new_help_string += f"{line}{' '*(line_width - len(line) -1)} │\n"
                new_help_string += f"╰{'─'*(line_width-2)}─╯\n\n"
        
        if epilog:
            new_help_string += f"{epilog}\n"

        return new_help_string

class CustomArgumentParser(argparse.ArgumentParser):
    def _get_formatter(self):
        formatter = super()._get_formatter()
        formatter._parser = self
        return formatter