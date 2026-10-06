import os
import tempfile
import unittest
from unittest.mock import patch

from modules.browser_lock import (
    extract_pid_from_lock,
    is_pid_alive,
    cleanup_stale_profile_locks,
    get_profile_dir,
)


class TestBrowserLock(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_extract_pid_from_lock_file(self):
        lock_file = os.path.join(self.temp_dir, "SingletonLock")
        with open(lock_file, "w", encoding="utf-8") as f:
            f.write("host-99999")
        pid = extract_pid_from_lock(lock_file)
        self.assertEqual(pid, 99999)

    def test_is_pid_alive_nonexistent(self):
        # A very large PID unlikely to exist
        self.assertFalse(is_pid_alive(99999999))
        self.assertFalse(is_pid_alive(-1))
        self.assertFalse(is_pid_alive(0))

    def test_is_pid_alive_current(self):
        # Current process is alive
        self.assertTrue(is_pid_alive(os.getpid()))

    def test_cleanup_stale_profile_locks(self):
        lock_path = os.path.join(self.temp_dir, "SingletonLock")
        cookie_path = os.path.join(self.temp_dir, "SingletonCookie")
        socket_path = os.path.join(self.temp_dir, "SingletonSocket")

        # Create simulated dead locks pointing to dead PID 99999999
        with open(lock_path, "w") as f:
            f.write("deadhost-99999999")
        with open(cookie_path, "w") as f:
            f.write("12345")
        with open(socket_path, "w") as f:
            f.write("socket")

        self.assertTrue(os.path.exists(lock_path))
        self.assertTrue(os.path.exists(cookie_path))
        self.assertTrue(os.path.exists(socket_path))

        cleanup_stale_profile_locks(self.temp_dir)

        self.assertFalse(os.path.exists(lock_path))
        self.assertFalse(os.path.exists(cookie_path))
        self.assertFalse(os.path.exists(socket_path))

    def test_cleanup_handles_large_cookie_int_without_overflow(self):
        # Chrome cookies can contain 64-bit/large ints that exceed C pid_t bounds
        cookie_path = os.path.join(self.temp_dir, "SingletonCookie")
        with open(cookie_path, "w") as f:
            f.write("140735812398123981238912349182390123")
        self.assertIsNone(extract_pid_from_lock(cookie_path))
        self.assertFalse(is_pid_alive(140735812398123981238912349182390123))
        cleanup_stale_profile_locks(self.temp_dir)
        self.assertFalse(os.path.exists(cookie_path))

    def test_cleanup_preserves_active_lock(self):
        lock_path = os.path.join(self.temp_dir, "SingletonLock")
        # Write current process PID which is active
        with open(lock_path, "w") as f:
            f.write(f"activehost-{os.getpid()}")

        cleanup_stale_profile_locks(self.temp_dir)
        # Should NOT be removed because process is alive
        self.assertTrue(os.path.exists(lock_path))

    def test_get_profile_dir_multi_user(self):
        user_dir = get_profile_dir("linkedin", user_id=2)
        self.assertIn("user_2_linkedin", user_dir)
        self.assertTrue(os.path.exists(user_dir))

        user_naukri = get_profile_dir("naukri", user_id=5)
        self.assertIn("user_5_naukri", user_naukri)
        self.assertTrue(os.path.exists(user_naukri))

    def test_get_profile_dir_default_user(self):
        ln_dir = get_profile_dir("linkedin", user_id=1)
        self.assertTrue(ln_dir.endswith("-chrome-profile"))

        nk_dir = get_profile_dir("naukri", user_id=1)
        self.assertTrue(nk_dir.endswith("-naukri-profile"))


if __name__ == "__main__":
    unittest.main()
