"""Save FalkorDB connection fields locally without putting passwords in commands."""
import getpass
import json
import os
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    destination = root / '.env'
    host = input('FalkorDB host (hostname only): ').strip()
    if not host or any(character in host for character in '/@?#\r\n'):
        raise SystemExit('Enter the hostname from the instance Connectivity tab, without a URL or password.')
    try:
        port = int(input('Port [6379]: ').strip() or '6379')
        if not 1 <= port <= 65535:
            raise ValueError()
    except ValueError:
        raise SystemExit('Port must be an integer between 1 and 65535.')
    username = input('Database username (blank if your instance does not require one): ').strip()
    password = getpass.getpass('Database password (hidden): ')
    if not password:
        raise SystemExit('No password entered. Configuration was not changed.')
    tls_answer = input('Does this instance support TLS? [Y/n]: ').strip().lower()
    if tls_answer not in ('', 'y', 'yes', 'n', 'no'):
        raise SystemExit('Answer yes or no according to the instance connection settings.')
    tls = tls_answer not in ('n', 'no')
    if not tls:
        print('This connection is unencrypted. Use disposable synthetic data until you have a protected connection.')
    password_file = root / '.workweave' / 'falkordb-password.txt'
    values = {'WORKWEAVE_GRAPH_HOST': host, 'WORKWEAVE_GRAPH_PORT': str(port),
              'WORKWEAVE_GRAPH_USERNAME': username, 'WORKWEAVE_GRAPH_PASSWORD': '',
              'WORKWEAVE_GRAPH_PASSWORD_FILE': password_file.resolve().as_posix(),
              'WORKWEAVE_GRAPH_PASSWORD_FILE_HOST': password_file.resolve().as_posix(),
              'WORKWEAVE_GRAPH_TLS': 'true' if tls else 'false'}
    if any('\n' in value or '\r' in value for value in [*values.values(), password]):
        raise SystemExit('Connection fields must be single-line values.')
    password_file.parent.mkdir(parents=True, exist_ok=True)
    secret_temporary = password_file.with_suffix('.tmp')
    secret_temporary.write_text(password, encoding='utf-8')
    os.chmod(secret_temporary, 0o600)
    secret_temporary.replace(password_file)
    source = destination.read_text(encoding='utf-8') if destination.exists() else (root / '.env.example').read_text(encoding='utf-8')
    lines = source.splitlines()
    written = set()
    output = []
    for line in lines:
        key = line.split('=', 1)[0].strip()
        if key in values:
            if key not in written:
                output.append(key + '=' + json.dumps(values[key], ensure_ascii=False))
                written.add(key)
        else:
            output.append(line)
    output.extend(key + '=' + json.dumps(value, ensure_ascii=False) for key, value in values.items() if key not in written)
    temporary = destination.with_suffix('.env.tmp')
    temporary.write_text('\n'.join(output) + '\n', encoding='utf-8')
    os.chmod(temporary, 0o600)
    temporary.replace(destination)
    print('Connection saved in .env; password saved in the ignored .workweave secret file. Password was not printed.')
    print('Start: docker compose -f docker-compose.cloud.yml -f docker-compose.cloud-secrets.yml up -d --build')
    print('Check: docker compose -f docker-compose.cloud.yml -f docker-compose.cloud-secrets.yml exec api python -m workweave_api.check_connection')


if __name__ == '__main__':
    main()
