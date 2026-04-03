"""
Generate sounds/chime.wav — a short dramatic bell/horn tone.

Uses only Python's standard library (math + wave).
Run this once before first launch, or via: python setup.py
"""
import math
import os
import struct
import wave


OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "chime.wav")

SAMPLE_RATE = 44100
DURATION    = 1.8   # seconds


def _make_samples(sample_rate: int, duration: float) -> list[int]:
    """
    Generate a multi-harmonic bell tone with exponential decay.
    Fundamental: 392 Hz (G4) — dark and resonant.
    """
    samples = []
    n_samples = int(sample_rate * duration)

    for i in range(n_samples):
        t = i / sample_rate

        # Three harmonics with different decay rates for a bell-like timbre
        h1 = 0.55 * math.sin(2 * math.pi * 392.0 * t) * math.exp(-2.5 * t)
        h2 = 0.30 * math.sin(2 * math.pi * 784.0 * t) * math.exp(-3.5 * t)
        h3 = 0.15 * math.sin(2 * math.pi * 1176.0 * t) * math.exp(-5.0 * t)

        # Brief attack envelope (first 5 ms)
        attack = min(1.0, t / 0.005)

        sample = (h1 + h2 + h3) * attack
        samples.append(int(max(-32767, min(32767, sample * 32767))))

    return samples


def generate(output_path: str = OUTPUT_PATH):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    samples = _make_samples(SAMPLE_RATE, DURATION)

    with wave.open(output_path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)   # 16-bit
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))

    print(f"Generated: {output_path}  ({DURATION}s, {SAMPLE_RATE} Hz, 16-bit mono)")


if __name__ == "__main__":
    generate()
