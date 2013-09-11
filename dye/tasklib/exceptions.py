class TasksError(Exception):
    """Base class for exceptions in this module."""
    def __init__(self, msg, exit_code=1):
        self.msg = msg
        self.exit_code = exit_code


class ShellCommandError(TasksError):
    """Exception raised for errors when calling shell commands."""
    pass


class InvalidProjectError(TasksError):
    """Exception raised when we failed to find something we require where we
    expected to."""
    pass


class InvalidPasswordError(TasksError):
    """Exception raised when we failed to find something we require where we
    expected to."""
    pass


class InvalidArgumentError(TasksError):
    """Exception raised when an argument is not valid."""
    def __init__(self, msg):
        self.msg = msg
        self.exit_code = 2
