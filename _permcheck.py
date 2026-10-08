import sys

import jsonschema
import pptx
import pytest

print("python    ", sys.version.split()[0])
print("python-pptx", pptx.__version__)
print("jsonschema", jsonschema.__version__)
print("pytest    ", pytest.__version__)
