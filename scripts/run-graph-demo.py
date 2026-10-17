"""Create a fresh synthetic Harbor Supply workspace through the real API."""
import argparse
import getpass
import http.cookiejar
import json
import time
import urllib.error
import urllib.parse
import urllib.request


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://localhost:8080', help='Workweave frontend origin')
    parser.add_argument('--username', help='Your existing Workweave email or username')
    args = parser.parse_args(argv)
    origin = args.url.rstrip('/')
    parsed = urllib.parse.urlsplit(origin)
    if parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment or not parsed.hostname:
        parser.error('--url must be an origin, without credentials, a path, or a query')
    if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in {'localhost', '127.0.0.1'}):
        parser.error('Use HTTPS, or HTTP on localhost for local development')
    username = args.username or input('Workweave email or username: ').strip()
    password = getpass.getpass('Workweave account password (hidden): ')
    client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def api(path, body=None):
        request = urllib.request.Request(origin + '/api/v1' + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Content-Type': 'application/json', 'Origin': origin})
        with client.open(request, timeout=180) as response:
            return json.load(response)

    logged_in = False
    try:
        api('/auth/login', {'username': username, 'password': password})
        logged_in = True
        company = api('/companies', {'name': 'Harbor Supply demo ' + time.strftime('%H-%M-%S')})
        base = '/companies/' + company['id']
        print('Created a separate synthetic workspace: ' + company['name'])
        job = api(base + '/demo', {})
        if not job.get('runs'):
            raise RuntimeError('The demo import did not produce an investigation')
        run_id = job['runs'][0]['id']
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            run = api(base + '/runs/' + run_id)
            if run['status'] in {'completed', 'blocked'}:
                break
            time.sleep(1)
        else:
            raise RuntimeError('Investigation still running; inspect it in Home')
        if run['status'] != 'completed':
            raise RuntimeError('Investigation needs attention; inspect it in Home')
        affected = {finding['entity_id'] for finding in run['findings']}
        if affected != {'SalesOrder:SO1', 'SalesOrder:SO2'}:
            raise RuntimeError('Unexpected affected commitments; inspect the saved investigation')
        tasks = [task for task in api(base + '/tasks') if task['run_id'] == run_id]
        if len(tasks) != 2:
            raise RuntimeError('Expected two internal review tasks')
        review = run.get('impact_review', {})
        if {item['entity_id'] for item in review.get('excluded', [])} != {'SalesOrder:SO3', 'SalesOrder:SO4'}:
            raise RuntimeError('Expected date and stock exclusions for SO3 and SO4')
        print('Verified: SO1/SO2 affected; SO3/SO4 excluded with evidence; SO5 outside the assessed paths; two review tasks saved.')
        print('Open your workspace menu in the browser, choose this company, and inspect Home.')
        print('This is a real deterministic graph workflow; it does not simulate an LLM response.')
    finally:
        if logged_in:
            try:
                api('/auth/logout', {})
            except (urllib.error.URLError, TimeoutError):
                pass


if __name__ == '__main__':
    try:
        main()
    except urllib.error.HTTPError as error:
        raise SystemExit('API request failed (HTTP ' + str(error.code) + '). Check your login and app connection.')
    except (urllib.error.URLError, TimeoutError, RuntimeError) as error:
        raise SystemExit(str(error))
