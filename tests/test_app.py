from __future__ import annotations

import threading
import unittest
import urllib.request

from momentshow.app import create_server


class AppTests(unittest.TestCase):
    def test_home_is_gui_with_tabs(self) -> None:
        httpd = create_server("127.0.0.1", 0)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = httpd.server_address[:2]
            with urllib.request.urlopen(f"http://{host}:{port}/", timeout=2) as response:
                html = response.read().decode("utf-8")
        finally:
            httpd.shutdown()
            httpd.server_close()
        self.assertIn("帮我回", html)
        self.assertIn("朋友圈", html)
        self.assertIn('id="tab-chat"', html)
        self.assertIn('id="tab-moments"', html)
        self.assertIn("读取窗口", html)
        self.assertIn("打开微信并采集", html)
        self.assertIn("class=\"split\"", html)


if __name__ == "__main__":
    unittest.main()
