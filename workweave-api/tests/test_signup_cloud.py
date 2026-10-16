import os
from urllib.parse import urlsplit, unquote
import httpx
import pytest
from workweave_api.identity import account_view
from pydantic import SecretStr
from workweave_api.config import Settings
from workweave_api.main import create_app
from workweave_api.store import Store, uid


def test_public_account_photo_normalization_and_secret_exclusion():
    import hashlib
    account = {'id': 'user_test', 'username': ' Person@Example.COM ', 'password_hash': 'private-hash', 'google_sub': 'private-subject', 'admin': True}
    view = account_view(account)
    assert view['email'] == 'person@example.com'
    assert hashlib.sha256(b'person@example.com').hexdigest() in view['avatar_url']
    assert view['avatar_url'].endswith('?s=96&d=404&r=g')
    assert view['platform_admin'] is False
    assert not {'password_hash', 'google_sub', 'admin'} & view.keys()
    assert account_view({'id': 'user_name', 'username': 'username_only'})['avatar_url'] is None


def test_cloud_credentials_are_encoded_and_connection_info_is_safe():
    config = Settings(_env_file=None, graph_host='example.invalid', graph_port=6380,
                      graph_username='test-user', graph_password=SecretStr('test-only:p@ss/#?%'), graph_tls=True)
    parsed = urlsplit(config.graph_connection_url)
    assert parsed.scheme == 'rediss' and parsed.hostname == 'example.invalid' and parsed.port == 6380
    assert unquote(parsed.password) == 'test-only:p@ss/#?%'
    assert config.graph_connection_info == {'mode': 'remote', 'tls': True}
    assert 'test-only:p@ss' not in repr(config)
    local = Settings(_env_file=None, graph_host='', graph_url='redis://localhost:16380')
    assert local.graph_connection_info == {'mode': 'local', 'tls': False}


def test_password_file_preserves_environment_like_characters(tmp_path):
    secret = tmp_path / 'password.txt'
    test_password = 'test-only:${UNSET_VALUE}:p@ss/"\\'
    secret.write_text(test_password, encoding='utf-8')
    config = Settings(_env_file=None, graph_host='example.invalid', graph_username='test-user', graph_password_file=secret)
    assert unquote(urlsplit(config.graph_connection_url).password) == test_password


