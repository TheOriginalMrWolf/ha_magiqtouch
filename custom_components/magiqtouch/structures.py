import json
import dataclasses
from dataclasses import dataclass, field, fields, is_dataclass

import logging

_LOGGER = logging.getLogger("magiqtouch")


def dataclass_from_dict(klass, d, show_errors=False):
    # https://stackoverflow.com/a/54769644
    try:
        fieldtypes = {f.name: f.type for f in dataclasses.fields(klass)}
        return klass(**{f: dataclass_from_dict(fieldtypes[f], d[f]) for f in d})
    except KeyError:
        raise
    except:
        # if type(klass) == Optional:
        # print(klass, type(klass), klass.__dict__)
        if show_errors or (isinstance(d, dict) and "MacAddressId" in d):
            print(klass, d)
            raise
        return d  # Not a dataclass fieldtypes


def flatten_dict(data, sep="_", parent_key="", result=None):
    """
    Flattens a nested dictionary into a single level dictionary.

    Args:
        data: The nested dictionary to flatten.
        sep: The separator to use when concatenating keys (default: "_").
        parent_key: The parent key for the current level (default: "").
        result: An optional dictionary to store the flattened data (default: None).

    Returns:
        A dictionary with flattened key-value pairs.
    """
    if result is None:
        result = {}
    for key, value in data.items():
        combined_key = parent_key + sep + key if parent_key else key
        if isinstance(value, dict):
            flatten_dict(value, sep, combined_key, result)
        else:
            result[combined_key] = value
    return result


@dataclass
class Zone:
    Name: str
    Type: str
    CoolerCompatible: bool
    HeaterCompatible: bool


@dataclass
class AOC:
    InSystem: bool
    MaximumTemperature: int
    MinimumTemperature: int


@dataclass
class Cabinet:
    CabinetSerialNo: int
    CoolerCabinetSoftRev: str
    ElectronicsSerialNo: str
    ModelNumber: str


@dataclass
class EVAPCoolerDef:
    Brands: int
    HumidityControl: bool
    MaximumTemperature: int
    MinimumTemperature: int
    TemperatureUnits: int


@dataclass
class WallControllerDef:
    Firmware: str
    Type: int


@dataclass
class HeaterDef:
    InSystem: bool
    FixedFan: bool
    Brands: int
    DataTableVersion: str
    ICSSoftwareRev: str
    MaxSetFanSpeed: int
    MaximumTemperature: int
    MinimumTemperature: int
    ModelNo: str
    SerialNo: int


@dataclass
class SystemDevice:
    available: bool
    fanFixed: bool


@dataclass
class SystemDef:
    configuration: int
    cooler: SystemDevice
    heater: SystemDevice
    fan: SystemDevice
    Address: str
    Name: str


@dataclass
class WifiModuleDef:
    MacAddressId: str = ""
    version: str = ""
    type: str = ""


@dataclass
class ACZonesDef:
    Manual: bool
    SlaveWallControls: bool
    Zones: list[Zone]


@dataclass
class SystemDetails:
    ACZones: ACZonesDef = None
    AOCFixed: AOC = None
    AOCInverter: AOC = None
    Cabinets: list[Cabinet] = field(default_factory=list)
    EVAPCooler: EVAPCoolerDef = None
    WallController: WallControllerDef = None
    Heater: HeaterDef = None
    MasterAirSensorPresent: bool = False
    SlaveWallControls: int = 0
    NoOfZoneControls: int = 0
    System: SystemDef = None
    Wifi_Module: WifiModuleDef = None  # field(default_factory=WifiModuleDef)
    ExternalAirSensorPresent: bool = False
    DamperDelayModulePresent: bool = False
    BMSS1: bool = False
    BMSMS1: bool = False
    ZoneAirSensors: int = 0

    def __str__(self):
        # report as valid json in logs
        return json.dumps(self.to_dict())

    def to_dict(self):
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data):
        dc = dataclass_from_dict(cls, data, True)
        dc.ACZones.Zones = [Zone(**d) for d in dc.ACZones.Zones]
        dc.Cabinets = [Cabinet(**d) for d in dc.Cabinets]
        return dc


