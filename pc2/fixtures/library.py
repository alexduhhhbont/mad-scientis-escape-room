import json
import threading
from typing import Optional

from pc2.config import FIXTURES_FILE
from pc2.fixtures.models import FixtureChannel, FixtureType, FixtureInstance


_DEFAULT_FIXTURE_DATA = {
    "types": [
        {
            "id": "party-led-rgbw",
            "name": "RGBW Party LED",
            "channels": [
                {"offset": 0, "name": "Red",        "role": "red"},
                {"offset": 1, "name": "Green",      "role": "green"},
                {"offset": 2, "name": "Blue",       "role": "blue"},
                {"offset": 3, "name": "White",      "role": "white"},
                {"offset": 4, "name": "Brightness", "role": "intensity"},
                {"offset": 5, "name": "Strobe",     "role": "strobe"},
            ],
        },
        {
            "id": "eurolite-rgb",
            "name": "Eurolite LED PARty RGB Spot",
            "channels": [
                {"offset": 0, "name": "Red",    "role": "red"},
                {"offset": 1, "name": "Green",  "role": "green"},
                {"offset": 2, "name": "Blue",   "role": "blue"},
                {"offset": 3, "name": "Dimmer", "role": "intensity"},
                {"offset": 4, "name": "Strobe", "role": "strobe"},
            ],
        },
    ],
    "instances": [
        {"id": 1, "name": "Fixture 1", "type_id": "party-led-rgbw", "dmx_address":  1},
        {"id": 2, "name": "Fixture 2", "type_id": "party-led-rgbw", "dmx_address":  7},
        {"id": 3, "name": "Fixture 3", "type_id": "party-led-rgbw", "dmx_address": 13},
        {"id": 4, "name": "Fixture 4", "type_id": "party-led-rgbw", "dmx_address": 19},
        {"id": 5, "name": "Fixture 5", "type_id": "eurolite-rgb",   "dmx_address": 25},
        {"id": 6, "name": "Fixture 6", "type_id": "eurolite-rgb",   "dmx_address": 30},
        {"id": 7, "name": "Fixture 7", "type_id": "eurolite-rgb",   "dmx_address": 35},
        {"id": 8, "name": "Fixture 8", "type_id": "eurolite-rgb",   "dmx_address": 40},
    ],
}


class FixtureLibrary:
    def __init__(self):
        self._lock = threading.Lock()
        self.types:     list = []
        self.instances: list = []
        self._load()

    def _parse(self, data: dict):
        self.types = [
            FixtureType(
                id=t["id"], name=t["name"],
                channels=[FixtureChannel(**ch) for ch in t["channels"]],
            )
            for t in data.get("types", [])
        ]
        self.instances = [
            FixtureInstance(**inst) for inst in data.get("instances", [])
        ]

    def _to_dict(self) -> dict:
        return {
            "types": [
                {
                    "id": t.id, "name": t.name,
                    "channels": [
                        {"offset": ch.offset, "name": ch.name, "role": ch.role}
                        for ch in t.channels
                    ],
                }
                for t in self.types
            ],
            "instances": [
                {
                    "id": i.id, "name": i.name,
                    "type_id": i.type_id, "dmx_address": i.dmx_address,
                }
                for i in self.instances
            ],
        }

    def _load(self):
        if FIXTURES_FILE.exists():
            try:
                self._parse(json.loads(FIXTURES_FILE.read_text()))
                return
            except Exception:
                pass
        self._parse(_DEFAULT_FIXTURE_DATA)
        self._save()

    def _save(self):
        FIXTURES_FILE.write_text(json.dumps(self._to_dict(), indent=2))

    def get_type(self, type_id: str) -> Optional[FixtureType]:
        with self._lock:
            return next((t for t in self.types if t.id == type_id), None)

    def get_instance(self, inst_id: int) -> Optional[FixtureInstance]:
        with self._lock:
            return next((i for i in self.instances if i.id == inst_id), None)

    def get_types_snapshot(self) -> list:
        with self._lock:
            return list(self.types)

    def get_instances_snapshot(self) -> list:
        with self._lock:
            return list(self.instances)

    def get_role_offsets(self, type_id: str) -> dict:
        ft = self.get_type(type_id)
        return {ch.role: ch.offset for ch in ft.channels} if ft else {}

    def next_instance_id(self) -> int:
        with self._lock:
            return max((i.id for i in self.instances), default=0) + 1

    def add_type(self, ft: FixtureType):
        with self._lock:
            self.types.append(ft)
            self._save()

    def update_type(self, ft: FixtureType):
        with self._lock:
            for i, t in enumerate(self.types):
                if t.id == ft.id:
                    self.types[i] = ft
                    break
            self._save()

    def delete_type(self, type_id: str):
        with self._lock:
            self.types = [t for t in self.types if t.id != type_id]
            self._save()

    def add_instance(self, inst: FixtureInstance):
        with self._lock:
            self.instances.append(inst)
            self._save()

    def update_instance(self, inst: FixtureInstance):
        with self._lock:
            for i, existing in enumerate(self.instances):
                if existing.id == inst.id:
                    self.instances[i] = inst
                    break
            self._save()

    def delete_instance(self, inst_id: int):
        with self._lock:
            self.instances = [i for i in self.instances if i.id != inst_id]
            self._save()


fixture_library = FixtureLibrary()
