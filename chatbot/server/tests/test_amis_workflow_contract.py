import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_PUBLIC_SYNC = ROOT / "workflows" / "local-n8n" / "amis_crm_public_sync.workflow.ts"
WORKFLOW_FULL_WARM = ROOT / "workflows" / "local-n8n" / "amis_crm_full_warm.workflow.ts"


class AmisWorkflowContractTests(unittest.TestCase):
    def test_public_sync_workflow_is_inactive_and_never_contains_amis_secret(self):
        source = WORKFLOW_PUBLIC_SYNC.read_text(encoding="utf-8")

        self.assertIn("active: false", source)
        self.assertIn("/admin/amis/sync", source)
        self.assertIn("AMIS_SYNC_INTERNAL_TOKEN", source)
        self.assertNotIn("AMIS_CLIENT_SECRET", source)
        self.assertNotRegex(source, r"client_secret\s*[:=]")

    def test_full_warm_workflow_contract_and_security(self):
        source = WORKFLOW_FULL_WARM.read_text(encoding="utf-8")

        # Live Full Warm is the sole hourly writer for private order snapshots.
        self.assertIn("active: true", source)
        self.assertIn("/admin/amis/warm", source)
        self.assertIn("CLIENT_SECRET", source)
        # Verify no literal secret is hardcoded in git repo template
        self.assertNotRegex(source, r"CLIENT_SECRET\s*=\s*['\"][a-zA-Z0-9_-]{10,}['\"]")

    def test_full_warm_stages_small_chunks_before_commit(self):
        source = WORKFLOW_FULL_WARM.read_text(encoding="utf-8")

        for contract in (
            "const CHUNK_SIZE = 100",
            "/admin/amis/warm/stage",
            "/admin/amis/warm/commit",
            "Prepare AMIS Warm Commit",
            "refusing a partial snapshot",
            "MAX_TRANSIENT_RETRIES = 5",
            "requestWithRetry",
            "PAGE_GAP_MS = 250",
        ):
            self.assertIn(contract, source)

    def test_embedded_code_node_javascript_is_valid(self):
        for workflow_path in (WORKFLOW_PUBLIC_SYNC, WORKFLOW_FULL_WARM):
            source = workflow_path.read_text(encoding="utf-8")
            snippets = re.findall(r"jsCode:\s*`([\s\S]*?)`", source)
            self.assertGreater(len(snippets), 0, f"No jsCode in {workflow_path.name}")

            for idx, snippet in enumerate(snippets):
                # n8n Code nodes run inside an async runner function.
                wrapped = f"async function _testRunner() {{\n{snippet}\n}}"
                completed = subprocess.run(
                    ["node", "--check"],
                    input=wrapped,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(
                    completed.returncode,
                    0,
                    f"JS syntax error in {workflow_path.name} snippet #{idx}: {completed.stderr}",
                )


if __name__ == "__main__":
    unittest.main()
