import setuptools

""" 

To distribute:
=============
rm dist/*; python setup.py sdist bdist_wheel; python -m twine upload dist/* 

"""

 

setuptools.setup(
    name="hardwarelibrary",
    version="1.0.5",
    url="https://github.com/DCC-Lab/PyHardwareLibrary",
    author="Daniel Cote",
    author_email="dccote@cervo.ulaval.ca",
    description="Cross-platform (macOS, Windows, Linux, etc...) library to control various hardware devices mostly for scientific applications.",
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    license='MIT',
    keywords='hardware devices usb communication app control spectrometer powermeter camera',
    packages=setuptools.find_packages(),
    install_requires=['numpy','matplotlib','PySerial','PyUSB','pyftdi','LabJackPython'],
    python_requires='>=3.7',
    package_data = {
        # If any package contains *.txt or *.rst files, include them:
        '': ['*.png'],
        "doc": ['*.html']
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        # Indicate who your project is intended for
        'Intended Audience :: Science/Research',
        'Intended Audience :: Education',
        'Topic :: Scientific/Engineering :: Physics',
        'Topic :: Education',

        # Pick your license as you wish (should match "license" above)
         'License :: OSI Approved :: MIT License',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',

        'Operating System :: OS Independent'
    ]
)
