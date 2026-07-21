"""Köprü dönüşümü: doğrudan rotası olmayan hedefe ara format üzerinden (heic→png→pdf)."""

import os
import tempfile
from pathlib import Path

from .base import ConversionRoute, all_routes, group_index

# Eşit uzunluktaki yollar arasında tercih edilen ara formatlar (kayıpsız olanlar önce).
_INTERMEDIATE_PREFERENCE = (".png", ".json", ".wav", ".mp4", ".csv", ".txt", ".html", ".jpg")


def _graph() -> dict[str, list[ConversionRoute]]:
    """Kaynak uzantı → o uzantıdan çıkan rotalar."""
    graph: dict[str, list[ConversionRoute]] = {}
    for route in all_routes():
        graph.setdefault(route.source_ext, []).append(route)
    return graph


def _best_chain(chains: list[list[ConversionRoute]]) -> list[ConversionRoute]:
    """Aynı uzunluktaki adaylar arasından ara-format tercihine göre birini seçer."""
    def rank(chain: list[ConversionRoute]) -> tuple:
        if len(chain) < 2:
            return (0, "")
        inter = chain[0].target_ext
        pref = (_INTERMEDIATE_PREFERENCE.index(inter)
                if inter in _INTERMEDIATE_PREFERENCE else len(_INTERMEDIATE_PREFERENCE))
        return (pref, inter)
    return min(chains, key=rank)


def find_chain(source_ext: str, target_ext: str,
               max_steps: int = 2) -> list[ConversionRoute] | None:
    """`source_ext`'ten `target_ext`'e en kısa rota zincirini (BFS) döner.
    Ara adımlar multi_output olamaz; son adım serbest. Yol yoksa None."""
    source_ext = source_ext.lower()
    target_ext = target_ext.lower()
    if source_ext == target_ext:
        return None

    graph = _graph()
    frontier: list[tuple[str, list[ConversionRoute]]] = [(source_ext, [])]
    visited = {source_ext}

    for _ in range(max_steps):
        complete: list[list[ConversionRoute]] = []
        next_frontier: list[tuple[str, list[ConversionRoute]]] = []
        next_visited: set[str] = set()
        for current, path in frontier:
            for route in graph.get(current, []):
                new_path = path + [route]
                if route.target_ext == target_ext:
                    complete.append(new_path)
                elif (not route.multi_output
                      and route.target_ext not in visited
                      and route.target_ext not in next_visited):
                    next_frontier.append((route.target_ext, new_path))
                    next_visited.add(route.target_ext)
        if complete:
            return _best_chain(complete)
        visited |= next_visited
        frontier = next_frontier
    return None


def make_composite(chain: list[ConversionRoute]) -> ConversionRoute:
    """Bir rota zincirini tek bir birleşik ConversionRoute'a sarar. Ara adımlar
    geçici dosyalara yazılır, son adım hedefe; geçiciler sonrasında silinir."""
    source_ext = chain[0].source_ext
    target_ext = chain[-1].target_ext
    via = tuple(r.target_ext for r in chain[:-1])
    requires = next((r.requires for r in chain if r.requires is not None), None)

    def convert(src: Path, dst: Path) -> None:
        current = src
        temps: list[Path] = []
        try:
            for i, route in enumerate(chain):
                if i == len(chain) - 1:
                    out = dst
                else:
                    fd, tmp = tempfile.mkstemp(suffix=route.target_ext)
                    os.close(fd)
                    out = Path(tmp)
                    temps.append(out)
                route.convert(current, out)
                current = out
        finally:
            for tmp in temps:
                tmp.unlink(missing_ok=True)

    return ConversionRoute(
        source_ext=source_ext,
        target_ext=target_ext,
        label=chain[-1].label,
        convert=convert,
        requires=requires,
        multi_output=chain[-1].multi_output,
        via=via,
    )


def bridged_routes_for(source_ext: str, max_steps: int = 2) -> list[ConversionRoute]:
    """İnteraktif menü için: `source_ext`'ten tam 2 adımda ulaşılabilen ama
    doğrudan rotası olmayan her hedef için sentetik köprü rotası üretir."""
    source_ext = source_ext.lower()
    direct_targets = {r.target_ext for r in all_routes() if r.source_ext == source_ext}
    graph = _graph()

    chains_by_target: dict[str, list[list[ConversionRoute]]] = {}
    for first in graph.get(source_ext, []):
        if first.multi_output:  # ara adım çoklu çıktı olamaz
            continue
        for second in graph.get(first.target_ext, []):
            target = second.target_ext
            if target == source_ext or target in direct_targets:
                continue
            chains_by_target.setdefault(target, []).append([first, second])

    return [
        make_composite(_best_chain(chains))
        for target, chains in sorted(
            chains_by_target.items(), key=lambda kv: (group_index(kv[0]), kv[0])
        )
    ]
