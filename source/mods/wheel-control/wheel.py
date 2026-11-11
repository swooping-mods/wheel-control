#!/usr/bin/env python3
"""Windows/Linux R9 / KS Pro + Simsonn Pro helper. Starts no game; stdlib only."""
import argparse
import json
import math
import os
from pathlib import Path
import signal
import struct
import time
from contextlib import contextmanager

if os.name != 'nt':
    import fcntl

EVENT = struct.Struct('<IhBB')
PACKET = struct.Struct('<IIQffII')
ACTIONS = {'handbrake': 1, 'boost': 2, 'lights': 4, 'cleaning': 8, 'exit': 16}
FILETIME_EPOCH = 116444736000000000


class Joystick:
    def __init__(self, path):
        self.path = str(Path(path).resolve(strict=True))
        self.fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK)
        self.axes, self.buttons = {}, {}
        try:
            buf = bytearray(128)
            fcntl.ioctl(self.fd, 0x80806a13, buf)  # JSIOCGNAME(128)
            self.name = buf.split(b'\0')[0].decode(errors='replace')
        except BaseException:
            self.close()
            raise

    def poll(self):
        for _ in range(4096):
            try:
                data = os.read(self.fd, EVENT.size)
            except BlockingIOError:
                return
            if len(data) != EVENT.size:
                raise OSError('Joystick disconnected: ' + self.path)
            _, value, kind, number = EVENT.unpack(data)
            kind &= 0x7f  # Initial-state records are required for stationary axes.
            if kind == 2:
                self.axes[number] = value
            elif kind == 1:
                self.buttons[number] = bool(value)
        raise OSError('Joystick event backlog exceeded the bounded poll')

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


LinuxJoystick = Joystick
if os.name == 'nt':
    from windows_input import Joystick


@contextmanager
def output_lock(path):
    with path.open('a+b') as handle:
        handle.seek(0, os.SEEK_END)
        if not handle.tell():
            handle.write(b'\0');handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def validate(profile):
    if profile.get('schema') != 'moon-wheel-profile/v1':
        raise ValueError('Unsupported wheel profile')
    for name in ('wheel', 'pedals'):
        if not isinstance(profile.get(name), str) or not profile[name]:
            raise ValueError('Missing device: ' + name)
    if profile['wheel'] == profile['pedals']:
        raise ValueError('Select the separate R9 and Simsonn devices')
    for name in ('steer', 'accelerator', 'brake'):
        a = profile[name]
        if type(a['axis']) is not int or not 0 <= a['axis'] <= 255:
            raise ValueError('Invalid axis index')
        keys = ('left', 'center', 'right') if name == 'steer' else ('rest', 'full')
        for key in keys:
            if type(a[key]) not in (int, float) or not math.isfinite(a[key]) or not -32768 <= a[key] <= 32767:
                raise ValueError('Invalid calibration endpoint')
        if name == 'steer':
            if not min(a['left'], a['right']) < a['center'] < max(a['left'], a['right']):
                raise ValueError('Center must lie between steering endpoints')
        elif abs(a['full'] - a['rest']) < 100:
            raise ValueError('Pedal calibration travel is too small')
        if not 0 <= a.get('deadzone', .03) < .5:
            raise ValueError('Invalid deadzone')
    if profile['accelerator']['axis'] == profile['brake']['axis']:
        raise ValueError('Simsonn accelerator and brake need separate axes')
    buttons = profile['buttons']
    if set(buttons) != set(ACTIONS):
        raise ValueError('Profile must describe each vehicle button action')
    selected = [n for n in buttons.values() if n is not None]
    if any(type(n) is not int or not 0 <= n <= 255 for n in selected) or len(selected) != len(set(selected)):
        raise ValueError('Buttons must be distinct zero-based device indices, or null')
    return profile


def pedal(raw, a):
    value = max(0., min(1., (raw-a['rest'])/(a['full']-a['rest'])))
    dead = a.get('deadzone', .03)
    return max(0., (value-dead)/(1-dead))


def steering(raw, a):
    right = (raw-a['center']) * (a['right']-a['center']) >= 0
    endpoint = a['right'] if right else a['left']
    value = min(1., abs((raw-a['center'])/(endpoint-a['center'])))
    dead = a.get('deadzone', .02)
    return max(0., (value-dead)/(1-dead)) * (1 if right else -1)


class Mapper:
    def __init__(self, profile):
        self.p = validate(profile)
        self.armed = False

    def sample(self, wheel, pedals):
        p = self.p
        required = (p['accelerator']['axis'], p['brake']['axis'])
        if p['steer']['axis'] not in wheel.axes or any(i not in pedals.axes for i in required):
            self.armed = False
            return 0., 0., 0, False
        gas = pedal(pedals.axes[required[0]], p['accelerator'])
        brake = pedal(pedals.axes[required[1]], p['brake'])
        if not self.armed:
            self.armed = gas <= .02 and brake <= .02 and not any(wheel.buttons.get(n, False) for n in p['buttons'].values() if n is not None)
        if not self.armed:
            return 0., 0., 0, False
        buttons = sum(bit for name, bit in ACTIONS.items() if wheel.buttons.get(p['buttons'][name], False))
        # Brake has priority when both pedals are pressed. Negative throttle is
        # the game's ordinary reverse/braking input, not a new gearbox model.
        throttle = -brake if brake > 0 else gas
        if buttons & 1:
            throttle = 0.
        return steering(wheel.axes[p['steer']['axis']], p['steer']), throttle, buttons, True


def packet(sample, now_ns=None):
    steer, throttle, buttons, enabled = sample
    stamp = (time.time_ns() if now_ns is None else now_ns)//100 + FILETIME_EPOCH
    return PACKET.pack(0x314c4857, 1, stamp, steer, throttle, buttons, int(enabled))


