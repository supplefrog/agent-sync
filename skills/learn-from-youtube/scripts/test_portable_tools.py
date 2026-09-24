"""Production-path regression probes; fixtures prove mechanics, not pedagogy."""
import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from bs4 import BeautifulSoup
from PIL import Image
from capture_frames import capture
from render_lesson import render


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'lesson.md'
        self.output = self.root / 'reader.html'

    def write(self, text):
        self.source.write_text(text, encoding='utf-8')

    def test_plain_article_needs_no_project_or_figures(self):
        self.write('# A useful question\n\nFor a new reader.\n\n## Think it through\n\nExplain why.')
        result = render(self.source, self.output)
        self.assertEqual(result['image_count'], 0)
        self.assertFalse(result['semantic_review'])
        soup=BeautifulSoup(self.output.read_text(encoding='utf-8'),'html.parser')
        self.assertEqual(soup.h1.text, 'A useful question')
        self.assertFalse(soup.select('script[src],link[rel="stylesheet"]'))

    def test_native_mime_bytes_caption_answers_and_focus_markup(self):
        image=self.root/'native.png'
        Image.new('RGB',(90,60),'red').save(image,format='JPEG')
        self.write('# Fixture\n\n## Observe\n\n![A red field](native.png)\n\n*Fixture, not course evidence.*\n\n<details markdown="1"><summary>Reveal</summary>\n\nThe answer.\n\n</details>')
        before=self.source.read_bytes()
        render(self.source,self.output)
        soup=BeautifulSoup(self.output.read_text(encoding='utf-8'),'html.parser')
        self.assertTrue(soup.img['src'].startswith('data:image/jpeg;base64,'))
        self.assertEqual(base64.b64decode(soup.img['src'].split(',')[1]),image.read_bytes())
        self.assertEqual(soup.img.parent['aria-haspopup'],'dialog')
        self.assertIn('Fixture, not course evidence.',soup.figcaption.text)
        self.assertEqual(soup.select_one('details:not(.contents) summary').text,'Reveal')
        self.assertEqual(before,self.source.read_bytes())

    def test_active_source_markup_cannot_execute(self):
        self.write('# Fixture\n\n<script>alert(1)</script><p onclick="alert(2)">Read</p><a href="java&#10;script:alert(3)">Unsafe link</a>')
        render(self.source,self.output)
        soup=BeautifulSoup(self.output.read_text(encoding='utf-8'),'html.parser')
        self.assertEqual(len(soup.find_all('script')),1) # only bundled reader script
        self.assertNotIn('alert(',soup.select_one('main').decode())

    def test_outside_assets_and_remote_images_rejected(self):
        for path in ('../outside.png','https://example.org/image.png'):
            with self.subTest(path=path):
                self.write(f'# Fixture\n\n![Image]({path})')
                with self.assertRaises(ValueError): render(self.source,self.output)
                self.assertFalse(self.output.exists())

    def test_existing_output_never_overwritten(self):
        self.write('# Fixture')
        self.output.write_text('preserve',encoding='utf-8')
        with self.assertRaises(ValueError): render(self.source,self.output)
        self.assertEqual(self.output.read_text(),'preserve')

    def test_missing_alt_and_duplicate_heading_ids_rejected(self):
        Image.new('RGB',(10,10),'blue').save(self.root/'x.png')
        for text in ('# Title\n\n![](x.png)', '# Title\n\n<h2 id="same">A</h2><h2 id="same">B</h2>'):
            self.write(text)
            with self.assertRaises(ValueError): render(self.source,self.output)

    def test_active_svg_rejected_and_simple_svg_preserved(self):
        svg=self.root/'diagram.svg'
        self.write('# Figure\n\n![Diagram](diagram.svg)')
        svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 40"><script>alert(1)</script></svg>')
        with self.assertRaises(ValueError): render(self.source,self.output)
        svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 40"><text x="2" y="20">Fixture</text></svg>')
        render(self.source,self.output)
        soup=BeautifulSoup(self.output.read_text(encoding='utf-8'),'html.parser')
        self.assertEqual(base64.b64decode(soup.img['src'].split(',')[1]),svg.read_bytes())

    def test_svg_animation_and_stylesheet_instructions_rejected(self):
        self.write('# Figure\n\n![Diagram](diagram.svg)')
        for markup in ('<animateTransform attributeName="transform"/>',
                       '<animateMotion path="M0 0 L10 10"/>',
                       '<?xml-stylesheet type="text/css" href="https://example.org/a.css"?>'):
            with self.subTest(markup=markup):
                (self.root/'diagram.svg').write_text(
                    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 40">'+markup+'</svg>')
                try:
                    with self.assertRaises(ValueError): render(self.source, self.output)
                finally:
                    self.output.unlink(missing_ok=True)


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),'local media tools required')
class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.media=self.root/'fixture.mp4'
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=96x64:rate=10','-t','1','-c:v','libx264','-pix_fmt','yuv420p',str(self.media)],check=True,timeout=20)
        self.digest=hashlib.sha256(self.media.read_bytes()).hexdigest()

    def test_source_identity_mapping_and_candidate_only_receipt(self):
        result=capture(self.media,self.root/'frames',[0,.5],'fixture states',source_origin=12)
        self.assertEqual(result['status'],'captured_candidates_not_reviewed')
        self.assertEqual(len(result['frames']),2)
        self.assertEqual(result['frames'][1]['requested_source_seconds'],12.5)
        self.assertIsNone(result['frames'][1]['actual_source_seconds'])
        self.assertFalse(result['semantic_coverage_verified'])
        self.assertTrue(result['source_size_mtime_unchanged'])
        self.assertEqual(self.digest,hashlib.sha256(self.media.read_bytes()).hexdigest())
        self.assertEqual(json.loads((self.root/'frames/capture.json').read_text())['status'],result['status'])

    def test_eof_and_storage_failure_never_issue_success(self):
        for name,times,budget in [('eof',[9],1_000_000),('tiny',[0],1)]:
            result=capture(self.media,self.root/name,times,'boundary',max_bytes=budget)
            self.assertEqual(result['status'],'blocked')
            self.assertFalse(result['semantic_coverage_verified'])

    def test_invalid_or_existing_batch_is_not_reset(self):
        for times in ([float('nan')],[-1],[0,0],list(range(13))):
            with self.assertRaises(ValueError): capture(self.media,self.root/'invalid',times,'fixture')
        folder=self.root/'existing'
        folder.mkdir()
        (folder/'capture.json').write_text('preserve')
        with self.assertRaises(FileExistsError): capture(self.media,folder,[0],'fixture')
        self.assertEqual((folder/'capture.json').read_text(),'preserve')

    def test_local_reference_input_is_rejected(self):
        playlist = self.root / 'reference.m3u8'
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(self.media), '-c', 'copy',
                        '-f', 'hls', str(playlist)], check=True, timeout=30)
        result = capture(playlist, self.root/'reference-frames', [0], 'reference negative')
        self.assertEqual(result['status'], 'blocked')

if __name__=='__main__':
    unittest.main(verbosity=2)
