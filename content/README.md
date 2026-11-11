# MOZA Vehicle Controls

R9 / KS Pro steering and separate Simsonn Pro pedals for vehicles.

## Install

Install [Moon Sweepers Mod Loader](https://github.com/swooping-mods/moon-sweepers-mod-loader) first.

Download [wheel-control-0.2.0.msmod](content/wheel-control-0.2.0.msmod), import it with **Install mod package**, then select the mod and its required frameworks.

Required mods: [vehicle-control-framework](https://github.com/swooping-mods/vehicle-control-framework).

## Controls

- Run the calibrated wheel.py helper for your R9 + KS Pro and Simsonn Pro pedals.
- Board a vehicle normally. The wheel controls steering; pedals control forward and reverse/brake.

Run `python3 content/wheel.py list` to find the wheel and pedal devices, then calibrate them before enabling vehicle input.

## Compatibility

Version 0.2.0. Targets the pinned Steam Windows x64 IL2CPP build of Moon Sweepers (Steam app 5335510). On Linux, the game runs through Proton. Experimental: back up saves before using save-affecting mods.

## Build

Run `python3 build.py --check` to verify source hashes, then `python3 build.py` to write a build under `.local/build/`. Requires installed Clang, lld-link and llvm-dlltool.

## Credits

See [CREDITS.txt](CREDITS.txt) and [third-party notices](vendored/THIRD_PARTY_NOTICES.md).
