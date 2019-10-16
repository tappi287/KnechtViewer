"""
    As of PySide2 5.12.1 shiboken2 libary will not load when frozen with only it's compiled *.pyc files
    https://bugreports.qt.io/browse/PYSIDE-942
"""
from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files('shiboken2', include_py_files=True, subdir='support')