"""Local-only, single-user medical volume viewer and frozen Cox calculator."""
import argparse
import io
import json
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

import numpy as np
import SimpleITK as sitk
from PIL import Image
from predictor import predict

ROOT = Path(__file__).resolve().parent
TOKEN = secrets.token_urlsafe(32)
LOCK = threading.RLock()
VOLUMES = {}
MAX_UPLOAD = 200 * 1024 * 1024
MAX_VOXELS = 64_000_000
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_SEQUENCES = 12

def load_volume(path):
    reader = sitk.ImageFileReader()
    reader.SetFileName(str(path))
    reader.ReadImageInformation()
    if reader.GetDimension() != 3 or reader.GetNumberOfComponents() != 1:
        raise ValueError('Only 3D scalar volumes are supported. Convert 4D or vector images first.')
    if np.prod(reader.GetSize(), dtype=np.int64) > MAX_VOXELS:
        raise ValueError('The volume exceeds 64 million voxels. Crop or downsample it first.')
    image = sitk.DICOMOrient(reader.Execute(), 'LPS')
    arr = sitk.GetArrayFromImage(image).astype(np.float32)
    sample = arr.ravel()[::max(1, arr.size // 200000)]
    finite = sample[np.isfinite(sample)]
    if not len(finite):
        raise ValueError('The image has no valid intensity values.')
    lo, hi = np.percentile(finite, [1, 99])
    if hi <= lo:
        hi = lo + 1
    direction = np.array(image.GetDirection()).reshape(3, 3)
    oblique = not np.allclose(direction, np.eye(3), atol=1e-3)
    meta = {'size': list(image.GetSize()), 'spacing': list(image.GetSpacing()),
            'window': float(hi-lo), 'level': float((hi+lo)/2), 'oblique': oblique,
            'orientation': 'LPS', 'id': secrets.token_hex(12)}
    return arr, meta

def slice_png(volume, plane, index, width, level):
    arr, meta = volume
    sx, sy, sz = meta['spacing']
    if plane == 'axial':
        slab, spacing = arr[index, :, :], (sx, sy)
    elif plane == 'coronal':
        slab, spacing = arr[:, index, :][::-1, :], (sx, sz)
    else:
        slab, spacing = arr[:, :, index][::-1, :], (sy, sz)
    pixels = np.nan_to_num((slab - (level-width/2)) / width, nan=0, posinf=1, neginf=0)
    im = Image.fromarray((np.clip(pixels, 0, 1)*255).astype(np.uint8))
    physical = (im.width*spacing[0], im.height*spacing[1])
    scale = min(1/min(spacing), 1200/max(physical))
    im = im.resize(tuple(max(1, round(x*scale)) for x in physical), Image.Resampling.BILINEAR)
    output = io.BytesIO()
    im.save(output, 'PNG')
    return output.getvalue()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Do not log image names or patient inputs.

    def send(self, body, status=200, content_type='application/json; charset=utf-8'):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        host = self.headers.get('Host', '')
        valid_host = host in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')
        return valid_host and secrets.compare_digest(self.headers.get('X-Local-Token', ''), TOKEN)

    def do_GET(self):
        parsed = urlparse(self.path)
        if self.headers.get('Host') not in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'):
            return self.send({'error': 'Host rejected'}, 403)
        if parsed.path == '/api/config':
            return self.send({'token': TOKEN, 'version': 'multi-sequence-1'})
        if parsed.path == '/api/volumes':
            if not self.authorized():
                return self.send({'error': 'Forbidden'}, 403)
            with LOCK:
                return self.send([volume[1] for volume in VOLUMES.values()])
        if parsed.path == '/api/slice':
            if not self.authorized():
                return self.send({'error': 'Forbidden'}, 403)
            try:
                q = parse_qs(parsed.query)
                plane = q['plane'][0]
                if plane not in ('axial','coronal','sagittal'):
                    raise ValueError('Invalid viewing plane.')
                with LOCK:
                    volume = VOLUMES.get(q.get('id', [''])[0])
                if volume is None:
                    raise ValueError('Please reload the image.')
                i = int(q['index'][0]); axis = {'axial':2,'coronal':1,'sagittal':0}[plane]
                if not 0 <= i < volume[1]['size'][axis]:
                    raise ValueError('Slice index is out of range.')
                width, level = float(q['width'][0]), float(q['level'][0])
                if not np.isfinite(width) or not np.isfinite(level) or width <= 0:
                    raise ValueError('Invalid window width or level.')
                return self.send(slice_png(volume,plane,i,width,level), content_type='image/png')
            except (ValueError, KeyError):
                return self.send({'error': 'Unable to read the slice.'}, 400)
        names = {'/':'index.html','/app.js':'app.js','/style.css':'style.css'}
        if parsed.path in names:
            name = names[parsed.path]
            mime = {'html':'text/html; charset=utf-8','js':'text/javascript; charset=utf-8','css':'text/css; charset=utf-8'}[name.split('.')[-1]]
            return self.send((ROOT/'static'/name).read_bytes(), content_type=mime)
        self.send({'error':'Not found'},404)

    def do_POST(self):
        if not self.authorized():
            return self.send({'error':'Forbidden'},403)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            limit = MAX_UPLOAD + 65536 if self.path == '/api/upload' else 16000
            if not 0 < length <= limit:
                return self.send({'error':'The request is empty or too large. Images must not exceed 200 MB.'},413)
            raw = self.rfile.read(length)
            if self.path == '/api/predict':
                values = json.loads(raw)
                if not isinstance(values, dict):
                    raise ValueError('Invalid input format.')
                return self.send(predict(values))
            if self.path == '/api/clear':
                with LOCK:
                    VOLUMES.clear()
                return self.send({'ok':True})
            if self.path != '/api/upload':
                return self.send({'error':'Not found'},404)
            ctype = self.headers.get('Content-Type', '')
            if not ctype.startswith('multipart/form-data;') or '\r' in ctype or '\n' in ctype:
                raise ValueError('Invalid upload format.')
            message = BytesParser(policy=default).parsebytes(('Content-Type: '+ctype+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+raw)
            parts = [p for p in message.iter_parts() if p.get_param('name', header='content-disposition')=='file']
            if len(parts) != 1:
                raise ValueError('Upload one image at a time.')
            name = (parts[0].get_filename() or '').lower()
            ext = next((x for x in ('.nii.gz','.nii','.nrrd') if name.endswith(x)), None)
            if ext is None:
                raise ValueError('Only .nii, .nii.gz, and .nrrd files are supported.')
            payload = parts[0].get_payload(decode=True)
            if not payload or len(payload) > MAX_UPLOAD:
                raise ValueError('Each image must be nonempty and no larger than 200 MB.')
            if ext == '.nrrd':
                header = payload[:65536].split(b'\n\n')[0].split(b'\r\n\r\n')[0].lower()
                if b'data file:' in header or b'datafile:' in header:
                    raise ValueError('Only self-contained NRRD files are supported. External data references are not accepted.')
            with tempfile.TemporaryDirectory(prefix='oai_viewer_') as tmp:
                path = Path(tmp)/('image'+ext)
                path.write_bytes(payload)
                volume = load_volume(path)
            with LOCK:
                if len(VOLUMES) >= MAX_SEQUENCES:
                    raise ValueError('At most 12 sequences can be loaded. Clear images before adding more.')
                if sum(item[0].nbytes for item in VOLUMES.values()) + volume[0].nbytes > MAX_TOTAL_BYTES:
                    raise ValueError('Loaded images exceed the 512 MB memory limit. Clear images before adding more.')
                volume[1]['name'] = (parts[0].get_filename() or 'MRI volume').replace('\\', '/').split('/')[-1]
                VOLUMES[volume[1]['id']] = volume
            return self.send(volume[1])
        except ValueError as error:
            return self.send({'error': str(error) or 'Invalid input or file format.'},400)
        except TypeError:
            return self.send({'error':'Invalid input or file format. Check the age, scores, and image.'},400)
        except RuntimeError:
            return self.send({'error':'Image loading failed. Check that the file is complete.'},400)

def open_browser(url):
    """Use the macOS URL launcher, which is reliable from Finder/Terminal."""
    try:
        if sys.platform == 'darwin':
            completed = subprocess.run(['/usr/bin/open', url], timeout=10, check=False)
            if completed.returncode == 0:
                return True
        if webbrowser.open(url, new=2):
            return True
    except (OSError, subprocess.TimeoutExpired, webbrowser.Error):
        pass
    print(f'Unable to open the browser automatically. Open this address: {url}', flush=True)
    return False

def existing_app(url):
    """Recognize our running app before reusing an occupied port."""
    try:
        with urlopen(url + '/api/config', timeout=2) as response:
            config = json.loads(response.read(4096))
        with urlopen(url + '/', timeout=2) as response:
            page = response.read(16384).decode('utf-8')
        return isinstance(config, dict) and isinstance(config.get('token'), str) and 'Knee Risk Studio</title>' in page
    except (OSError, ValueError, UnicodeDecodeError):
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    url = f'http://127.0.0.1:{args.port}'
    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    except OSError:
        if existing_app(url):
            print(f'OAI Knee Risk is already running at: {url}', flush=True)
            if not args.no_browser:
                open_browser(url)
        else:
            print('Port in use by another service. Use --port 8766.', flush=True)
        return
    server.daemon_threads = True
    url = f'http://127.0.0.1:{server.server_port}'
    print(f'OAI Knee Risk is running at: {url}\nLocal access only. Close this window or press Ctrl+C to stop.', flush=True)
    if not args.no_browser:
        launch = threading.Timer(0.8, open_browser, args=(url,))
        launch.daemon = True
        launch.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
