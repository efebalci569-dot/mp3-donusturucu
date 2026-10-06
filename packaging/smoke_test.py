"""Paketlenmiş uygulamayı --smoke-test ile çalıştırır (CI ve yerel kontrol için).

Kullanım: python packaging/smoke_test.py <çalıştırılabilir dosya>
"""
import os
import subprocess
import sys


def main(exe):
    # Windows CreateProcess "dist/..." gibi eğik çizgili göreli yolu bulamıyor.
    exe = os.path.abspath(exe)
    try:
        code = subprocess.run([exe, '--smoke-test'], timeout=180).returncode
    except subprocess.TimeoutExpired:
        code = 'zaman aşımı'
    if code == 0:
        print('SMOKE OK')
        return 0
    print(f'SMOKE FAIL ({code})')
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
