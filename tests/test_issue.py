# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: 
"""
import sys
import unittest

sys.path.append('..')
from codev.format_command import format_command_for_display, parse_command


class IssueTestCase(unittest.TestCase):

    def test_code_predict(self):
        prompts = """ls
            ll
            'touch test.txt'
            """
        results = parse_command(prompts)
        print(results)
        self.assertEqual(len(results), 3)


if __name__ == '__main__':
    unittest.main()
