"""
"""
import os
import glob
def test_imports():
    tmp = os.path.dirname(__file__)
    tmp = os.path.dirname(os.path.dirname(tmp))
    tmp = os.path.join(tmp,'src/*.py')
    tmp = [os.path.split(x)[-1] for x in glob.glob(tmp)]
    tmp = [os.path.splitext(x)[0] for x in tmp if not x.startswith('_')]
    for x in tmp:
        exec(f'import {x}')
