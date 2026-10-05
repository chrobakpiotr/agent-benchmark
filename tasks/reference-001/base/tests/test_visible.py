import unittest

from calc import median


class VisibleMedian(unittest.TestCase):
    def test_sorted_odd(self):
        self.assertEqual(median([1, 2, 3]), 2)
