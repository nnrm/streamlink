import ntpath
import os
import posixpath
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

from streamlink_cli.output import FileOutput, PlayerOutput
from tests import posix_only, windows_only


@patch("streamlink_cli.output.stdout")
class TestFileOutput(unittest.TestCase):
    @staticmethod
    def subject(filename, fd):
        fo_record = FileOutput(fd=fd)
        fo_main = FileOutput(filename=filename, record=fo_record)

        return fo_main, fo_record

    def test_init(self, mock_stdout: Mock):
        mock_path = Mock(spec=Path("foo", "bar"))
        fo_main, fo_record = self.subject(mock_path, mock_stdout)

        self.assertEqual(fo_main.opened, False)
        self.assertIs(fo_main.filename, mock_path)
        self.assertIs(fo_main.fd, None)
        self.assertIs(fo_main.record, fo_record)

        self.assertEqual(fo_main.record.opened, False)
        self.assertIs(fo_main.record.filename, None)
        self.assertIs(fo_main.record.fd, mock_stdout)
        self.assertIs(fo_main.record.record, None)

    def test_early_close(self, mock_stdout: Mock):
        mock_path = Mock(spec=Path("foo", "bar"))
        fo_main, fo_record = self.subject(mock_path, mock_stdout)

        fo_main.close()  # doesn't raise

    def test_early_write(self, mock_stdout: Mock):
        mock_path = Mock(spec=Path("foo", "bar"))
        fo_main, fo_record = self.subject(mock_path, mock_stdout)

        with self.assertRaises(OSError) as cm:
            fo_main.write(b"foo")
        self.assertEqual(str(cm.exception), "Output is not opened")

    def _test_open(self, mock_open: Mock, mock_stdout: Mock):
        mock_path = Mock(spec=Path("foo", "bar"))
        mock_fd = mock_open(mock_path, "wb")
        fo_main, fo_record = self.subject(mock_path, mock_stdout)

        fo_main.open()
        self.assertEqual(fo_main.opened, True)
        self.assertEqual(fo_main.record.opened, True)
        self.assertEqual(mock_path.parent.mkdir.call_args_list, [call(parents=True, exist_ok=True)])
        self.assertIs(fo_main.fd, mock_fd)

        fo_main.write(b"foo")
        self.assertEqual(mock_fd.write.call_args_list, [call(b"foo")])
        self.assertEqual(mock_stdout.write.call_args_list, [call(b"foo")])

        fo_main.close()
        self.assertEqual(mock_fd.close.call_args_list, [call()])
        self.assertEqual(mock_stdout.close.call_args_list, [])
        self.assertEqual(fo_main.opened, False)
        self.assertEqual(fo_main.record.opened, False)

        return mock_path

    @posix_only
    @patch("builtins.open")
    def test_open_posix(self, mock_open: Mock, mock_stdout: Mock):
        self._test_open(mock_open, mock_stdout)

    @windows_only
    @patch("streamlink_cli.output.msvcrt")
    @patch("builtins.open")
    def test_open_windows(self, mock_open: Mock, mock_msvcrt: Mock, mock_stdout: Mock):
        mock_path = self._test_open(mock_open, mock_stdout)
        self.assertEqual(mock_msvcrt.setmode.call_args_list, [
            call(mock_stdout.fileno(), os.O_BINARY),
            call(mock_open(mock_path, "wb").fileno(), os.O_BINARY),
        ])


