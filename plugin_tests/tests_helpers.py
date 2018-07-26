
import httmock
import re
import os

GOOD_REPO = 'whole-tale/jupyter-base'
GOOD_COMMIT = 'b45f9a57'
GOOD_CHILD = '4b35fe6'
XPRA_REPO = 'whole-tale/xpra-base'
XPRA_COMMIT = 'fad88f5'


@httmock.urlmatch(scheme='https', netloc='^api\.github\.com$',
                  path='^/repos/([\w\-]+)/([\w\-]+)$', method='GET')
def mockReposRequest(url, request):
    owner, repo = re.match(
        '^/repos/([\w\-]+)/([\w\-]+)$', url.path).groups()
    repo_slug = os.path.join(owner, repo)
    headers = {'content-type': 'application/json'}
    if repo_slug == GOOD_REPO:
        return httmock.response(
            200, {'full_url': repo_slug}, headers, None, 5, request)
    elif repo_slug == XPRA_REPO:
        return httmock.response(
            200, {'full_url': repo_slug}, headers, None, 5, request)

    content = {u'documentation_url': u'https://developer.github.com/v3',
               u'message': u'Not Found'}
    return httmock.response(404, content, headers, None, 5, request)


@httmock.urlmatch(scheme='https', netloc='^api\.github\.com$',
                  path='^/repos/([\w\-]+)/([\w\-]+)/commits/(\w+)$',
                  method='GET')
def mockCommitRequest(url, request):
    owner, repo, commit = re.match(
        '^/repos/([\w\-]+)/([\w\-]+)/commits/(\w+)$',
        url.path).groups()
    headers = {'content-type': 'application/json'}
    if commit == GOOD_COMMIT:
        return httmock.response(
            200, {'sha': GOOD_COMMIT}, headers, None, 5, request)
    elif commit == GOOD_CHILD:
        return httmock.response(
            200, {'sha': GOOD_CHILD}, headers, None, 5, request)
    elif commit == XPRA_COMMIT:
        return httmock.response(
            200, {'sha': XPRA_COMMIT}, headers, None, 5, request)

    content = {u'documentation_url': u'https://developer.github.com/v3',
               u'message': u'Not Found'}
    return httmock.response(404, content, headers, None, 5, request)


@httmock.all_requests
def mockOtherRequest(url, request):
    raise Exception('Unexpected url %s' % str(request.url))
