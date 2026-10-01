import sys
import unittest
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from domains.amis.live_crm import check_amis_live_status  # noqa: E402


class AmisLiveStatusTests(unittest.TestCase):
    def test_status_does_not_call_a_credential_or_local_file_realtime(self):
        status = check_amis_live_status()

        self.assertEqual(status["mode"], "PROTECTED_WARM_CACHE")
        self.assertFalse(status["realtime_enabled"])
        self.assertIn("inventory", status["unavailable_realtime_capabilities"])
        self.assertIn("exact_order_code_plus_phone_hmac_fresh_cache", status["order_lookup"])


if __name__ == "__main__":
    unittest.main()
