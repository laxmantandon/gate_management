from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in gate_management/__init__.py
from gate_management import __version__ as version

setup(
	name="gate_management",
	version=version,
	description="Gate management",
	author="laxmantandon@gmail.com",
	author_email="laxmantandon@gmail.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
