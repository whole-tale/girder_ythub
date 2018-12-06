import json
from tests import base

# TODO: for some reason vcr is stuck in a infinite loop


def setUpModule():
    base.enabledPlugins.append('wholetale')
    base.startServer()


def tearDownModule():
    base.stopServer()


class RepositoryTestCase(base.TestCase):

    def _lookup(self, url, path):
        return self.request(
            path='/repository/' + path, method='GET',
            params={'dataId': json.dumps([url])}
        )

    def testErrorHandling(self):
        for path in ('lookup', 'listFiles'):
            resp = self._lookup('https://doi.org/10.7910/DVN/blah', path)
            self.assertStatus(resp, 400)
            self.assertEqual(resp.json, {
                'message': 'Id "https://doi.org/10.7910/DVN/blah" was '
                           'categorized as DOI, but its resolution failed.',
                'type': 'rest'
            })

            resp = self._lookup('https://wrong.url', path)
            self.assertStatus(resp, 400)
            if path == 'lookup':
                self.assertTrue(resp.json['message'].startswith(
                    'Lookup for "https://wrong.url" failed with:'
                ))
            else:
                self.assertTrue(resp.json['message'].startswith(
                    'Listing files at "https://wrong.url" failed with:'
                ))
