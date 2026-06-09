# Nebula Courier

![Nebula Courier Cover](cover_nebula_courier_round_tunnel.png)

(The entire game, including this README file, is AI-generated.)

Nebula Courier is a small 3D arcade game written in Python. You fly a spaceship through a round sci-fi tunnel that follows a circular path. Along the way, you collect green and blue crystals, dodge asteroids, and use boost to move faster through the tunnel.

The game has no external Python dependencies. It uses `tkinter`, which is included with standard Python installations.

## Features

- 3D perspective with a custom lightweight renderer
- Round tunnel with stationary boundary rings
- Circular tunnel path for stronger spatial motion
- Green crystals, moving blue bonus crystals, asteroids, score, combo, lives, and boost energy
- Keyboard controls with `WASD` or arrow keys

## Starting the Game

The easiest way is to double-click:

```bat
start_spiel.bat
```

Or from a terminal:

```bat
cd ...\Spiel
start_spiel.bat
```

Alternatively, run it directly with Python:

```bat
python spiel.py
```

If `python` is not recognized on your computer, install Python 3 from https://www.python.org/downloads/ and enable the `Add python.exe to PATH` option in the installer.

## Controls

- `WASD` or arrow keys: steer the spaceship
- `Space`: boost
- `R`: restart after game over or victory
- `Esc`: quit

## Goal

Collect green crystals, chase moving blue bonus crystals for extra points, dodge asteroids, and guide the Nebula Courier through the tunnel until you reach distance 1400.

## Files

- `spiel.py`: main game code
- `start_spiel.bat`: Windows start script
- `cover_nebula_courier_round_tunnel.png`: cover image with the round tunnel
