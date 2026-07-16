"""czcore — shared core for control-z standalone tools.

Pure-python algorithm pieces live here with no heavy imports at module load;
decode/encode/model code guards its dependencies so the test suite runs anywhere.
"""

__version__ = "0.1.0"
