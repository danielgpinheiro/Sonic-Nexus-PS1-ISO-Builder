#!/usr/bin/env python3
"""The whole build-time asset pipeline in one command: Sonic Nexus Data.bin -> the disc's Data/ tree.

Stages (each tool documents its own format; golden rule: nothing is decoded at runtime):
   1. convert_tiles.py     16x16Tiles.gif -> .raw + .vram (VRAM tile pages), added into Data.bin
   2. extract_loose.py     Data.bin VFS -> loose Data/ tree (Data.bin itself leaves the disc tree)
   3. tools/rsdkscript     RetroScript -> per-stage bytecode + sprite manifests (C++17 host tool)
   4. tools/atlas          per-stage sprite atlas (.atl: 4/8-bit VRAM pages + CLUTs)
   5. tools/bgstrips       per-stage background line strips (BGStrips.bin)
   6. tools/audio          SFX -> .vag (SPU-ADPCM), music -> Music.xa + Music.bin (CD-XA)
   7. tools/fmv            Intro.rsv + Intro.ogg -> Intro.str + Intro.sti (MDEC video + XA audio)
The intro's .rsv source is moved out of the disc tree (fmv-src/). The PC source files that stay
in the tree (.gif, .wav, .ogg, .raw, .txt) are left off the disc by tools/disc/build_disc.py.

Output layout (the repo's own, so `make disc` works on it): OUT/build/iso/Data/**,
OUT/build/fmv-src/Intro.rsv, OUT/build/manifest/, OUT/build/Data.bin.patched.

External tools, found on PATH or through these environment variables: PSXAVENC, FFMPEG, FFPROBE,
CXX (C++17 compiler for rsdkscript), MKPSXISO (only for the disc). Python: Pillow + numpy.

Usage: build_assets.py --data PATH/Data.bin [--out DIR]   (default DIR: the repo, i.e. build/iso)
"""
import argparse, importlib.util, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..'))
WORKSPACE_TOOLS = {  # the development workspace's builds, used when nothing else is configured
    'PSXAVENC': os.path.join(REPO, '..', 'psxavenc', 'build', 'psxavenc'),
    'MKPSXISO': os.path.join(REPO, '..', 'mkpsxiso-2.30-Darwin', 'bin', 'mkpsxiso'),
}


def find_tool(env, name):
    path = os.environ.get(env) or shutil.which(name)
    if not path and os.path.exists(WORKSPACE_TOOLS.get(env, '')):
        path = WORKSPACE_TOOLS[env]
    return path


def check_tools(need_disc=False):
    tools, missing = {}, []
    wanted = [('PSXAVENC', 'psxavenc'), ('FFMPEG', 'ffmpeg'), ('FFPROBE', 'ffprobe')]
    if need_disc:
        wanted.append(('MKPSXISO', 'mkpsxiso'))
    for env, name in wanted:
        p = find_tool(env, name)
        (tools.__setitem__(env, os.path.abspath(p)) if p else missing.append('%s (or set %s)' % (name, env)))
    cxx = os.environ.get('CXX') or shutil.which('clang++') or shutil.which('g++') or shutil.which('c++')
    (tools.__setitem__('CXX', cxx) if cxx else missing.append('a C++17 compiler: clang++ or g++ (or set CXX)'))
    for mod, pkg in (('PIL', 'Pillow'), ('numpy', 'numpy')):
        if importlib.util.find_spec(mod) is None:
            missing.append('Python package %s (pip install %s)' % (pkg, pkg))
    if missing:
        sys.exit('Missing tools:\n  ' + '\n  '.join(missing))
    return tools


def run(step, cmd, cwd, env):
    print('[%s] %s' % (step, ' '.join(os.path.relpath(c, cwd) if os.path.isabs(c) and c.startswith(cwd) else c
                                      for c in cmd)), flush=True)
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--data', required=True, help='Sonic Nexus (2008) Data.bin')
    ap.add_argument('--out', default=REPO, help='output root (gets build/iso/Data/...)')
    a = ap.parse_args()
    tools = check_tools()
    env = dict(os.environ, **tools)
    py = sys.executable
    out = os.path.abspath(a.out)
    build = os.path.join(out, 'build')
    iso = os.path.join(build, 'iso')
    if os.path.exists(os.path.join(iso, 'Data')):
        sys.exit('%s already has a Data/ tree: use an empty --out (or remove build/iso/Data)' % iso)
    os.makedirs(iso, exist_ok=True)
    shutil.copyfile(a.data, os.path.join(iso, 'Data.bin'))

    run('1 tiles', [py, os.path.join(REPO, 'convert_tiles.py')], out, env)
    run('2 extract', [py, os.path.join(REPO, 'extract_loose.py')], out, env)
    os.replace(os.path.join(iso, 'Data.bin'), os.path.join(build, 'Data.bin.patched'))  # off the disc
    os.makedirs(os.path.join(build, 'fmv-src'), exist_ok=True)
    rsv = os.path.join(build, 'fmv-src', 'Intro.rsv')
    os.replace(os.path.join(iso, 'Data', 'Sprites', 'Videos', 'Intro.rsv'), rsv)

    run('3 scripts', ['make', '-s', '-C', os.path.join(REPO, 'tools', 'rsdkscript'), 'CXX=' + tools['CXX']], out, env)
    os.makedirs(os.path.join(iso, 'Data', 'Scripts', 'Bytecode'), exist_ok=True)
    run('3 scripts', [os.path.join(REPO, 'tools', 'rsdkscript', 'rsdkscript'), 'build/iso',
                      'build/iso/Data/Scripts/Bytecode', '--manifest', 'build/manifest'], out, env)
    run('4 atlas', [py, os.path.join(REPO, 'tools', 'atlas', 'build_atlas.py'), 'build/iso/Data', 'build/manifest'], out, env)
    run('5 bgstrips', [py, os.path.join(REPO, 'tools', 'bgstrips', 'build_bgstrips.py'), 'build/iso/Data'], out, env)
    run('6 sfx', [py, os.path.join(REPO, 'tools', 'audio', 'build_sfx.py'), 'build/iso/Data'], out, env)
    run('6 music', [py, os.path.join(REPO, 'tools', 'audio', 'build_music.py'), 'build/iso/Data'], out, env)
    run('7 video', [py, os.path.join(REPO, 'tools', 'fmv', 'build_str.py'), 'build/iso/Data', rsv], out, env)
    print('assets ready in %s' % os.path.join(iso, 'Data'))


if __name__ == '__main__':
    main()
