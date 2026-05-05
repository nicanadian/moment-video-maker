"""Song analysis pipeline (PRD §F6, §14).

Produces a SongAnalysis whose shape matches PRD §8.4. The labeling heuristic
is intentionally conservative: section detection is approximate and the artist
is expected to hand-correct the JSON when needed (PRD §14.3).
"""

from __future__ import annotations

from pathlib import Path

from solypsizm_moment_studio.models import Section, SongAnalysis


def label_sections(
    raw_sections: list[tuple[float, float, float, float]],
) -> list[Section]:
    """Label a list of (start, end, energy_avg, energy_peak) tuples.

    Heuristic for v1:
    - First/last section → "intro"/"outro" only if its energy is *strictly* below
      the median, so a loud opener doesn't get labeled "intro".
    - Middle sections bucketed by energy into thirds: bottom → verse, top → chorus,
      mid → "pre-chorus" if it sits between a verse-like section and a chorus,
      otherwise "bridge".
    - With fewer than 3 middle sections we fall back to a top/bottom split.

    The labeler is intentionally crude — PRD §14.3 expects the artist to hand-edit
    `song-analysis.json` when needed.
    """
    if not raw_sections:
        return []

    n = len(raw_sections)
    energies = sorted(e for _, _, e, _ in raw_sections)
    median = energies[n // 2]

    intro_taken = raw_sections[0][2] < median
    outro_taken = n > 1 and raw_sections[-1][2] < median

    middle = list(range(n))
    if intro_taken:
        middle.remove(0)
    if outro_taken and (n - 1) in middle:
        middle.remove(n - 1)

    chorus_indices: set[int] = set()
    verse_indices: set[int] = set()
    mid_indices: set[int] = set()
    if middle:
        sorted_mid = sorted(middle, key=lambda i: raw_sections[i][2])
        m = len(sorted_mid)
        third = m // 3
        if third == 0:
            half = m // 2
            chorus_indices = set(sorted_mid[half:])
            verse_indices = set(sorted_mid[:half])
        else:
            verse_indices = set(sorted_mid[:third])
            chorus_indices = set(sorted_mid[m - third :])
            mid_indices = set(sorted_mid[third : m - third])

    verse_n = chorus_n = prechorus_n = bridge_n = 0
    last_label: str | None = None
    out: list[Section] = []

    for i, (start, end, energy_avg, energy_peak) in enumerate(raw_sections):
        if i == 0 and intro_taken:
            name = "intro"
            last_label = "intro"
        elif i == n - 1 and outro_taken:
            name = "outro"
            last_label = "outro"
        elif i in chorus_indices:
            chorus_n += 1
            name = f"chorus {chorus_n}"
            last_label = "chorus"
        elif i in verse_indices:
            verse_n += 1
            name = f"verse {verse_n}"
            last_label = "verse"
        elif i in mid_indices:
            next_is_chorus = (i + 1) in chorus_indices
            if next_is_chorus and last_label in {"intro", "verse"}:
                prechorus_n += 1
                name = f"pre-chorus {prechorus_n}"
                last_label = "pre-chorus"
            else:
                bridge_n += 1
                name = "bridge" if bridge_n == 1 else f"bridge {bridge_n}"
                last_label = "bridge"
        else:
            name = f"section {i + 1}"
            last_label = "section"

        out.append(
            Section(
                name=name,
                start=float(start),
                end=float(end),
                energy_avg=float(energy_avg),
                energy_peak=float(energy_peak),
            )
        )
    return out


def analyze_audio(audio_path: Path, audio_rel: str) -> SongAnalysis:
    """Run the librosa pipeline and produce a SongAnalysis.

    librosa is imported lazily so that core CLI startup doesn't pay its cost.
    """
    import librosa
    import numpy as np

    y, sr = librosa.load(str(audio_path), sr=None, mono=True)
    duration = float(librosa.get_duration(y=y, sr=sr))

    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    tempo_value = float(np.atleast_1d(tempo)[0])

    # Heuristic downbeats: every 4th beat. Madmom would do better; tracked as v2.
    downbeat_times = beat_times[::4] if len(beat_times) > 0 else np.array([])

    boundaries = _detect_section_boundaries(y, sr, duration)
    raw = _compute_section_energy(y, sr, boundaries)
    sections = label_sections(raw)

    return SongAnalysis(
        audio_file=audio_rel,
        duration_seconds=duration,
        tempo_bpm=round(tempo_value, 2),
        sections=sections,
        beat_grid_seconds=[round(float(t), 3) for t in beat_times],
        downbeat_seconds=[round(float(t), 3) for t in downbeat_times],
    )


def _detect_section_boundaries(y, sr, duration: float) -> list[float]:
    """Return a list of boundary times in seconds, including 0 and duration."""
    import librosa
    import numpy as np

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    features = np.vstack([chroma, mfcc])

    # Aim for ~7-9 sections in a typical pop song.
    target_k = max(4, min(9, int(duration / 25)))
    boundary_frames = librosa.segment.agglomerative(features, k=target_k)
    times = librosa.frames_to_time(boundary_frames, sr=sr)
    boundaries = [0.0, *[float(t) for t in times], duration]
    boundaries = sorted(set(round(b, 3) for b in boundaries))
    # Drop boundaries that produce sub-2-second sections — likely artifacts.
    cleaned = [boundaries[0]]
    for b in boundaries[1:]:
        if b - cleaned[-1] >= 2.0:
            cleaned.append(b)
    if cleaned[-1] != boundaries[-1]:
        cleaned.append(boundaries[-1])
    return cleaned


def _compute_section_energy(
    y, sr, boundaries: list[float]
) -> list[tuple[float, float, float, float]]:
    """Return [(start, end, energy_avg, energy_peak), ...] for each adjacent pair."""
    import librosa
    import numpy as np

    rms = librosa.feature.rms(y=y)[0]
    rms_times = librosa.times_like(rms, sr=sr)
    out: list[tuple[float, float, float, float]] = []
    for start, end in zip(boundaries[:-1], boundaries[1:], strict=False):
        mask = (rms_times >= start) & (rms_times < end)
        if not np.any(mask):
            avg = peak = 0.0
        else:
            window = rms[mask]
            avg = float(window.mean())
            peak = float(window.max())
        out.append((start, end, round(avg, 4), round(peak, 4)))
    return out
