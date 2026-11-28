"""test_k3s.py -- mm-api in k3s (k3s/): the scripts parse; the manifest has the image of the nodes, its password from a
Secret (never in the repo), no wallet, the port 8300 outside, no token of Kubernetes; myDATA sent by one mm-api at a
time (the turn of MyData). Runs everywhere.

    python3 -m pytest -q tests/test_k3s.py
"""
import os
import re
import subprocess

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


def text(*p):
    with open(os.path.join(ROOT, *p), encoding='utf-8') as f:
        return f.read()


def test_the_scripts_parse():
    for f in ('ship.sh', 'deploy.sh'):
        subprocess.run(['bash', '-n', os.path.join(ROOT, 'k3s', f)], check=True)


def test_the_manifest():
    y = text('k3s', 'mm-api.yaml')
    assert 'image: localhost/mm/mm-api:@TAG@' in y and 'imagePullPolicy: IfNotPresent' in y
    assert 'replicas: 2' in y and 'kind: PodDisruptionBudget' in y and 'automountServiceAccountToken: false' in y
    assert 'secretKeyRef:' in y and 'name: mm-db' in y and 'value: "@DB_URL@"' in y
    assert 'name: MM_TNS_ADMIN\n              value: ""' in y, 'no wallet in the cluster'
    assert 'type: LoadBalancer' in y and 'port: 8300' in y and 'targetPort: 8090' in y
    assert 'secretName: mm-mydata' in y and 'optional: true' in y
    assert not re.search(r'(?i)password:\s*\S', y.replace('key: password', ''))


def test_deploy_asks_the_password():
    d = text('k3s', 'deploy.sh')
    assert 'read -rsp' in d and '--from-file=password=/dev/stdin' in d and 'SERVICE_NAME=mm_rw' in d
    assert '192.168.178.221' in d and '192.168.178.222' in d and 'shred -u' in d
    s = text('k3s', 'ship.sh')
    assert 'k3s ctr images import' in s and 'docker save' in s and './mvnw' in s


def test_mydata_one_sender_at_a_time():
    m = text('api', 'src', 'main', 'java', 'mm', 'api', 'MyData.java')
    assert "for update skip locked" in m and 'MYDATA_SENDER' in m and 'static boolean takeTurn' in m
    main = text('api', 'src', 'main', 'java', 'mm', 'api', 'Main.java')
    assert 'MyData.takeTurn(turn)' in main and 'turn.rollback()' in main
