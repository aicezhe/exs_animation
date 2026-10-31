#!/usr/bin/env python3
"""Split long recordings into 1 s training clips.

Input layout (one long file per word per speaker, any format ffmpeg can read):
    <src>/<speaker>/<Word>.m4a        e.g.  EXS audio/franc/Elly.m4a

Output layout (16 kHz, mono, 16-bit, exactly 1.0 s each):
    <out>/<speaker>/<word>.<speaker>.m<mode>.<NN>.wav
    e.g.  data/franc/elly.franc.m3.02.wav

Each long file is expected to contain the utterances in recording order:
    MODE_COUNTS = 8, 6, 4, 4, 7   ->  modes m1..m5, 29 utterances in total.
Utterances are found by short-time energy above a rolling noise floor. If the
number found differs from the expected one, nothing is written for that file;
open the preview image, then tune --margin-db (see --help) or use --force.

Needs: ffmpeg on PATH, numpy, scipy, matplotlib.
"""
import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.ndimage import percentile_filter, uniform_filter1d

SR = 16000                    # Hz, same as the notebook
WIN = int(SR * 0.02)          # 20 ms analysis frame (320 samples)
HOP = int(SR * 0.01)          # 10 ms step (160 samples)
MODE_COUNTS = (8, 6, 4, 4, 7)
WORDS = ("elly", "focus", "slack", "telegram")
AUDIO_EXT = {".m4a", ".mp3", ".wav", ".aac", ".flac", ".ogg", ".mp4", ".mov"}


