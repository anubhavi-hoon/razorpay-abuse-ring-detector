import unittest

import abuse_detector


class PackageTest(unittest.TestCase):
    def test_package_imports(self):
        self.assertEqual(abuse_detector.__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()

