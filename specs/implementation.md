# MOZA Vehicle Controls: behavior and implementation

Describes the exported implementation **0.2.0**. The linked source and metadata define this version; gameplay qualification is a separate requirement.

## Behavior

A Python helper reads calibrated MOZA wheel and SIMSONN pedal inputs through OS interfaces, then publishes bounded versioned packets to the native consumer. wheel.py lists devices, calibrates and runs the selected device set; Windows uses its dedicated input adapter. While driving, Vehicle Control Framework arbitrates steering, forward/reverse/brake and boost against assists. Stale/invalid helper data falls back instead of holding an old command.

## State and lifecycle

Calibration/preferences are helper files; packets and native device state are temporary. The native consumer owns no vehicle save data. Focus, active local driver and valid packet/session checks admit proposals. Neutral wheel traffic remains a hardware fallback and does not alone cancel GPS/Edge Cruise; meaningful manual input takes over.

## Integration and configuration

Runtime dependencies: [vehicle-control-framework](https://github.com/swooping-mods/vehicle-control-framework).

The [module metadata](../source/mods/wheel-control/mod.json) owns the version and declared integration contract. Native modules start at `MoonLab_ModStart`. Game/Unity integrations target the pinned Steam Windows x64 IL2CPP build.

| Service | ABI | Table size |
|---|---:|---|
| Requires `vehicle-control-framework.controls` | 1 | at least 72 bytes |

## Implementation sources

- [mod.c](../source/mods/wheel-control/mod.c)
- [input_core.h](../source/mods/wheel-control/input_core.h)
- [wheel.py](../source/mods/wheel-control/wheel.py)
- [windows_input.py](../source/mods/wheel-control/windows_input.py)

## Verification boundary

Requires actual compatible hardware and existing Python/OS support. No bundled Python/Qt runtime or guaranteed force feedback. Simulated packets/build checks do not qualify physical calibration, pedal direction or real driving.

`python3 build.py --check` verifies the exported source hashes. It does not execute the mod or qualify the behaviors above. Installation and independent build prerequisites are in the [README](../README.md).