def read_audio(path):
    """Decode any audio file to float32, 16 kHz, mono (through ffmpeg)."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "x.wav"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "wav", str(out)],
            check=True)
        sr, data = wavfile.read(out)
    assert sr == SR
    if data.dtype == np.int16:
        return data.astype(np.float32) / 32768.0
    return data.astype(np.float32)


def frame_db(y):
    """Loudness per 20 ms frame (10 ms step) in dB, via a cumulative sum of y**2."""
    cs = np.concatenate([[0.0], np.cumsum(y.astype(np.float64) ** 2)])
    starts = np.arange(0, len(y) - WIN + 1, HOP)
    energy = (cs[starts + WIN] - cs[starts]) / WIN
    return 10.0 * np.log10(energy + 1e-10)


def find_segments(y, margin_db, min_gap, min_len, floor_seconds=3.0):
    """Return a list of (start, end) sample indices of utterances."""
    db = uniform_filter1d(frame_db(y), size=5)                       # smooth over ~50 ms
    size = max(3, int(floor_seconds / (HOP / SR)))
    floor = percentile_filter(db, percentile=10, size=size, mode="nearest")   # rolling noise floor
    active = (db > floor + margin_db) & (db > -70.0)

    # runs of active frames
    idx = np.flatnonzero(np.diff(np.concatenate([[0], active.astype(np.int8), [0]])))
    runs = [[idx[i], idx[i + 1]] for i in range(0, len(idx), 2)]

    # merge runs separated by short gaps (pauses inside a word)
    gap_frames = int(min_gap / (HOP / SR))
    merged = []
    for a, b in runs:
        if merged and a - merged[-1][1] <= gap_frames:
            merged[-1][1] = b
        else:
            merged.append([a, b])

    min_frames = int(min_len / (HOP / SR))
    segs = [(a * HOP, b * HOP + WIN) for a, b in merged if b - a >= min_frames]
    return segs, db, floor


def cut_clip(y, start, end, n_samples, align):
    """1 s window around the segment, zero-padded beyond the file edges."""
    centre = (start + end) // 2
    a = centre - n_samples // 2 if align == "center" else start - int(0.2 * SR)
    clip = np.zeros(n_samples, dtype=np.float32)
    lo, hi = max(a, 0), min(a + n_samples, len(y))
    clip[lo - a:hi - a] = y[lo:hi]
    return clip


def mode_of(index, counts):
    """Mode number (1-based) of the utterance with this 0-based index."""
    edge = 0
    for m, c in enumerate(counts, start=1):
        edge += c
        if index < edge:
            return m, index - (edge - c) + 1
    raise IndexError(index)


def save_preview(path, y, segs, db, floor, counts, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = np.arange(len(y)) / SR
    step = max(1, len(y) // 20000)
    fig, ax = plt.subplots(2, 1, figsize=(13, 5), sharex=True, gridspec_kw={"height_ratios": [3, 1.3]})
    ax[0].plot(t[::step], y[::step], lw=0.5, color="#555")
    colours = ["#2e7d32", "#1565c0", "#ef6c00", "#6a1b9a", "#c62828"]
    for i, (a, b) in enumerate(segs):
        ok = i < sum(counts)
        m = mode_of(i, counts)[0] if ok else 0
        col = colours[m - 1] if ok else "#000000"
        ax[0].axvspan(a / SR, b / SR, color=col, alpha=0.25)
        ax[0].text((a + b) / 2 / SR, ax[0].get_ylim()[1] * 0.9, str(i + 1), ha="center", fontsize=8)
    ax[0].set_title(title)
    tf = (np.arange(len(db)) * HOP + WIN / 2) / SR
    ax[1].plot(tf, db, lw=0.7, label="loudness, dB")
    ax[1].plot(tf, floor, lw=0.9, label="noise floor")
    ax[1].legend(loc="upper right", fontsize=8)
    ax[1].set_xlabel("time, s")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("src", type=Path, help="folder with <speaker>/<Word>.m4a")
    p.add_argument("out", type=Path, help="output folder, e.g. model/data")
    p.add_argument("--counts", default=",".join(map(str, MODE_COUNTS)), help="utterances per mode, in order")
    p.add_argument("--margin-db", type=float, default=10.0,
                   help="how far above the noise floor speech must be. Lower it if utterances are missing, raise it if there are extras")
    p.add_argument("--min-gap", type=float, default=0.25, help="pauses shorter than this stay inside one utterance, s")
    p.add_argument("--min-len", type=float, default=0.12, help="ignore sounds shorter than this, s")
    p.add_argument("--align", choices=["center", "start"], default="center",
                   help="where the word sits in the 1 s clip")
    p.add_argument("--pick-loudest", action="store_true",
                   help="if more utterances than expected are found, keep the loudest ones (check the preview!)")
    p.add_argument("--force", action="store_true", help="write clips even when the count does not match")
    p.add_argument("--dry-run", action="store_true", help="only write previews and the report")
    a = p.parse_args()

    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg not found. Install it, e.g. `brew install ffmpeg`.")
    counts = tuple(int(c) for c in a.counts.split(","))
    expected = sum(counts)
    n_samples = SR

    report = []
    files = sorted(f for f in a.src.rglob("*") if f.suffix.lower() in AUDIO_EXT and not f.name.startswith("."))
    if not files:
        raise SystemExit(f"No audio files under {a.src}")
    for f in files:
        speaker = f.parent.name.lower()
        word = f.stem.lower()
        if word not in WORDS:
            report.append((speaker, word, "-", expected, "skipped (not a command word)"))
            continue
        y = read_audio(f)
        segs, db, floor = find_segments(y, a.margin_db, a.min_gap, a.min_len)
        found = len(segs)
        if a.pick_loudest and found > expected:
            power = [float(np.mean(y[s:e] ** 2)) for s, e in segs]
            keep = sorted(np.argsort(power)[-expected:])
            segs = [segs[i] for i in keep]
        ok = len(segs) == expected
        status = "OK" if ok else ("FORCED" if a.force else "MISMATCH, nothing written")
        save_preview(a.out / "_preview" / f"{speaker}.{word}.png", y, segs, db, floor, counts,
                     f"{speaker} / {word}: found {found}, expected {expected}")
        if (ok or a.force) and not a.dry_run:
            dst = a.out / speaker
            dst.mkdir(parents=True, exist_ok=True)
            for i, (s, e) in enumerate(segs[:expected]):
                m, k = mode_of(i, counts)
                clip = cut_clip(y, s, e, n_samples, a.align)
                name = f"{word}.{speaker}.m{m}.{k:02d}.wav"
                wavfile.write(dst / name, SR, (np.clip(clip, -1, 1) * 32767).astype(np.int16))
        longest = max(((e - s) / SR for s, e in segs), default=0.0)
        report.append((speaker, word, found, expected, f"{status}; longest {longest:.2f} s"))

    print(f"{'speaker':10} {'word':10} {'found':>5} {'expected':>8}  status")
    for r in report:
        print(f"{r[0]:10} {r[1]:10} {r[2]!s:>5} {r[3]:>8}  {r[4]}")
    print(f"\nPreviews: {a.out / '_preview'}")


if __name__ == "__main__":
    main()