class TestPlayerOutput(unittest.TestCase):
    def test_supported_player_generic(self):
        self.assertEqual("vlc",
                         PlayerOutput.supported_player("vlc"))

        self.assertEqual("mpv",
                         PlayerOutput.supported_player("mpv"))

        self.assertEqual("potplayer",
                         PlayerOutput.supported_player("potplayermini.exe"))

    @patch("streamlink_cli.output.os.path.basename", new=ntpath.basename)
    def test_supported_player_win32(self):
        self.assertEqual("mpv",
                         PlayerOutput.supported_player("C:\\MPV\\mpv.exe"))
        self.assertEqual("vlc",
                         PlayerOutput.supported_player("C:\\VLC\\vlc.exe"))
        self.assertEqual("potplayer",
                         PlayerOutput.supported_player("C:\\PotPlayer\\PotPlayerMini64.exe"))

    @patch("streamlink_cli.output.os.path.basename", new=posixpath.basename)
    def test_supported_player_posix(self):
        self.assertEqual("mpv",
                         PlayerOutput.supported_player("/usr/bin/mpv"))
        self.assertEqual("vlc",
                         PlayerOutput.supported_player("/usr/bin/vlc"))

    @patch("streamlink_cli.output.os.path.basename", new=ntpath.basename)
    def test_supported_player_args_win32(self):
        self.assertEqual("mpv",
                         PlayerOutput.supported_player("C:\\MPV\\mpv.exe --argh"))
        self.assertEqual("vlc",
                         PlayerOutput.supported_player("C:\\VLC\\vlc.exe --argh"))
        self.assertEqual("potplayer",
                         PlayerOutput.supported_player("C:\\PotPlayer\\PotPlayerMini64.exe --argh"))

    @patch("streamlink_cli.output.os.path.basename", new=posixpath.basename)
    def test_supported_player_args_posix(self):
        self.assertEqual("mpv",
                         PlayerOutput.supported_player("/usr/bin/mpv --argh"))
        self.assertEqual("vlc",
                         PlayerOutput.supported_player("/usr/bin/vlc --argh"))

    @patch("streamlink_cli.output.os.path.basename", new=posixpath.basename)
    def test_supported_player_negative_posix(self):
        self.assertEqual(None,
                         PlayerOutput.supported_player("/usr/bin/xmpvideo"))
        self.assertEqual(None,
                         PlayerOutput.supported_player("/usr/bin/echo"))

    @patch("streamlink_cli.output.os.path.basename", new=ntpath.basename)
    def test_supported_player_negative_win32(self):
        self.assertEqual(None,
                         PlayerOutput.supported_player("C:\\mpc\\mpc-hd.exe"))
        self.assertEqual(None,
                         PlayerOutput.supported_player("C:\\mplayer\\not-vlc.exe"))
        self.assertEqual(None,
                         PlayerOutput.supported_player("C:\\NotPlayer\\NotPlayerMini64.exe"))

    def test_open_player_with_title_mpv_escape_1(self):
        self.assertEqual(PlayerOutput._mpv_title_escape("no escape $$ codes $"),
                         'no escape $$$$ codes $$')

    def test_open_player_with_title_mpv_escape_2(self):
        self.assertEqual(PlayerOutput._mpv_title_escape(r'\$> begins with escape code $$'),
                         '$> begins with escape code $$')

    def test_open_player_with_title_mpv_escape_3(self):
        self.assertEqual(PlayerOutput._mpv_title_escape(r'ends with escape code $$ \$>'),
                         'ends with escape code $$$$ $>')

    def test_open_player_with_title_mpv_escape_4(self):
        self.assertEqual(PlayerOutput._mpv_title_escape(r'\$> $$ begins with escape and double \$> $$ escape codes'),
                         '$> $$ begins with escape and double $> $$ escape codes')

    def test_open_player_with_title_mpv_escape_5(self):
        self.assertEqual(PlayerOutput._mpv_title_escape(r'\$> \\$> showing "\$>" after escaping'),
                         r'$> \$> showing "$>" after escaping')

    def test_open_player_with_title_mpv_escape_6(self):
        self.assertEqual(PlayerOutput._mpv_title_escape("$$$$$$> not a valid way to escape $"),
                         '$$$$$$$$$$$$> not a valid way to escape $$')

    def test_open_player_with_title_mpv_escape_7(self):
        self.assertEqual(PlayerOutput._mpv_title_escape("$> also not a valid way to escape $"),
                         '$$> also not a valid way to escape $$')

    def test_open_player_with_title_mpv_escape_8(self):
        self.assertEqual(PlayerOutput._mpv_title_escape("not valid $$$$$$> not a valid way to escape $"),
                         'not valid $$$$$$$$$$$$> not a valid way to escape $$')

    def test_open_player_with_title_mpv_escape_9(self):
        self.assertEqual(PlayerOutput._mpv_title_escape(r'Multiple $> \$> $> $$ \$> $$> $> \$> $> $> \$> \$> \$>\$>$$$$'),
                         'Multiple $$> $> $> $$ $> $$> $> $> $> $> $> $> $>$>$$$$')

    def test_open_player_with_title_mpv_escape_10(self):
        self.assertEqual(PlayerOutput._mpv_title_escape(r'odd leading $$$\$> $$$ $>'),
                         'odd leading $$$$$$$> $$$ $>')

    def test_open_player_with_title_mpv_escape_11(self):
        self.assertEqual(PlayerOutput._mpv_title_escape(r'even leading $$\$\$> $$$$$'),
                         'even leading $$$$$$> $$$$$$$$$$')  # will expand after \$> because eve)

    def test_open_player_with_title_mpv_escape_12(self):
        self.assertEqual(PlayerOutput._mpv_title_escape(r'$$$$$\$\$> even leading beginning $$'),
                         r'$$$$$$$$$$$$> even leading beginning $$$$')

    def test_open_player_with_title_mpv_escape_13(self):
        self.assertEqual(PlayerOutput._mpv_title_escape(r'$$$$$\$> odd leading beginning $$'),
                         r'$$$$$$$$$$$> odd leading beginning $$')

    def test_open_player_with_title_mpv_escape_14(self):
        self.assertEqual(PlayerOutput._mpv_title_escape(r'odd and even $\$> $$ \$\$> $$'),
                         'odd and even $$$> $$ $$> $$')

    def test_open_player_with_title_mpv_escape_15(self):
        self.assertEqual(PlayerOutput._mpv_title_escape(r'even and odd \$\$> $$ $\$> $$'),
                         'even and odd $$> $$$$ $$$> $$')

    def test_open_player_with_title_mpv_escape_16(self):
        self.assertEqual(PlayerOutput._mpv_title_escape(r'\$\$> $$$ \\$> $ showing "\$>" before escaping'),
                         r'$$> $$$$$$ \$> $ showing "$>" before escaping')
