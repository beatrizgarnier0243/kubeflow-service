import os
import tempfile
import unittest

from kubeflow_service import ServiceResolver, ServiceInfo, resolve
from kubeflow_service.core import _parse_line


class TestParseLine(unittest.TestCase):
    def test_standard_entry(self):
        self.assertEqual(_parse_line("http 80/tcp www www-http"), ("http", 80, "tcp"))

    def test_comment_only(self):
        self.assertIsNone(_parse_line("# this is a comment"))

    def test_blank_line(self):
        self.assertIsNone(_parse_line(""))

    def test_inline_comment(self):
        self.assertEqual(_parse_line("ssh 22/tcp # SSH"), ("ssh", 22, "tcp"))

    def test_missing_protocol(self):
        self.assertIsNone(_parse_line("foo 80"))

    def test_non_numeric_port(self):
        self.assertIsNone(_parse_line("foo abc/tcp"))

    def test_case_normalization(self):
        self.assertEqual(_parse_line("HTTP 80/TCP"), ("http", 80, "tcp"))


class TestServiceResolver(unittest.TestCase):
    SAMPLE = (
        "# sample services\n"
        "http\t\t80/tcp www www-http\n"
        "http\t\t80/udp\n"
        "ssh\t\t22/tcp\n"
        "dns\t\t53/domain\n"
        "ntp\t\t123/udp\n"
        ""  # trailing blank line
    )

    def _make_resolver(self, content: str) -> ServiceResolver:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix="_services", delete=False)
        tmp.write(content)
        tmp.close()

        import kubeflow_service.core as core
        original_files = core._SERVICE_FILES
        core._SERVICE_FILES = (tmp.name,)
        try:
            return ServiceResolver()
        finally:
            core._SERVICE_FILES = original_files
            os.unlink(tmp.name)

    def setUp(self):
        import kubeflow_service.core as core
        core._resolver = None

    def test_lookup_tcp(self):
        r = self._make_resolver(self.SAMPLE)
        info = r.lookup("http", "tcp")
        self.assertIsInstance(info, ServiceInfo)
        self.assertEqual(info.name, "http")
        self.assertEqual(info.port, 80)
        self.assertEqual(info.protocol, "tcp")

    def test_lookup_udp(self):
        r = self._make_resolver(self.SAMPLE)
        info = r.lookup("http", "udp")
        self.assertEqual(info.port, 80)
        self.assertEqual(info.protocol, "udp")

    def test_lookup_no_protocol_prefers_tcp(self):
        r = self._make_resolver(self.SAMPLE)
        info = r.lookup("http")
        self.assertEqual(info.protocol, "tcp")

    def test_lookup_falls_back_to_non_standard_protocol(self):
        r = self._make_resolver(self.SAMPLE)
        info = r.lookup("dns")
        self.assertEqual(info.port, 53)
        self.assertEqual(info.protocol, "domain")

    def test_lookup_missing_service(self):
        r = self._make_resolver(self.SAMPLE)
        self.assertIsNone(r.lookup("nonexistent", "tcp"))

    def test_lookup_missing_protocol(self):
        r = self._make_resolver(self.SAMPLE)
        self.assertIsNone(r.lookup("ssh", "udp"))

    def test_first_wins_on_duplicate(self):
        content = "echo 7/tcp\necho 9/tcp\n"
        r = self._make_resolver(content)
        info = r.lookup("echo", "tcp")
        self.assertEqual(info.port, 7)

    def test_case_insensitive_lookup(self):
        r = self._make_resolver(self.SAMPLE)
        info = r.lookup("SSH", "TCP")
        self.assertEqual(info.port, 22)

    def test_empty_name_returns_none(self):
        r = self._make_resolver(self.SAMPLE)
        self.assertIsNone(r.lookup("", "tcp"))
        self.assertIsNone(r.lookup("   ", "tcp"))


class TestResolveFunction(unittest.TestCase):
    def setUp(self):
        import kubeflow_service.core as core
        core._resolver = None

    def test_resolve_real_http(self):
        # /etc/services universally contains http 80/tcp.
        # If the file is absent, skip rather than invent a result.
        if not os.path.isfile("/etc/services"):
            self.skipTest("no /etc/services on this system")
        info = resolve("http", "tcp")
        self.assertIsNotNone(info)
        self.assertEqual(info.port, 80)

    def test_resolve_returns_none_for_unknown(self):
        if not os.path.isfile("/etc/services"):
            self.skipTest("no /etc/services on this system")
        self.assertIsNone(resolve("zzzznotreal", "tcp"))


if __name__ == "__main__":
    unittest.main()
