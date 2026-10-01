import sys
import unittest
from pathlib import Path


SERVER_DIR = Path(__file__).resolve().parents[1]
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from domains.rag_test.routes import ChatPipelineDebugRequest, _debug_message_id  # noqa: E402


class DebugEndpointContractTests(unittest.TestCase):
    def test_missing_message_id_generates_a_unique_id_for_each_turn(self):
        request = ChatPipelineDebugRequest(text="Alo")

        first = _debug_message_id(request)
        second = _debug_message_id(request)

        self.assertTrue(first.startswith("dashboard-debug:"))
        self.assertNotEqual(first, second)

    def test_explicit_message_id_is_preserved_for_duplicate_testing(self):
        request = ChatPipelineDebugRequest(text="Alo", message_id="mid-retry-1")

        self.assertEqual(_debug_message_id(request), "mid-retry-1")


if __name__ == "__main__":
    unittest.main()
