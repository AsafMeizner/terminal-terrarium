# Make your own ASCII animal

No graphics experience needed. If you can change a number in a file, you can make a creature
swim across your terminal.

Inspired by [@stephenz.mp4's reel](https://www.instagram.com/reel/Dfv29ZozCr2/) explaining
ASCII animals for non-technical friends. This page uses the same ideas, and terrarium has them
built in.

## How it works, in four ideas

**1. The screen is a grid of cells,** like graph paper. Each cell holds one character:
` . : - = + * # % @`. Lighter characters look faint, heavier ones look solid.

**2. Many times a second the program does two things: move, then draw.**

**3. Move.** Every animal follows its own simple rules. A fish wanders in lazy S-curves. If
there's food, it turns toward the food. If your mouse comes close, it darts away. That's
`Mover` in [`terrarium/shapes.py`](../terrarium/shapes.py).

**4. Draw.** An animal is a few round parts: circles, ovals and "capsules" (a stretched blob that
can be fat at one end and thin at the other). For every cell the program asks *how deep inside
the animal am I?*

```
        . : - = = - : .           edge cells     ->  light characters  . :
     .:=*#%%%%%%%%%#*=:.
    :*%%%%%%%%%%%%%%%%%*: =+*:     deep inside    ->  dense characters   % @
     .:=*#%%%%%%%%%#*=:.  -=*:
        . : - = = - : .           lit side is brighter, the shadow side darker
```

Depth is a trick too: smaller animals are "farther away", so they move slower and fade into the
dark. That's `depth=` in the code.

## Make one (5 minutes)

1. Install terrarium (Python 3.9+):

   ```sh
   pipx install git+https://github.com/AsafMeizner/terminal-terrarium
   ```

2. Ask it for a starter animal:

   ```sh
   terrarium --new my_fish --path ~/.terrarium/scenes
   ```

   That writes `~/.terrarium/scenes/my_fish.py`.

3. Run it:

   ```sh
   terrarium my_fish
   ```

   You'll see little fish wandering. **Click** to drop food and watch them go for it. Point at
   one and it swims away.

4. Open `my_fish.py` in any text editor and play. Save, then run `terrarium my_fish` again.

## What's in the file

The starter has four parts, matching the four ideas above.

**`setup`: create the animals.** Each one rolls its own little "genome", so every run is different:

```python
depth = rng.random()                 # 0 = far away, 1 = close
"size": 2 + 3 * depth,               # far things look smaller
"color": hsv(rng.random(), 0.6, 1.0),
```

**`on_click`: what clicking does.** Here it drops food:

```python
def on_click(self, x, y):
    self.food.append([x, y])
```

**`update`: move.** Wander, but head for the nearest food, and flee the mouse pointer:

```python
m.update(dt, self.t, (self.w, self.h), target=target, threat=self.pointer)
```

**`draw`: build the body from round parts, then let terrarium shade it:**

```python
body = Body()
body.capsule(head_x, head_y, tail_x, tail_y, 0.6 * size, 0.25 * size, color=c["color"])  # body
body.circle(tail_x, tail_y, 0.35 * size, color=c["color"])                                # tail
body.spot(eye_x, eye_y, 0.3, (20, 20, 30), "o")                                           # eye
body.draw(cv, depth=c["depth"])
```

## Things to try

- **Rounder animals:** change the `0.6` in the capsule to `0.9`.
- **A different animal:** a ladybug is one `circle` plus black `spot`s. A snake is a `Chain`
  (a spine that follows its head) with a `capsule` between each pair of points.
- **Patterns:** `body.draw(cv, pattern=fn)` lets you color cells yourself. Stripes are
  `lambda x, y, part, inside: (0, 0, 0) if int(x) % 3 == 0 else None`.
- **Glow:** `body.draw(cv, glow=0.6)` adds a soft halo, which suits jellyfish and fireflies.
- **More behavior:** make them flee the mouse faster, sleep at night, or chase each other.
  Change `Mover`'s `speed`, or write your own rule in `update`.
- **Colors:** run with `-t vapor` or `-t ocean` to recolor everything, or `--charset blocks`
  for a chunkier look.

## The toolkit

| | |
|---|---|
| `Body()` | a creature made of round parts |
| `.circle(x, y, r, color=)` | a round part (`r` in cells) |
| `.ellipse(x, y, rx, ry, angle, color=)` | an oval, turned by `angle` (radians) |
| `.capsule(x0, y0, x1, y1, r0, r1, color=)` | a blob from one point to another, radius `r0` to `r1` |
| `.spot(x, y, r, color, char=None)` | a decal on top: eyes, spots, stripes |
| `.draw(cv, depth=, light=, glow=, pattern=)` | shade it onto the screen |
| `Mover(rng, x, y, speed, depth)` | wanders in S-curves; `.update(dt, t, (w, h), target=, threat=)` |
| `Chain(x, y, n, spacing)` | a spine that follows its head; `.follow(x, y)`, `.points` |
| `self.pointer` | where the mouse is, or `None` |
| `on_click(self, x, y)` | runs when you click |

Real scenes built this way: [`fishbowl.py`](../terrarium/scenes/fishbowl.py) is a fuller version
of the starter, with a glass bowl, a plant, pebbles, bubbles and a calico pattern.

## Share it

Put your file in `terrarium/scenes/` in a fork of this repo, run
`python scripts/make_gifs.py my_fish` for a screenshot, and open a pull request. Once merged, it
shows up in `terrarium --list`, in the README, and on the
[web playground](https://terminal-terrarium.vercel.app).