def publish(output, sample):
    tmp = output.with_name(output.name + '.tmp')
    if output.is_symlink() or tmp.is_symlink():
        raise ValueError('Refusing a symlink state file')
    tmp.write_bytes(packet(sample))
    os.replace(tmp, output)


def snapshot(device, prompt):
    input(prompt + ' Then press Enter here. ')
    device.poll()
    return dict(device.axes)


def moved(before, after):
    choices = [(abs(v-before.get(i, v)), i) for i, v in after.items()]
    if not choices or max(choices)[0] < 100:
        raise ValueError('No clear axis movement; repeat calibration')
    return max(choices)[1]


def calibrate(args):
    wheel, pedals = Joystick(args.wheel), None
    try:
        pedals = Joystick(args.pedals)
        center = snapshot(wheel, 'Center the wheel')
        left = snapshot(wheel, 'Turn to your desired full-left steering point')
        axis = moved(center, left)
        right = snapshot(wheel, 'Turn to your desired full-right steering point')
        profile = {'schema': 'moon-wheel-profile/v1', 'wheel': args.wheel, 'pedals': args.pedals,
                   'wheel_name': wheel.name, 'pedals_name': pedals.name,
                   'steer': {'axis': axis, 'left': left[axis], 'center': center[axis], 'right': right[axis], 'deadzone': .02},
                   'buttons': {name: None for name in ACTIONS}}
        for name in ('accelerator', 'brake'):
            rest = snapshot(pedals, 'Release ALL pedals')
            full = snapshot(pedals, 'Hold only the ' + name + ' at your comfortable maximum')
            index = moved(rest, full)
            profile[name] = {'axis': index, 'rest': rest[index], 'full': full[index], 'deadzone': .03}
        print('Bind actual device button indices; this avoids assuming diagram numbering survives the driver.')
        for name in ACTIONS:
            input('Release all wheel buttons, then Enter. ')
            wheel.poll()
            baseline = {n for n, v in wheel.buttons.items() if v}
            input('Hold the wheel button for ' + name + ', then Enter (or Enter with none to skip). ')
            wheel.poll()
            held = [n for n, v in wheel.buttons.items() if v and n not in baseline]
            if len(held) > 1:
                raise ValueError('Hold only one button')
            profile['buttons'][name] = held[0] if held else None
        validate(profile)
        target = Path(args.profile)
        if target.exists():
            raise ValueError('Profile already exists; choose a new output filename')
        target.write_text(json.dumps(profile, indent=2)+'\n')
        print('Saved calibrated profile:', target)
    finally:
        wheel.close()
        if pedals:
            pedals.close()


def run(args):
    profile = validate(json.loads(Path(args.profile).read_text()))
    output = Path(args.output)
    if output.name != 'MoonLab.Wheel.bin':
        raise ValueError('Output filename must be MoonLab.Wheel.bin in your private modded game folder')
    output = output.parent.resolve(strict=True) / output.name
    # Do not silently write into a Steam/Bottles installation. Private loader
    # copies contain the loader bootstrap configuration or a MoonLab mod DLL.
    if not ((output.parent/'MoonLab.Mod.dll').is_file() or (output.parent/'MoonLab/mods/wheel-control/mod.dll').is_file()):
        raise ValueError('Output must be a prepared private MoonLab game folder')
    lock = output.with_suffix('.lock')
    if lock.is_symlink():
        raise ValueError('Refusing symlink lock')
    with output_lock(lock):
        wheel = pedals = None
        try:
            wheel = Joystick(profile['wheel']); pedals = Joystick(profile['pedals'])
            for label, device in [('wheel', wheel), ('pedals', pedals)]:
                if device.name != profile[label+'_name']:
                    raise ValueError('Device identity changed; recalibrate ' + label)
            mapper = Mapper(profile)
            print('Wheel helper running; release pedals/buttons to arm. Ctrl+C stops it. No game is launched.')
            while True:
                started = time.monotonic()
                wheel.poll(); pedals.poll()
                publish(output, mapper.sample(wheel, pedals))
                time.sleep(max(0, 1/60 - (time.monotonic()-started)))
        finally:
            publish(output, (0., 0., 0, False))
            if wheel: wheel.close()
            if pedals: pedals.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('list')
    p = commands.add_parser('monitor'); p.add_argument('device')
    p = commands.add_parser('calibrate')
    for name in ('wheel', 'pedals', 'profile'): p.add_argument('--'+name, required=True)
    p = commands.add_parser('run')
    p.add_argument('--profile', required=True); p.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'list' and os.name == 'nt':
            from windows_input import devices
            found = devices()
            for path, name in found: print(path, name)
            if not found: print('No DirectInput controllers found. Connect the R9 and Simsonn USB devices.')
        elif args.command == 'list':
            found = False
            for path in sorted(Path('/dev/input').glob('js*')):
                found = True
                try:
                    dev = Joystick(path)
                    try: print(path, dev.name)
                    finally: dev.close()
                except OSError as error: print(path, error)
            if not found: print('No Linux joystick devices visible. Connect the R9 and Simsonn USB devices.')
        elif args.command == 'monitor':
            dev = Joystick(args.device)
            try:
                print(dev.name, '(axes/buttons are zero-based device indices)')
                while True:
                    dev.poll(); print('axes', dev.axes, 'held buttons', [n for n,v in dev.buttons.items() if v], flush=True)
                    time.sleep(.2)
            finally: dev.close()
        elif args.command == 'calibrate': calibrate(args)
        else: run(args)
    except KeyboardInterrupt:
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, str(error)+'\n')
    return 0


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    raise SystemExit(main())
