import logging
import os

from flask import Flask, jsonify, request, send_file, send_from_directory

import converter
from paths import APP_ID, resource_dir
from version import __version__

log = logging.getLogger('mp3.app')

NOT_READY_MSG = 'Uygulama hâlâ hazırlanıyor, birazdan tekrar dene.'


def create_app(port, setup, lifecycle, retry_setup, update_info):
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 64 * 1024
    frontend_dir = str(resource_dir() / 'frontend')
    allowed_hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}

    @app.before_request
    def check_host():
        # DNS rebinding'e karşı: yalnızca kendi adresimizden gelen istekler.
        if request.host not in allowed_hosts:
            return jsonify({'success': False, 'error': 'Yasak'}), 403

    @app.route('/')
    def index():
        return send_from_directory(frontend_dir, 'index.html')

    @app.route('/<path:asset>')
    def frontend_asset(asset):
        return send_from_directory(frontend_dir, asset)

    @app.route('/api/health')
    def health():
        return jsonify({'status': 'ok', 'app': APP_ID, 'version': __version__})

    @app.route('/api/setup')
    def setup_status():
        data = setup.to_dict()
        data['update'] = update_info()
        return jsonify(data)

    @app.route('/api/setup/retry', methods=['POST'])
    def setup_retry():
        retry_setup()
        return jsonify({'success': True}), 202

    @app.route('/api/heartbeat', methods=['POST'])
    def heartbeat():
        lifecycle.heartbeat()
        return '', 204

    @app.route('/api/convert', methods=['POST'])
    def convert():
        if not setup.ready:
            return jsonify({'success': False, 'error': NOT_READY_MSG}), 503
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
        log.info('convert start job=%s', job['id'])
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
            'error': job['error'],
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

    return app
