"""Public account fields only; provider secrets and password hashes stay private."""
import hashlib
import re


def account_view(account):
    username = account['username']
    email = (account.get('email') or username).strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        email = ''
    avatar = ('https://www.gravatar.com/avatar/' + hashlib.sha256(email.encode()).hexdigest() + '?s=96&d=404&r=g') if email else None
    return {'id': account['id'], 'username': username, 'name': account.get('name') or username,
            'email': email or None, 'avatar_url': avatar,
            'platform_admin': account['id'] == 'local_admin' and bool(account.get('admin'))}
