# MOZA Vehicle Controls

<img src="media/icon.png" alt="MOZA Vehicle Controls icon" width="128" height="128">

R9 / KS Pro steering and separate Simsonn Pro pedals for vehicles.

## Install

Install [Moon Sweepers Mod Loader](https://github.com/swooping-mods/moon-sweepers-mod-loader) first.

Download [wheel-control-0.2.0.msmod](content/wheel-control-0.2.0.msmod), then drag and drop the `.msmod` file onto the [Moon Sweepers Mod Loader](https://github.com/swooping-mods/moon-sweepers-mod-loader) window. You can also use **Add mods…** (older loader builds: **Install mod package**).

Select the mod and its required frameworks, click **Prepare files**, then **Launch**.

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
