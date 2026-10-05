import unittest

from calc import median


class HiddenMedian(unittest.TestCase):
    def test_unsorted_odd(self):
        self.assertEqual(median([9, 1, 5]), 5)

    def test_unsorted_even(self):
        self.assertEqual(median([4, 1, 3, 2]), 2.5)

    def test_single(self):
        self.assertEqual(median([7]), 7)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            median([])
