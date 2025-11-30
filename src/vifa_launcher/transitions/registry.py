# SPDX-License-Identifier: GPL-3.0-or-later
#
# VIfA-Launcher - Visual Interface for Applications
# Copyright (C) 2025 Tasteron
#
# This project is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#
from __future__ import annotations
from typing import Callable, Dict, Optional, Type, Any
import os, pkgutil, importlib, inspect

_StrategyFactory = Callable[[], Any]
_DEBUG = os.environ.get("VIFA_LAUNCHER_PLUGIN_DEBUG") == "1"

def _dbg(msg: str):
    if _DEBUG:
        print(f"[registry] {msg}")

class NoopStrategy:
    NAME = "none"

    def start(self, stack, index: int, duration_ms: int):
        from PyQt5.QtCore import QObject, pyqtSignal, QTimer
        class _DummyAnim(QObject):
            finished = pyqtSignal()
            def start(self): QTimer.singleShot(0, self.finished.emit)
        stack.setCurrentIndex(index)
        return _DummyAnim(stack)

class _Registry:
    def __init__(self):
        self._factories: Dict[str, _StrategyFactory | Type] = {}
        self._instances: Dict[str, Any] = {}
        self._autodiscovered: bool = False

    def register(self, name: str, factory_or_class: _StrategyFactory | Type) -> None:
        key = (name or "").strip().lower()
        if not key:
            raise ValueError("Transition name must not be empty.")
        self._factories[key] = factory_or_class
        self._instances.pop(key, None)

    def _get_or_create(self, key: str) -> Any:
        if key in self._instances:
            return self._instances[key]
        factory = self._factories[key]
        inst = factory() if (callable(factory) and not isinstance(factory, type)) else factory()
        self._instances[key] = inst
        return inst

    def _is_concrete_strategy_class(self, cls: Type, mod_name: str) -> bool:
        if getattr(cls, "__module__", None) != mod_name: return False
        if not inspect.isclass(cls): return False
        if inspect.isabstract(cls): return False
        if not hasattr(cls, "start") or not callable(getattr(cls, "start")): return False
        start = getattr(cls, "start")
        if getattr(start, "__isabstractmethod__", False): return False
        return True

    def _register_from_module(self, mod, key_hint: Optional[str] = None) -> bool:
        mod_name = mod.__name__; key_l = (key_hint or "").strip().lower()
        candidates = []
        for attr, obj in vars(mod).items():
            if not self._is_concrete_strategy_class(obj, mod_name): continue
            an = attr.lower(); score = 0
            if key_l and key_l in an: score += 20
            if an.endswith("strategy"): score += 10
            if "transition" in an: score += 5
            candidates.append((score, attr, obj))
        if not candidates: return False
        candidates.sort(key=lambda t: (-t[0], t[1]))
        _, attr, cls = candidates[0]
        name = None
        for k in ("NAME", "name", "ID", "id"):
            if hasattr(cls, k): name = str(getattr(cls, k)); break
        if not name: name = (key_hint or mod_name.rsplit(".", 1)[-1])
        self.register(name.strip().lower(), cls)
        return True

    def _register_builtin(self, key: str, module_names: list[str]) -> None:
        if key in self._factories: return
        for modname in module_names:
            try:
                mod = importlib.import_module(modname)
                if self._register_from_module(mod, key_hint=key):
                    return
            except Exception as e:
                _dbg(f"Builtin '{key}' not loadable: {e}")

    def _maybe_autodiscover(self):
        if self._autodiscovered: return
        self._register_builtin("slide", ["vifa_launcher.transitions.slide"])
        self._register_builtin("fade", ["vifa_launcher.transitions.fade"])
        pkg_name = __name__.rsplit(".", 1)[0] + ".plugins"
        try:
            pkg = importlib.import_module(pkg_name)
            for _, modname, ispkg in pkgutil.iter_modules(getattr(pkg, "__path__", []), pkg.__name__ + "."):
                if ispkg: continue
                try:
                    mod = importlib.import_module(modname)
                    self._register_from_module(mod, key_hint=modname.rsplit(".", 1)[-1])
                except Exception as e:
                    _dbg(f"Plugin import error {modname}: {e}")
        except Exception as e:
            _dbg(f"No plugin package: {e}")
        self._autodiscovered = True

    def get(self, name: str) -> Any:
        self._maybe_autodiscover()
        key = (name or "").strip().lower() or "slide"
        if key == "none": return NoopStrategy()
        if key in self._factories: return self._get_or_create(key)
        for cand in ("slide", "fade"):
            if cand in self._factories: return self._get_or_create(cand)
        return NoopStrategy()

    def names(self) -> list[str]:
        self._maybe_autodiscover()
        names = sorted(self._factories.keys())
        if "none" not in names: names = ["none"] + names
        return names

registry = _Registry()

def register(name: str, factory_or_class: _StrategyFactory | Type) -> None:
    registry.register(name, factory_or_class)

