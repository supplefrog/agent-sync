"""Offline regression checks for the source-ready CLI; FFmpeg required."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('source_ready.py')


class ReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.good = cls.root / 'good.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=10', '-t', '2', '-c:v', 'libx264', '-y', str(cls.good)], check=True, timeout=30)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def gate(self, media, duration='2', extra=()):
        receipt = self.root / 'receipt.json'
        receipt.write_text('{"status":"media_ready_not_semantically_reviewed"}', encoding='utf-8')
        p = subprocess.run([sys.executable, str(SCRIPT), str(media), '--duration', duration, '--receipt', str(receipt), *extra], capture_output=True, text=True, timeout=40)
        return p.returncode, json.loads(receipt.read_text(encoding='utf-8'))

    def test_valid_silent_source(self):
        code, result = self.gate(self.good)
        self.assertEqual(code, 0)
        self.assertTrue(result['full_decode_passed'])
        self.assertFalse(result['audio_present'])

    def test_missing_source_invalidates_old_pass(self):
        code, result = self.gate(self.root / 'missing.mp4')
        self.assertNotEqual(code, 0)
        self.assertEqual(result['status'], 'blocked')

    def test_caption_file_is_not_video(self):
        path = self.root / 'captions.json'
        path.write_text('{"events":[]}', encoding='utf-8')
        self.assertNotEqual(self.gate(path)[0], 0)

    def test_truncated_media(self):
        path = self.root / 'truncated.mp4'
        path.write_bytes(self.good.read_bytes()[:200])
        self.assertNotEqual(self.gate(path)[0], 0)

    def test_wrong_duration(self):
        self.assertNotEqual(self.gate(self.good, '20')[0], 0)

    def test_required_audio_missing(self):
        self.assertNotEqual(self.gate(self.good, extra=['--require-audio'])[0], 0)

    def test_insufficient_resolution(self):
        self.assertNotEqual(self.gate(self.good, extra=['--min-height', '1080'])[0], 0)

    def test_nonfinite_duration(self):
        self.assertNotEqual(self.gate(self.good, 'nan')[0], 0)

    def test_each_required_stream_must_cover_interval(self):
        for video_duration, audio_duration in ((1, 2), (2, 1), (2, 2)):
            with self.subTest(video=video_duration, audio=audio_duration):
                path = self.root / f'streams-{video_duration}-{audio_duration}.mkv'
                subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                                f'testsrc2=size=96x64:rate=10:duration={video_duration}',
                                '-f', 'lavfi', '-i', f'sine=duration={audio_duration}',
                                '-c:v', 'libx264', '-c:a', 'pcm_s16le', str(path)],
                               check=True, timeout=30)
                code, _ = self.gate(path, extra=['--require-audio'])
                self.assertEqual(code == 0, video_duration == audio_duration == 2)

    def test_playlists_rejected_even_when_local_media_is_valid(self):
        playlist = self.root / 'reference.m3u8'
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(self.good), '-c', 'copy',
                        '-f', 'hls', str(playlist)], check=True, timeout=30)
        # Content detection, not a filename extension check.
        disguised = self.root / 'playlist.mp4'
        disguised.write_bytes(playlist.read_bytes())
        for path in (playlist, disguised):
            with self.subTest(path=path.name): self.assertNotEqual(self.gate(path)[0], 0)

    def test_receipt_alias_cannot_modify_media(self):
        for kind in ('hardlink', 'symlink'):
            with self.subTest(kind=kind):
                source = self.root / f'alias-source-{kind}.mp4'
                source.write_bytes(self.good.read_bytes())
                before = source.read_bytes()
                receipt = self.root / f'alias-{kind}.json'
                try:
                    if kind == 'hardlink': receipt.hardlink_to(source)
                    else: receipt.symlink_to(source)
                except OSError as exc:
                    if kind == 'symlink': continue  # Windows may disallow symlinks.
                    raise exc
                p = subprocess.run([sys.executable, str(SCRIPT), str(source), '--duration', '2',
                                    '--receipt', str(receipt)], capture_output=True, text=True, timeout=40)
                self.assertNotEqual(p.returncode, 0)
                self.assertEqual(source.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
