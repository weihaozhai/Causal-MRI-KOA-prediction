import io
import json
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.request
import urllib.error
from pathlib import Path

import numpy as np
import SimpleITK as sitk
from PIL import Image
import app
from predictor import MODEL, predict

class AppTests(unittest.TestCase):
    def setUp(self):
        app.VOLUMES.clear()
        self.values = {'age':71,'sex_num':1,'cart_area_PL':0,'cart_area_FMA':0,'bml_size_SS':0}

    def test_verified_probabilities_and_monotonicity(self):
        r = predict(self.values)
        self.assertAlmostEqual(r['risk']['5'], 1-0.9771467433558098, places=12)
        self.assertAlmostEqual(r['risk']['10'], 1-0.956652774393697, places=12)
        self.assertLess(r['risk']['5'],r['risk']['10'])
        high = predict({**self.values, 'cart_area_PL':3,'cart_area_FMA':3,'bml_size_SS':3})
        self.assertGreater(high['risk']['5'],r['risk']['5'])
        self.assertEqual(high['group'],'High risk')
        mean = predict({**MODEL['means'], 'sex_num':0, 'cart_area_PL':0,'cart_area_FMA':0,'bml_size_SS':0})
        self.assertTrue(0 <= mean['risk']['10'] <= 1)

    def test_validation(self):
        for change in ({'age':19},{'age':float('nan')},{'sex_num':2},{'bml_size_SS':1.5},{'age':None},{'sex_num':True}):
            with self.assertRaises(ValueError):
                predict({**self.values,**change})

    def test_macos_browser_launcher(self):
        with patch.object(app.sys, 'platform', 'darwin'), patch.object(app.subprocess, 'run') as run:
            run.return_value.returncode = 0
            self.assertTrue(app.open_browser('http://127.0.0.1:8765'))
            run.assert_called_once_with(['/usr/bin/open', 'http://127.0.0.1:8765'], timeout=10, check=False)

    def test_launch_reuses_existing_app(self):
        with patch.object(app.sys, 'argv', ['app.py']), patch.object(app, 'ThreadingHTTPServer', side_effect=OSError), patch.object(app, 'existing_app', return_value=True), patch.object(app, 'open_browser') as launch:
            app.main()
            launch.assert_called_once_with('http://127.0.0.1:8765')

    def test_formats_and_slices(self):
        with tempfile.TemporaryDirectory() as tmp:
            arr=np.arange(5*6*7,dtype=np.float32).reshape(5,6,7)
            image=sitk.GetImageFromArray(arr);image.SetSpacing((1,2,3))
            for ext in ('.nii','.nii.gz','.nrrd'):
                path=Path(tmp)/('volume'+ext);sitk.WriteImage(image,str(path))
                volume=app.load_volume(path)
                np.testing.assert_array_equal(volume[0],arr)
                for plane,index in [('axial',2),('coronal',3),('sagittal',3)]:
                    png=app.slice_png(volume,plane,index,300,150)
                    rendered=Image.open(io.BytesIO(png))
                    self.assertGreater(rendered.width,0)
                    if plane=='axial':
                        self.assertEqual(rendered.size,(7,12))
            image4=sitk.JoinSeries(image,image)
            path=Path(tmp)/'four.nii';sitk.WriteImage(image4,str(path))
            with self.assertRaises(ValueError): app.load_volume(path)

    def test_http_end_to_end(self):
        server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler)
        server.daemon_threads=True
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        def request(path,body=None,headers=None):
            req=urllib.request.Request(base+path,data=body,headers=headers or {})
            return urllib.request.urlopen(req,timeout=10)
        try:
            self.assertTrue(app.existing_app(base))
            self.assertIn(b'Knee Risk Studio',request('/').read())
            token=json.loads(request('/api/config').read())['token']
            with self.assertRaises(urllib.error.HTTPError):request('/api/predict',b'{}')
            auth={'X-Local-Token':token}
            r=json.loads(request('/api/predict',json.dumps(self.values).encode(),auth).read())
            self.assertAlmostEqual(r['risk']['5'],0.0228532566441902,places=12)
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'image.nii.gz';sitk.WriteImage(sitk.GetImageFromArray(np.ones((5,6,7),dtype=np.float32)),str(path))
                boundary='OAItestboundary'
                body=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="image.nii.gz"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()+path.read_bytes()+f'\r\n--{boundary}--\r\n'.encode())
                meta=json.loads(request('/api/upload',body,{**auth,'Content-Type':f'multipart/form-data; boundary={boundary}'}).read())
                data=request(f'/api/slice?id={meta["id"]}&plane=axial&index=2&width=1&level=1',headers=auth).read()
                self.assertEqual(Image.open(io.BytesIO(data)).format,'PNG')
                old_id=meta['id']
                sitk.WriteImage(sitk.GetImageFromArray(np.full((9,8,7),5,dtype=np.float32)),str(path))
                body=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="coronal.nii.gz"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()+path.read_bytes()+f'\r\n--{boundary}--\r\n'.encode())
                second=json.loads(request('/api/upload',body,{**auth,'Content-Type':f'multipart/form-data; boundary={boundary}'}).read())
                self.assertNotEqual(old_id,second['id'])
                self.assertEqual(second['size'],[7,8,9])
                self.assertEqual(len(json.loads(request('/api/volumes',headers=auth).read())),2)
                first_png=request(f'/api/slice?id={old_id}&plane=axial&index=2&width=10&level=5',headers=auth).read()
                second_png=request(f'/api/slice?id={second["id"]}&plane=coronal&index=3&width=10&level=5',headers=auth).read()
                self.assertNotEqual(first_png,second_png)
                with patch.object(app,'MAX_SEQUENCES',2):
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        request('/api/upload',body,{**auth,'Content-Type':f'multipart/form-data; boundary={boundary}'})
                    self.assertEqual(error.exception.code,400)
                self.assertEqual(len(app.VOLUMES),2)
                with patch.object(app,'MAX_TOTAL_BYTES',1):
                    with self.assertRaises(urllib.error.HTTPError):
                        request('/api/upload',body,{**auth,'Content-Type':f'multipart/form-data; boundary={boundary}'})
                self.assertEqual(len(app.VOLUMES),2)
            request('/api/clear',b'{}',auth).read()
            self.assertEqual(app.VOLUMES,{})
        finally:
            server.shutdown();server.server_close();thread.join()

if __name__=='__main__': unittest.main(verbosity=2)
