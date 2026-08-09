import unittest

from app.config import config
from app.segment import feature


class ConfigTests(unittest.TestCase):
    def test_yaml_config_is_loaded_without_versions(self) -> None:
        self.assertEqual(config.model.n_estimators, 200)
        self.assertEqual(config.model.balance_floor, 256)
        self.assertEqual(config.session.max_age, 3600)
        self.assertEqual(feature.COUNT, 16)
        self.assertEqual(config.performance.feature.max_workers, 12)
        self.assertEqual(config.performance.cuda_forest.early_exit[0].trees, 64)
        self.assertEqual(config.performance.export.png_compress_level, 1)
        self.assertNotIn("version", feature.config())


if __name__ == "__main__":
    unittest.main()
