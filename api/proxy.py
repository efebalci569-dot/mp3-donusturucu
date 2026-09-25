import os

import httpx
from flask import Flask, Response, jsonify, request

app = Flask(__name__)

BACKEND_URL = os.environ.get('BACKEND_URL', '').rstrip('/')

HOP_BY_HOP = {
    'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
    'te', 'trailers', 'transfer-encoding', 'upgrade', 'host',
    'content-encoding', 'content-length',
}

client = None
download_client = None


def get_client():
    global client
    if client is None:
        client = httpx.Client(
            base_url=BACKEND_URL,
            # Vercel Hobby'de fonksiyon ~10sn'de kesilir; poll akışı hızlı olmalı
            timeout=httpx.Timeout(25.0, connect=10.0),
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=5)
        )
    return client


def get_download_client():
    global download_client
    if download_client is None:
        download_client = httpx.Client(
            base_url=BACKEND_URL,
            timeout=httpx.Timeout(55.0, connect=10.0),
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=5)
        )
    return download_client


@app.route('/', defaults={'path': ''},
           methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
@app.route('/<path:path>',
           methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
def proxy(path):
    if not BACKEND_URL:
        return jsonify({
            'success': False,
            'error': 'BACKEND_URL environment variable ayarlanmamış'
        }), 500

    rewritten = request.args.get('path')
    if rewritten:
        target_path = '/api/' + rewritten.lstrip('/')
    else:
        target_path = '/' + path if path else '/'
    params = {k: v for k, v in request.args.items() if k != 'path'}

    req_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in HOP_BY_HOP and k.lower() != 'x-vercel-forwarded-*'.lower()
    }

    try:
        # /api/download/* büyük dosya taşır -> uzun timeout; diğerleri (convert/status) kısa
        http_client = get_download_client() if target_path.startswith('/api/download') else get_client()
        resp = http_client.request(
            method=request.method,
            url=target_path,
            params=params,
            content=request.get_data(),
            headers=req_headers
        )
    except httpx.TimeoutException:
        return jsonify({'success': False,
                        'error': 'Backend zaman aşımına uğradı'}), 504
    except httpx.HTTPError:
        return jsonify({'success': False,
                        'error': 'Backend sunucusuna ulaşılamıyor'}), 502

    resp_headers = {
        k: v for k, v in resp.headers.items()
        if k.lower() not in HOP_BY_HOP
    }
    return Response(resp.content, status=resp.status_code,
                    headers=resp_headers)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '9000'))
    app.run(debug=False, host='0.0.0.0', port=port)