################
# Remote Status
################
@dataclass
class UnitDetails:
    brand: int = 0
    name: str = ""
    runningState: str = ""
    zoneRunningState: str = ""
    zoneOn: bool = False
    zoneType: str = ""
    set_temp: float = 0.0
    temperature_units: str = ""
    actual_temp: float = 0.0
    max_temp: float = 0.0
    min_temp: float = 0.0
    fan_speed: int = 0
    max_fan_speed: int = 0
    min_fan_speed: int = 0
    control_mode: str = ""
    control_mode_type: str = ""
    internal_temp: float = 0.0
    external_temp: float = None
    programMode: str = ""
    ProgramModeOverridden: bool = False
    ProgramPeriodActive: bool = False
    programOverrideDisabled: bool = False



@dataclass
class Fan:
    cooler_available: bool = False
    cooler_brand: int = 0
    heater_available: bool = False
    heater_brand: int = 0
    heater_Fan_Speed: int = 0
    cooler_Fan_Speed: int = 0


@dataclass
class Installed:
    evap: bool = False
    faoc: bool = False
    heater: bool = False
    iaoc: bool = False
    coolerType: int = 0


@dataclass
class RemoteStatus:
    device: str = ""
    timestamp: int = 0
    online: bool = False
    systemOn: bool = False
    runningMode: str = ""
    heaterFault: bool = False
    coolerFault: bool = False
    cooler: list[UnitDetails] = field(default_factory=list)
    heater: list[UnitDetails] = field(default_factory=list)
    fan: Fan = field(default_factory=Fan)
    touchCount: int = 0
    installed: Installed = field(default_factory=Installed)

    def update(self, other: "RemoteStatus"):
        # Log the contents of 'other' as JSON
        try:
            _LOGGER.debug("RemoteStatus.update - other: %s", json.dumps(dataclasses.asdict(other)))
        except Exception as e:
            _LOGGER.error("RemoteStatus.update - error serializing 'other': %s", e)

        # Log the list of all RemoteStatus fields
        field_names = [f.name for f in fields(RemoteStatus)]
        _LOGGER.debug("RemoteStatus fields: %s", field_names)

        for fld in fields(RemoteStatus):
            current = getattr(self, fld.name)
            new = getattr(other, fld.name)
            if is_dataclass(fld.type):
                for k, v in new.__dict__.items():
                    setattr(current, k, v)
            elif fld.name in ("cooler", "heater"):
                # try:
                #     _LOGGER.debug("\nupdate - current: %s\n", json.dumps([dataclasses.asdict(u) for u in current]))
                #     _LOGGER.debug("update - new: %s\n", json.dumps([dataclasses.asdict(u) for u in new]))
                # except Exception as e:
                #     _LOGGER.error("update - error logging current/new: %s", e)

                # Extend current list if new has more items
                if len(current) < len(new):
                    _data_to_add = [dataclasses.replace(unit) for unit in new[len(current):]]
                    _LOGGER.debug("update - extending current with: %s\n", json.dumps([dataclasses.asdict(u) for u in _data_to_add]))
                    current.extend(_data_to_add)
                for i, unit in enumerate(new):
                    cu = current[i]
                    if cu.zoneType != unit.zoneType or cu.name != unit.name:
                        raise ValueError(f"units out of order\n{self}\n{other}")
                    for k, v in dataclasses.asdict(unit).items():
                        setattr(current[i], k, v)
            else:
                setattr(self, fld.name, new)

    def __str__(self):
        # report as valid json in logs
        return json.dumps(self.to_dict())

    def to_dict(self):
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data):
        dc = dataclass_from_dict(cls, data)
        dc.cooler = [UnitDetails(**c) for c in dc.cooler]
        dc.heater = [UnitDetails(**h) for h in dc.heater]
        return dc

    def __eq__(self, other):
        if not isinstance(other, RemoteStatus):
            return False
        s = flatten_dict(dataclasses.asdict(self))
        o = flatten_dict(dataclasses.asdict(other))

        _LOGGER.debug(f"Object equality test:\nself:\n{s}\nother:\n{o}\n")
        for key in list(s.keys()):
            if key.lower() in ("timestamp", "touchcount"):
                s.pop(key)
                o.pop(key)
        return s == o
