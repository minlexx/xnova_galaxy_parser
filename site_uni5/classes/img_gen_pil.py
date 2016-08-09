#!/usr/bin/python3

# Uses Python Imaging Library fork (Pillow) to render galaxy maps
# Requirements, installation:
# pip3 install Pillow
# on Debian Linux, requirements should be installed:
# - compiler (build-essential)
# - zlib devel files (zlib1g-dev)
# - libjpeg, libjpeg-devel

import io
import logging
import sqlite3
import sys

try:
    import PIL
except ImportError:
    PIL = None
    sys.stderr.write('Cannot import Pillow module! Install Pillow:\n')
    sys.stderr.write('#  pip3 install Pillow\n')
    exit(1)


import PIL.Image
import PIL.ImageDraw


# global XNova log message formatter
g_xn_log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')


# get "standard" logger for application, public api
def get_logger(name, debug=False):
    level = logging.INFO
    if debug:
        level = logging.DEBUG
    # each module gets its own logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False
    # each module logger has its own handler attached
    log_handler = logging.StreamHandler(stream=sys.stdout)
    log_handler.setLevel(level)
    # but all loggers/handlers have the same global formatter
    log_handler.setFormatter(g_xn_log_formatter)
    logger.addHandler(log_handler)
    return logger


g_logger = get_logger(__name__, debug=True)
g_output_filename = 'galaxy_map.png'
g_db_filename = 'galaxy5.db'
g_db = sqlite3.connect(g_db_filename)

SCALE_X = 2
SCALE_Y = 100
HEIGHT = 4*SCALE_Y
WIDTH = 500*SCALE_X


def load_galaxy_bg():
    try:
        img = PIL.Image.open('bg.png')
        return img
    except IOError:
        g_logger.error('Failed to open bg.png!')
        return None


def generate_background() -> PIL.Image.Image:
    img = PIL.Image.new('RGBA', (WIDTH, HEIGHT), color=(0, 0, 0, 255))
    draw_galaxy_grid(img, (128, 128, 128, 255))
    return img


def draw_galaxy_grid(img: PIL.Image.Image, color: tuple):
    draw = PIL.ImageDraw.Draw(img)
    for x in [200, 400, 600, 800]:
        draw.line([(x, 0), (x, 399)], fill=color)
    for y in [100, 200, 300]:
        draw.line([(0, y), (999, y)], fill=color)


def draw_population(img: PIL.Image.Image):
    draw = PIL.ImageDraw.Draw(img)
    cur = g_db.cursor()
    for x in range(0, 499):
        for y in range(0, 4):
            q = 'SELECT COUNT(*) FROM planets WHERE s=? AND g=?'
            cur.execute(q, (x + 1, y + 1))
            row = cur.fetchone()
            num_planets = row[0]
            fill_percent = num_planets / 15
            cc = int(255 * fill_percent)
            #
            draw.rectangle([(x*SCALE_X,         HEIGHT - y*SCALE_Y),
                            (x*SCALE_X+SCALE_X, HEIGHT - y*SCALE_Y - SCALE_Y)],
                           fill=(cc, cc, cc, 255), outline=None)
    cur.close()


def draw_moons(img: PIL.Image.Image):
    draw = PIL.ImageDraw.Draw(img)
    q = 'SELECT g, s, p FROM planets WHERE luna_id > 0'
    cur = g_db.cursor()
    cur.execute(q)
    rows = cur.fetchall()
    for row in rows:
        x = int(row[1]) * SCALE_X  # system
        y = HEIGHT - int(row[0]) * SCALE_Y  # galaxy
        y += round(SCALE_Y * (int(row[2]) / 15))  # position
        # g_logger.debug('Row: {0}, xy: {1}, {2}'.format(row, x, y))
        # img.putpixel((x, y), (255, 255, 0, 255))
        draw.ellipse([(x-2, y-2), (x+2, y+2)], fill=(255, 255, 0, 128), outline=None)
    cur.close()


def draw_player_planets(img: PIL.Image.Image, user_name: str, moons_only: bool = False):
    draw = PIL.ImageDraw.Draw(img)
    q = 'SELECT g, s, p FROM planets WHERE (user_name LIKE ?)'
    if moons_only:
        q += ' AND (luna_id > 0)'
    cur = g_db.cursor()
    cur.execute(q, (user_name, ))
    rows = cur.fetchall()
    for row in rows:
        x = int(row[1]) * SCALE_X  # system
        y = HEIGHT - int(row[0]) * SCALE_Y  # galaxy
        y += round(SCALE_Y * (int(row[2]) / 15))  # position
        # g_logger.debug('Row: {0}, xy: {1}, {2}'.format(row, x, y))
        # img.putpixel((x, y), (255, 255, 0, 255))
        draw.ellipse([(x - 2, y - 2), (x + 2, y + 2)], fill=(255, 255, 0, 128), outline=None)
    cur.close()


def draw_alliance_planets(img: PIL.Image.Image, ally_name: str, moons_only: bool = False):
    draw = PIL.ImageDraw.Draw(img)
    q = 'SELECT g, s, p FROM planets WHERE ((ally_name LIKE ?) OR (ally_tag LIKE ?))'
    if moons_only:
        q += ' AND (luna_id > 0)'
    cur = g_db.cursor()
    cur.execute(q, (ally_name, ally_name))
    rows = cur.fetchall()
    for row in rows:
        x = int(row[1]) * SCALE_X  # system
        y = HEIGHT - int(row[0]) * SCALE_Y  # galaxy
        y += round(SCALE_Y * (int(row[2]) / 15))  # position
        # g_logger.debug('Row: {0}, xy: {1}, {2}'.format(row, x, y))
        # img.putpixel((x, y), (255, 255, 0, 255))
        draw.ellipse([(x - 2, y - 2), (x + 2, y + 2)], fill=(255, 255, 0, 128), outline=None)
    cur.close()


def get_image_bytes(img: PIL.Image.Image, fmt=None) -> bytes:
    bio = io.BytesIO()
    img.save(fp=bio, format=fmt)
    return bio.getvalue()


def main():
    img = generate_background()
    draw_population(img)
    # draw_moons(img)
    # draw_player_planets(img, 'DemonDV', moons_only=False)
    draw_alliance_planets(img, 'НеДорого', moons_only=True)
    draw_galaxy_grid(img, (128, 128, 255, 255))
    img.save(g_output_filename)
    #
    # cleanup
    g_db.close()

if __name__ == '__main__':
    g_logger.info('Using Pillow library, version {0} (PIL {1})'.format(
        PIL.PILLOW_VERSION, PIL.VERSION))
    main()
