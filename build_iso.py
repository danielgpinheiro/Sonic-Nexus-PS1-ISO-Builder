#!/usr/bin/env python3
"""Sonic Nexus PS1 ISO Builder: your Sonic Nexus (2008) Data.bin -> a PlayStation disc image.

    python3 build_iso.py --data /path/to/Data.bin [--license licensea.dat] [--out output]

1. checks the tools (Python packages, psxavenc, ffmpeg/ffprobe, mkpsxiso, a C++17 compiler);
2. checks that Data.bin is the original 2008 release (SHA-256), unless --force;
3. converts the game's assets for the PlayStation (builder/tools/build_assets.py);
4. builds the disc around the prebuilt executable (bin/SonicNexus-PS1.exe) with mkpsxiso;
5. verifies the image byte by byte (EDC/ECC, license sectors, every file);
6. writes output/SonicNexus-PS1.bin + .cue + SHA256SUMS.

No game data is included in this repository: download Sonic Nexus yourself (see README.md).
"""
import argparse, hashlib, os, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
BUILDER = os.path.join(ROOT, 'builder')
EXE = os.path.join(ROOT, 'bin', 'SonicNexus-PS1.exe')
NAME = 'SonicNexus-PS1'
DATA_SHA256 = 'b876d40ff9e045b9a254f2471dcfe691968013e4f2ac0f82fba9947536dc0868'  # Sonic Nexus 2008 Data.bin

sys.path.insert(0, os.path.join(BUILDER, 'tools'))
import build_assets  # noqa: E402


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description='Build a Sonic Nexus PlayStation disc image from your own Data.bin.')
    ap.add_argument('--data', required=True, help='Data.bin from the Sonic Nexus (2008) download')
    ap.add_argument('--license', help='optional Sony license file (e.g. licensea.dat, NTSC-U) for retail consoles')
    ap.add_argument('--out', default=os.path.join(ROOT, 'output'), help='output folder (default: output/)')
    ap.add_argument('--force', action='store_true', help='accept a Data.bin that is not the original release')
    ap.add_argument('--keep-work', action='store_true', help='keep the intermediate files (output/work)')
    a = ap.parse_args()

    if sys.version_info < (3, 8):
        sys.exit('Python 3.8 or newer is required.')
    if not os.path.isfile(a.data):
        sys.exit('Data.bin not found: %s' % a.data)
    if a.license and not os.path.isfile(a.license):
        sys.exit('License file not found: %s' % a.license)
    tools = build_assets.check_tools(need_disc=True)
    got = sha256(a.data)
    if got != DATA_SHA256:
        msg = 'This Data.bin is not the original Sonic Nexus (2008) file (SHA-256 %s).' % got
        if not a.force:
            sys.exit(msg + '\nUse the unmodified Data.bin from the download, or pass --force to try anyway.')
        print('WARNING: ' + msg + ' Continuing because of --force.')

    out = os.path.abspath(a.out)
    work = os.path.join(out, 'work')
    if os.path.exists(work):
        shutil.rmtree(work)
    os.makedirs(work)
    env = dict(os.environ, **tools)
    py = sys.executable
    subprocess.run([py, os.path.join(BUILDER, 'tools', 'build_assets.py'), '--data', a.data, '--out', work],
                   env=env, check=True)
    iso = os.path.join(work, 'build', 'iso')
    prefix = os.path.join(out, NAME)
    lic = os.path.abspath(a.license) if a.license else 'none'
    print('[disc] mkpsxiso', flush=True)
    subprocess.run([py, os.path.join(BUILDER, 'tools', 'disc', 'build_disc.py'), iso, EXE, lic, prefix],
                   env=env, check=True)
    print('[verify]', flush=True)
    subprocess.run([py, os.path.join(BUILDER, 'tools', 'disc', 'verify_disc.py'), prefix + '.bin', iso, EXE, lic],
                   env=env, check=True)
    with open(os.path.join(out, 'SHA256SUMS'), 'w') as f:
        for ext in ('.bin', '.cue'):
            f.write('%s  %s\n' % (sha256(prefix + ext), NAME + ext))
    if not a.keep_work:
        shutil.rmtree(work)
        shutil.rmtree(os.path.join(out, 'disc'), ignore_errors=True)
    print('\nDone: %s.cue / .bin%s' % (prefix, '' if a.license else
                                       '\n(no license file: plays in emulators, on ODEs and modded consoles)'))


if __name__ == '__main__':
    main()
