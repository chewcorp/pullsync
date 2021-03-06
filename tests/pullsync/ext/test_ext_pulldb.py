import json
import os
import sys

from apiclient.http import HttpMock, HttpMockSequence
from cement.core import foundation, handler
from cement.utils import test
import mock

from pullsync.ext.ext_pulldb import FetchError, UpdateError

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')


def datafile(name):
    return os.path.join(TEST_DATA_DIR, name)


class TestApp(foundation.CementApp):
    class Meta:
        label = 'pullsync'
        argv = []
        config_files = [
            datafile('pulldb.conf')
        ]
        extensions = [
            'pullsync.ext.interfaces',
            'pullsync.ext.ext_google',
            'pullsync.ext.ext_pulldb',
        ]


class PulldbTest(test.CementTestCase):
    app_class = TestApp

    def fetch_unread_test(self):
        self.app.setup()
        with open(os.path.join(TEST_DATA_DIR, 'unread.json')) as json_file:
            unread = json.load(json_file)
        self.app.pulldb.fetch_page = mock.Mock(return_value=unread)
        self.assertEqual(len(unread['results']), 100)
        results = self.app.pulldb.fetch_unread()
        self.app.pulldb.fetch_page.assert_called_with(
            '/api/pulls/list/unread', cursor=None
        )
        self.assertEqual(len(results), 100)
        for pull in results:
            self.assertTrue('issue_id' in pull)

    def fetch_new_test(self):
        self.app.setup()
        with open(os.path.join(TEST_DATA_DIR, 'fetch_new.json')) as json_file:
            unread = json.load(json_file)
        self.app.pulldb.fetch_page = mock.Mock(return_value=unread)
        self.assertEqual(len(unread['results']), 5)
        results = self.app.pulldb.fetch_new()
        self.app.pulldb.fetch_page.assert_called_with(
            '/api/pulls/list/new', cursor=None, cache=False
        )
        self.assertEqual(len(results), 5)
        for pull in results:
            self.assertTrue('issue_id' in pull)

    def pull_new_test(self):
        self.app.setup()
        self.app.google._http = HttpMockSequence([
            ({'status': 500}, "500 Server Error"),
            ({'status': 200},
             '{"status": 200, "results": {"failed": ["1000"]}}'),
            ({'status': 200},
             '{"status": 200, "results": {"updated": ["1000"]}}'),
        ])
        # The following calls should not trigger a refresh
        self.app.pulldb.refresh_pull = mock.Mock(side_effect=AssertionError)
        with self.assertRaises(UpdateError):
            self.app.pulldb.pull_new(1000)
        self.app.pulldb.pull_new(1000)
        self.app.pulldb.refresh_pull = mock.Mock()
        self.app.pulldb.pull_new(1000)
        self.app.pulldb.refresh_pull.assert_called_once_with(1000)

    def pull_new_arg_test(self):
        self.app.setup()
        self.app.pulldb.refresh_pull = mock.Mock(return_value=[])
        http_mock = mock.Mock()
        http_mock.request = mock.Mock(
            side_effect=HttpMock(datafile('pull_update_pull_1000.json'),
                                 headers={'status': 200}).request)
        self.app.google._http = http_mock
        with self.assertRaises(TypeError):
            self.app.pulldb.pull_new(None)
        self.app.pulldb.pull_new(1000)
        self.app.pulldb.refresh_pull.assert_called_with(1000)
        request_args = self.app.google._http.request.call_args
        print list(request_args)
        data = json.loads(request_args[1]['body'])
        self.assertEqual(data['pull'][0], "1000")
