"""Замер генерации пикселей без Tkinter и без заполнения таблицы шагов."""

import argparse
from datetime import datetime, timezone
import gc
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
from time import perf_counter_ns

from raster import ALGORITHMS, bresenham_circle


def measure(loops=40, repeats=5):
    if loops < 1 or repeats < 1:
        raise ValueError("Число повторов должно быть положительным")
    rows = []
    for name, function in ALGORITHMS.items():
        circle = function is bresenham_circle
        for size in ((40, 200, 400) if circle else (100, 500, 1000)):
            if circle:
                cases = [(0, 0, size)]
            else:
                short = size * 2 // 5
                cases = [(0, 0, x, y) for x, y in (
                    (size, short), (short, size), (-short, size), (-size, short),
                    (-size, -short), (-short, -size), (short, -size), (size, -short))]
            counts = [len(function(*case)) for case in cases]  # Прогрев и объём выхода.
            samples = []
            for _ in range(repeats):
                gc_was_enabled = gc.isenabled()
                gc.disable()
                try:
                    start = perf_counter_ns()
                    for _ in range(loops):
                        for case in cases:
                            function(*case)
                    elapsed = perf_counter_ns() - start
                finally:
                    if gc_was_enabled:
                        gc.enable()
                samples.append(elapsed / (loops * len(cases)) / 1000)
            average_count = statistics.mean(counts)
            median = statistics.median(samples)
            rows.append({"algorithm": name, "kind": "radius" if circle else "length", "size": size,
                         "calls_per_repeat": loops * len(cases), "pixels_per_call": average_count,
                         "median_us": median, "min_us": min(samples), "max_us": max(samples),
                         "ns_per_pixel": median * 1000 / average_count})
    cpu = platform.processor() or platform.machine()
    if sys.platform == "darwin":
        try:
            cpu = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"],
                                          text=True, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            pass  # Название процессора не влияет на замер.
    return {"measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "python": sys.version.split()[0], "system": platform.system(), "machine": platform.machine(),
            "cpu": cpu, "clock": "perf_counter_ns", "loops": loops, "repeats": repeats,
            "description": "Генерация списка Pixel без trace и GUI; GC отключён внутри замеров.",
            "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loops", type=int, default=40)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("benchmark_results.json"))
    args = parser.parse_args()
    data = measure(args.loops, args.repeats)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for row in data["rows"]:
        print(f'{row["algorithm"]:25} {row["size"]:4}  {row["median_us"]:9.2f} мкс')
    print("Результаты:", args.output)


if __name__ == "__main__":
    main()
