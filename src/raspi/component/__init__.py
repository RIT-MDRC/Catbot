# Keep this file empty as this will cause the package to be imported when any of the submodule is imported.
# for example:
# `import component.motor` in the script file somewhere else
# will run component.__init__.py
# then run component/motor/__init__.py
# Meaning importing any of the submodules in component will import any file referenced here.
# If that is expected then put it here, otherwise, do not put anything here.

from . import latch
