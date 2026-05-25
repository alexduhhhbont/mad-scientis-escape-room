from dataclasses import dataclass


@dataclass
class FixtureChannel:
    offset: int
    name:   str
    role:   str   # one of CHANNEL_ROLES


@dataclass
class FixtureType:
    id:       str
    name:     str
    channels: list   # list[FixtureChannel]


@dataclass
class FixtureInstance:
    id:          int
    name:        str
    type_id:     str
    dmx_address: int   # 1-indexed base channel
