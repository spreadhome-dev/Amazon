#!/usr/bin/env python3
"""
setup.py — Spread Spain Backend Setup
Fixes Python 3.14 compatibility & pythonw.exe pip issue.
Run with: python setup.py  (NOT pythonw)
"""

import subprocess, sys, os, platform

def run(cmd, capture=False):
    print(f"\n  ▶ {cmd}")
    if capture:
        return subprocess.run(cmd, shell=True, capture_output=True, text=True)
    result = subprocess.run(cmd, shell=True)
    return result

def fail(msg):
    print(f"\n❌  {msg}")
    print("\n    Press Enter to close...")
    input()
    sys.exit(1)

print("""
╔══════════════════════════════════════════════════╗
║   Spread Spain — Amazon Monitor Backend Setup    ║
╚══════════════════════════════════════════════════╝
""")

# ── 1. Make sure we're using python.exe, not pythonw.exe ──────────────────
exe = sys.executable
if exe.endswith("pythonw.exe"):
    python_exe = exe.replace("pythonw.exe", "python.exe")
    if os.path.exists(python_exe):
        print(f"  ⚠  Detected pythonw.exe — relaunching with python.exe ...")
        os.execv(python_exe, [python_exe] + sys.argv)
    else:
        fail("Cannot find python.exe. Open a Command Prompt and run:\n    python setup.py")

print(f"  ✅ Python {sys.version.split()[0]}  ({exe})")
print(f"  ✅ Platform: {platform.system()} {platform.release()}")

# ── 2. Create virtual environment ─────────────────────────────────────────
venv_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv")
if not os.path.exists(venv_dir):
    print("\n📦 Creating virtual environment (venv)...")
    r = run(f'"{exe}" -m venv "{venv_dir}"')
    if r.returncode != 0:
        fail("Could not create venv.")
    print("  ✅ venv created")
else:
    print(f"\n  ✅ venv already exists")

# ── Pick python/pip inside venv ───────────────────────────────────────────
if platform.system() == "Windows":
    venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
    venv_pip    = os.path.join(venv_dir, "Scripts", "pip.exe")
else:
    venv_python = os.path.join(venv_dir, "bin", "python")
    venv_pip    = os.path.join(venv_dir, "bin", "pip")

# ── 3. Upgrade pip inside venv ────────────────────────────────────────────
print("\n📦 Upgrading pip inside venv...")
r = run(f'"{venv_python}" -m pip install --upgrade pip --quiet')
if r.returncode != 0:
    fail("pip upgrade failed. Check your internet connection.")

# ── 4. Install packages ───────────────────────────────────────────────────
print("\n📦 Installing Python packages...")
req_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
r = run(f'"{venv_pip}" install -r "{req_file}"')
if r.returncode != 0:
    fail(
        "Package installation failed.\n\n"
        "    Common fixes:\n"
        "    1. Check internet connection\n"
        "    2. Try running setup.py again\n"
        "    3. If behind a corporate proxy, set HTTP_PROXY env variable"
    )
print("  ✅ All packages installed")

# ── 5. Install Playwright Chromium browser ───────────────────────────────
print("\n🌐 Installing Playwright Chromium browser (may take 2-3 min)...")
r = run(f'"{venv_python}" -m playwright install chromium')
if r.returncode != 0:
    print("  ⚠  Playwright browser install had issues.")
    print("     Run manually: venv\\Scripts\\python -m playwright install chromium")
else:
    print("  ✅ Chromium installed")

# ── 6. Write START_SERVER.bat ─────────────────────────────────────────────
if platform.system() == "Windows":
    bat = os.path.join(os.path.dirname(os.path.abspath(__file__)), "START_SERVER.bat")
    with open(bat, "w") as f:
        f.write(f'@echo off\necho Starting Spread Spain Backend...\n"{venv_python}" app.py\npause\n')
    print(f"\n  ✅ Created START_SERVER.bat")

print(f"""
╔══════════════════════════════════════════════════╗
║   ✅  Setup Complete!                            ║
╠══════════════════════════════════════════════════╣
║                                                  ║
║   TO START THE SERVER:                           ║
║                                                  ║
║   Option A — Double-click: START_SERVER.bat      ║
║                                                  ║
║   Option B — Command Prompt:                     ║
║     venv\\Scripts\\python app.py                  ║
║                                                  ║
║   Then open dashboard.html in your browser.      ║
║   API runs at: http://localhost:5000             ║
╚══════════════════════════════════════════════════╝
""")
input("Press Enter to close...")
