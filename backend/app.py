import os
from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS

import converter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'frontend'))

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 64 * 1024

cors_origins = os.environ.get('CORS_ORIGINS', '*')
if cors_origins.strip() == '*':
    CORS(app)
else:
    CORS(app, origins=[o.strip() for o in cors_origins.split(',') if o.strip()])

converter.start_janitor()


@app.route('/')
def index():
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.route('/<path:asset>')
def frontend_asset(asset):
    return send_from_directory(FRONTEND_DIR, asset)


@app.route('/api/health')
def health():
    ffmpeg = converter.resolve_ffmpeg()
    return jsonify({
        'status': 'ok',
        'ffmpeg': bool(ffmpeg),
        'max_jobs': converter.MAX_CONCURRENT_JOBS
    })


@app.route('/api/debug')
def debug():
    info = converter.debug_info()
    info['status'] = 'ok'
    return jsonify(info)


@app.route('/api/convert', methods=['POST'])
def convert():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'success': False, 'error': 'Geçersiz istek'}), 400

    url = str(data.get('url', '')).strip()
    if not url:
        return jsonify({'success': False, 'error': 'Lütfen bir YouTube linki girin'}), 400

    if not converter.validate_url(url):
        return jsonify({'success': False,
                        'error': 'Geçerli bir YouTube linki girin (youtube.com veya youtu.be)'}), 400

    job = converter.start_job(url)
    print(f'[api] convert start url={url[:80]} job={job["id"]}', flush=True)
    return jsonify({'success': True, 'job_id': job['id']}), 202


@app.route('/api/status/<job_id>')
def status(job_id):
    job = converter.get_job(job_id)
    if not job:
        return jsonify({'success': False, 'error': 'İş bulunamadı veya süresi doldu'}), 404
    return jsonify({
        'success': True,
        'status': job['status'],
        'progress': job['progress'],
        'title': job['title'],
        'size_mb': job['size_mb'],
        'filename': job['filename'],
        'error': job['error']
    })


@app.route('/api/download/<job_id>')
def download(job_id):
    path, filename = converter.build_download_response_path(job_id)
    if not path or not os.path.exists(path):
        return jsonify({'success': False, 'error': 'Dosya bulunamadı veya süresi doldu'}), 404
    return send_file(path, as_attachment=True, download_name=filename,
                     mimetype='audio/mpeg', conditional=False)


@app.errorhandler(404)
def not_found(_e):
    return jsonify({'success': False, 'error': 'Sayfa bulunamadı'}), 404


@app.errorhandler(500)
def server_error(_e):
    return jsonify({'success': False, 'error': 'Sunucu hatası'}), 500


port = int(os.environ.get('PORT', '8000'))

if __name__ == '__main__':
    print(f'MP3 DÖNÜŞTÜRÜCÜM backend başlatıldı -> http://127.0.0.1:{port}')
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True)