@pytest.mark.asyncio
async def test_signup_cannot_change_runtime_secrets_and_setup_persists(tmp_path):
    config = Settings(_env_file=None, graph_host='', graph_url=os.environ.get('WORKWEAVE_TEST_GRAPH_URL', 'redis://localhost:16380'),
                      ollama_url='http://localhost:1', data_dir=tmp_path, allowed_hosts=['local.test'],
                      admin_password='test-bootstrap-password-only', groq_key='', gemini_key='')
    app = create_app(config)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://local.test') as first:
            result = await first.post('/api/v1/auth/signup', json={'username': uid('signup'), 'password': 'test-password-12345', 'company_name': 'Setup test', 'industry': 'Logistics'})
            assert result.status_code == 200, result.text
            created = result.json()
            base = '/api/v1/companies/' + created['company_id']
            control = Store(app.state.graph, 'ww_control')
            assert (await control.get('user', created['id']))['admin'] is False
            assert (await first.get('/api/v1/auth/me')).json()['platform_admin'] is False
            denied = await first.put(base + '/providers/groq/key', json={'key': 'test-only-key-never-saved'})
            assert denied.status_code == 403
            assert (await first.put(base + '/providers/ollama_cloud/key', json={'key': 'test-only-key-never-saved'})).status_code == 403
            assert app.state.router.vault.read() == {}
            cloud_policy = {'allowed': ['ollama_cloud'], 'cloud_consent': True, 'local_only': False}
            app_default = {'allowed': ['ollama_cloud', 'groq', 'gemini', 'ollama'], 'cloud_consent': True, 'local_only': False}
            assert (await first.get(base + '/providers')).json()['policy'] == app_default
            # Older workspaces with no stored preference inherit the app-wide
            # default in Settings, just as generation does.
            company = await control.get('company', created['company_id'])
            company.pop('provider_policy')
            await control.put('company', company)
            assert (await first.get(base + '/providers')).json()['policy'] == app_default
            legacy_policy = {'allowed': ['groq', 'gemini', 'ollama'], 'cloud_consent': False, 'local_only': False}
            assert (await first.put(base + '/providers/policy', json=legacy_policy)).status_code == 200
            assert (await first.get(base + '/providers')).json()['policy'] == legacy_policy
            assert (await first.put(base + '/providers/policy', json={**cloud_policy, 'local_only': True})).status_code == 422
            assert (await first.get(base + '/providers')).json()['policy'] == legacy_policy
            assert (await first.put(base + '/providers/policy', json=cloud_policy)).status_code == 200
            assert (await first.get(base + '/providers')).json()['policy'] == cloud_policy
            # Legacy users with an old admin flag also cannot change platform secrets.
            account = await control.get('user', created['id'])
            account['admin'] = True
            await control.put('user', account)
            assert (await first.put(base + '/providers/groq/key', json={'key': 'test-only-key-never-saved'})).status_code == 403
            csv = b'id,name,owner\nR1,Customer commitment,Operations\n'
            uploaded = await first.post(base + '/sources/upload', files={'file': ('records.csv', csv, 'text/csv')})
            assert uploaded.status_code == 200, uploaded.text
            preview = uploaded.json()
            pending = (await first.get(base + '/imports')).json()
            assert preview['id'] in {p['id'] for p in pending}
            confirmed = await first.post(base + '/imports/' + preview['id'] + '/confirm', json={'mappings': [t['suggested_mapping'] for t in preview['tables']]})
            assert confirmed.status_code == 200, confirmed.text
            assert preview['id'] not in {p['id'] for p in (await first.get(base + '/imports')).json()}
            assert len((await first.get(base + '/sources')).json()) == 1
            profile = {'description': 'We deliver customer commitments.', 'industry': 'Logistics', 'responsibilities': 'Operations owns delivery.', 'procedure': '', 'confirmed': True, 'onboarding_step': 'complete'}
            assert (await first.put(base + '/profile', json=profile)).status_code == 200
            persisted = (await first.get(base + '/profile')).json()
            assert persisted['confirmed'] is True and persisted['onboarding_step'] == 'complete' and persisted['industry'] == 'Logistics'
            ready = (await first.get('/api/v1/system/readiness')).json()
            assert ready['database']['status'] == 'connected' and ready['platform_admin'] is False
            assert 'password' not in ready['database'] and 'username' not in ready['database']
            async with httpx.AsyncClient(transport=transport, base_url='http://local.test') as second:
                other = await second.post('/api/v1/auth/signup', json={'username': uid('outsider'), 'password': 'test-password-12345', 'company_name': 'Isolated company'})
                assert other.status_code == 200
                assert (await second.get(base + '/sources')).status_code == 404
                assert (await second.get(base + '/imports')).status_code == 404
                assert (await second.put(base + '/profile', json=profile)).status_code == 404
            await first.post('/api/v1/auth/logout')
            assert (await first.get('/api/v1/system/readiness')).status_code == 401


@pytest.mark.asyncio
async def test_unconfigured_google_is_not_advertised(tmp_path):
    config = Settings(_env_file=None, graph_host='', graph_url=os.environ.get('WORKWEAVE_TEST_GRAPH_URL', 'redis://localhost:16380'), data_dir=tmp_path,
                      allowed_hosts=['local.test'], allow_private_drive=False, google_client_id='', google_client_secret='')
    app = create_app(config)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://local.test') as client:
        assert (await client.get('/api/v1/auth/options')).json() == {'google': False}
        assert (await client.get('/api/v1/auth/google/url')).status_code == 409
    await app.state.router.close()
    await app.state.graph.close()


@pytest.mark.asyncio
async def test_frontend_origin_allowlist_does_not_trust_forwarded_headers(tmp_path):
    config = Settings(_env_file=None, data_dir=tmp_path, allowed_hosts=['api.test'],
                      allowed_origins=['https://web.test'], allow_private_drive=False,
                      google_client_id='', google_client_secret='')
    app = create_app(config)
    # No lifespan or database is needed: POST to a GET-only endpoint returns
    # 405. A disallowed Origin must be rejected first, with 403.
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://api.test') as client:
        for origin, expected in [('https://web.test', 405), ('https://evil.test', 403),
                                 ('https://web.test.evil.test', 403), ('http://web.test', 403),
                                 ('null', 403), ('https://api.test', 405)]:
            response = await client.post('/api/v1/auth/google/url', headers={
                'Origin': origin, 'X-Forwarded-Host': 'web.test', 'X-Forwarded-Proto': 'https'})
            assert response.status_code == expected, response.text
    await app.state.router.close()
    await app.state.graph.close()
