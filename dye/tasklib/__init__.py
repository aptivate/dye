# import all functions that don't start with _
from .django import link_local_settings
from .tasklib import *

# the global dictionary
from .environment import env

# import this one that does - used in a few places
from .tasklib import _setup_paths
