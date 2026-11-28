"""Change the dev password in index.html.

    python3 tools/set_dev_password.py "my new password"

Only a SHA-256 hash is stored in the file, never the password. Devices already unlocked
with the old password go back to normal-player mode until you unlock them again.
Note: this keeps friends out of the dev tools; it is not real security, since anyone
can edit their own copy of a web page.
"""
import hashlib, os, re, sys

if len(sys.argv) != 2 or len(sys.argv[1]) < 6:
    sys.exit('usage: set_dev_password.py "new password" (6+ characters)')
path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'index.html')
src = open(path, encoding='utf-8').read()
h = hashlib.sha256(('paperland-dev:' + sys.argv[1]).encode()).hexdigest()
new, n = re.subn(r"const DEV_HASH='[0-9a-f]{64}';", f"const DEV_HASH='{h}';", src)
if n != 1:
    sys.exit('DEV_HASH line not found')
open(path, 'w', encoding='utf-8').write(new)
print('Dev password changed.')
