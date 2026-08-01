import unittest

from app.config import config
from app.segment import feature


class ConfigTests(unittest.TestCase):
    def test_yaml_config_is_loaded_without_versions(self) -> None:
        self.assertEqual(config.refine.patch, 256)
        self.assertEqual(config.model.n_estimators, 200)
        self.assertEqual(feature.COUNT, 15)
        self.assertNotIn("version", feature.config())


if __name__ == "__main__":
    unittest.main()
