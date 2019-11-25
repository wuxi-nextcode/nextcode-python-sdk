from nextcode.utils import host_from_url
from tests import BaseTestCase


class UtilsTest(BaseTestCase):
    def test_host_from_url(self):
        url = "https://www.server.com"
        ret = host_from_url(url)
        self.assertEqual(ret, url + "/")

        url = "https://www.server.com/"
        ret = host_from_url(url)
        self.assertEqual(ret, url)

        url = "https://www.server.com/"
        ret = host_from_url(url + "path/another")
        self.assertEqual(ret, url)

        url = "http://www.server.com:8080/"
        ret = host_from_url(url)
        self.assertEqual(ret, url)

        url = "http://www.server.com:8080"
        ret = host_from_url(url)
        self.assertEqual(ret, url + "/")

        url = "www.server.com:8080/"
        ret = host_from_url(url)
        self.assertEqual(ret, "https://" + url)

        url = "localhost:8080"
        ret = host_from_url(url)
        self.assertEqual(ret, "https://" + url + "/")

        url = "http://localhost:8080"
        ret = host_from_url(url)
        self.assertEqual(ret, url + "/")
