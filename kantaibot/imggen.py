"""Handles image generation."""
from PIL import Image, ImageDraw, ImageFont
import io
import os
import ship_stats
import userinfo
import math
import json
from settings import setting, namesub

DIR_PATH = os.path.dirname(os.path.realpath(__file__))

_json_cache = {}


def read_json(filepath):
    """Return the JSON inside of the given JSON file."""
    if (filepath in _json_cache):
        return _json_cache[filepath]
    with open(filepath, 'r', encoding='utf-8') as fileinfo:
        data = json.load(fileinfo)
        _json_cache[filepath] = data
        return data


CONFIG_DATA_FILE = os.path.join(DIR_PATH, "../layout.json")
CONFIG_DATA = read_json(CONFIG_DATA_FILE)

small_ico_ring_img = os.path.join(DIR_PATH, "images/ring_icon.png")

large_bg_map_img = os.path.join(DIR_PATH, "images/map_bg.jpg")

RARITY_COLORS = [(150, 150, 150), (150, 150, 150), (150, 150, 150),
                 (0, 122, 103), (255, 255, 50), (0, 255, 84),
                 (250, 25, 25), (255, 0, 234)]


def generate_inventory_screen(member, page, only_dupes=False):
    """Return a BytesIO object of the user's inventory image.

    Parameters
    ----------
    member : discord.Member
        The user to generate the inventory of.
    page : int
        The page to show.
    only_dupes : bool
        If True, only display ships which the user has two or more of.
    """
    discord_id = member.id
    user = userinfo.get_user(discord_id)
    inv = userinfo.get_user_inventory(discord_id)
    layout = CONFIG_DATA['inventory']
    w, h = layout['image_size']
    antialias_value = 2
    w *= antialias_value
    h *= antialias_value
    sx, sy = layout['per_row'], layout['per_column']
    cw = int(w / sx)
    ch = int(h / sy)
    h += layout['lower_padding'] * antialias_value

    ship_pool = inv.inventory
    if (only_dupes):
        new_pool = []
        first_bases = {}
        for s in ship_pool:
            first_bases[s.sid] = s.base().get_first_base()
        for i in range(len(ship_pool)):
            s = ship_pool.pop(0)
            if (first_bases[s.sid].sid in map(lambda x:
                                              first_bases[x.sid].sid, new_pool)
                or first_bases[s.sid].sid in map(lambda x:
                                                 first_bases[x.sid].sid,
                                                 ship_pool)):
                new_pool.append(s)
        ship_pool = new_pool

    ships_per_page = sx * sy
    pages_needed = (len(ship_pool) // ships_per_page) + \
        (0 if len(ship_pool) % ships_per_page == 0 and len(ship_pool) > 0
         else 1)
    if (page < 1):
        page = 1
    elif (page > pages_needed):
        page = pages_needed

    img = Image.new(size=(w, h), mode="RGB", color=(255, 255, 255))

    draw = ImageDraw.Draw(img)
    shade = False
    indx = 0
    indx += (ships_per_page * (page - 1))
    for xi in range(sx):
        for yi in range(sy):
            ship = ship_pool[indx] if indx < len(ship_pool) else None

            shade_color = (("filled_color1" if shade else "filled_color2")
                           if ship else ("empty_color1" if shade else "empty_color2"))
            rbg = None

            if (ship):
                rbg = ship_stats.get_rarity_backdrop(ship.base().rarity)
                rbg = rbg.resize((cw, ch))
                fleet = userinfo.UserFleet.instance(1, discord_id)
                if (ship.invid in fleet.ships):
                    flag = fleet.ships.index(ship.invid) == 0
                    if flag:
                        shade_color = 'flag_border_color'
                    else:
                        shade_color = "fleet_color1" if shade else "fleet_color2"
                elif (ship.base().has_seasonal_cg()):
                    shade_color = "seasonal_color1" if shade else "seasonal_color2"

            shade_color = tuple(layout[shade_color])

            x, y = (xi * cw, yi * ch)
            draw.rectangle((x, y, x + cw, y + ch), fill=shade_color)
            if (rbg):
                img.paste(rbg, (x, y))
            if (ship):
                base = ship.base()
                font = ImageFont.truetype("fonts/trebucbd.ttf", ch * 1 // 2)
                num_str = "%s-%04d" % (base.stype, ship.invid)
                draw_squish_text(img, (x + cw * 3 // 4, y + ch * 1 // 4), num_str,
                                 font, cw * 7 // 16 - 2, color=(0, 0, 0))

                if (setting('features.levels_enabled')):
                    if (setting('features.marriage_enabled') and ship.level > setting('levels.level_cap')):
                        ring = Image.open(small_ico_ring_img)
                        ring = ring.resize((ch // 3 - 4, ch // 3 - 4))
                        ring_loc = (x + cw * 8 // 9 - 2, y + ch * 5 // 8 + 2)
                        draw.ellipse(
                            (ring_loc, tuple(map(sum, zip(ring_loc, ring.size)))), fill=(0, 0, 0))
                        img.paste(ring, ring_loc, mask=ring)
                    font = ImageFont.truetype(
                        "fonts/trebucbd.ttf", ch * 3 // 8)
                    lvl_str = "Lv. %02d" % (ship.level)
                    draw_squish_text(img, (x + 2 + cw * 11 // 16, y + ch * 3 // 4 - 2),
                                     lvl_str, font, cw // 3 - 4, color=(0, 0, 0))
                    if (ship.is_remodel_ready()):
                        draw.rectangle((x + cw // 2 + 2, y + ch * 9 // 16, x + cw * 31 // 32, y + ch * 15 // 16),
                                       outline=(50, 0, 250), width=2)

                cir_start_x = x + 3
                cir_start_y = y + 3
                use_damaged = False  # TODO check if use damaged image
                ico = base.get_cg(ico=True, dmg=use_damaged)
                ico = ico.resize((int(ch * 1.5) - 6, ch - 6), Image.BILINEAR)
                pxls = ico.load()
                grad_start = int(ico.size[0] * 0.75)
                grad_end = ico.size[0]
                for ix in range(grad_start, grad_end):
                    for iy in range(ico.size[1]):
                        fade_amt = (ix - grad_start) / (grad_end - grad_start)
                        fade_amt *= fade_amt
                        new_alpha = int(pxls[ix, iy][3] * (1 - fade_amt))
                        pxls[ix, iy] = pxls[ix, iy][:3] + (new_alpha,)
                img.paste(ico, (cir_start_x, cir_start_y), ico)

                draw.rectangle((x, y, x + cw - 1,
                                y + ch - 1), outline=shade_color, width=3)
            shade = not shade
            indx += 1
        if(sy % 2 == 0):
            shade = not shade

    draw = ImageDraw.Draw(img)
    # start position of footer
    x, y = (0, layout['image_size'][1] * antialias_value)
    fw, fh = (w, layout['lower_padding'] * antialias_value)  # size of footer

    display_name = "%s#%s" % (member.name, member.discriminator)
    font = ImageFont.truetype("fonts/framd.ttf", fh * 3 // 4)
    o_txt = namesub("<ship_plural.title>") if not only_dupes else "Dupes"
    draw.text((x + 10, y + fh // 8), "%s's %s" % (display_name, o_txt),
              font=font, fill=(0, 0, 0))

    font = ImageFont.truetype("fonts/framdit.ttf", fh // 2)
    pg_txt = "Page %s of %s" % (page, pages_needed)
    pgw, pgh = draw.textsize(pg_txt, font=font)
    pgx, pgy = (fw - pgw - 2, y + fh - pgh - 2)
    draw.text((pgx, pgy), pg_txt, font=font, fill=(50, 50, 50))

    font = ImageFont.truetype("fonts/trebucbd.ttf", fh * 3 // 8)
    rsc_x, rsc_y = (fw * 21 // 32, y + 1)

    txt_fuel = "%05d" % (user.fuel)
    txt_ammo = "%05d" % (user.ammo)
    txt_steel = "%05d" % (user.steel)
    txt_bauxite = "%05d" % (user.bauxite)
    txt_ships = "%03d / %03d" % (len(ship_pool), user.shipslots)
    txt_rings = "%01d" % (user.rings)

    txt_w, txt_h = draw.textsize(txt_fuel, font)

    ico_size = (fh * 3 // 8 + 2, fh * 3 // 8 + 2)
    if (setting('features.resources_enabled')):
        ico_fuel = Image.open(DIR_PATH + '/icons/fuel.png').resize(ico_size,
                                                                   Image.LINEAR)
        ico_ammo = Image.open(DIR_PATH + '/icons/ammo.png').resize(ico_size,
                                                                   Image.LINEAR)
        ico_steel = Image.open(DIR_PATH + '/icons/steel.png').resize(ico_size,
                                                                     Image.LINEAR)
        ico_bauxite = Image.open(DIR_PATH + '/icons/bauxite.png') \
            .resize(ico_size, Image.LINEAR)
    ico_ships = Image.open(DIR_PATH + '/icons/ship.png').resize(ico_size,
                                                                Image.LINEAR)
    if (setting('features.marriage_enabled') and setting('levels.marriage_ring_required')):
        ico_rings = Image.open(DIR_PATH + '/icons/marriagepapers.png') \
            .resize(ico_size, Image.LINEAR)

    x_off = ico_size[0] + txt_w + 6
    y_off = ico_size[1] + 2
    toff_x, toff_y = (ico_size[0] + 2, (ico_size[1] - txt_h) // 2)

    if (setting('features.resources_enabled')):
        draw.text((rsc_x + toff_x, rsc_y + toff_y), txt_fuel, font=font,
                  fill=(0, 0, 0))
        draw.text((rsc_x + toff_x, rsc_y + toff_y + y_off), txt_ammo, font=font,
                  fill=(0, 0, 0))
        draw.text((rsc_x + toff_x + x_off, rsc_y + toff_y), txt_steel, font=font,
                  fill=(0, 0, 0))
        draw.text((rsc_x + toff_x + x_off, rsc_y + toff_y + y_off), txt_bauxite,
                  font=font, fill=(0, 0, 0))
    draw.text((rsc_x + toff_x + x_off * 2, rsc_y + toff_y), txt_ships,
              font=font, fill=(0, 0, 0))
    if (setting('features.marriage_enabled') and setting('levels.marriage_ring_required')):
        draw.text((rsc_x + toff_x + int(x_off * 3.5), rsc_y + toff_y), txt_rings,
                  font=font, fill=(0, 0, 0))

    if (setting('features.resources_enabled')):
        img.paste(ico_fuel, (rsc_x, rsc_y), mask=ico_fuel)
        img.paste(ico_ammo, (rsc_x, rsc_y + y_off), mask=ico_fuel)
        img.paste(ico_steel, (rsc_x + x_off, rsc_y), mask=ico_fuel)
        img.paste(ico_bauxite, (rsc_x + x_off, rsc_y + y_off), mask=ico_fuel)
    img.paste(ico_ships, (rsc_x + x_off * 2, rsc_y), mask=ico_ships)
    if (setting('features.marriage_enabled') and setting('levels.marriage_ring_required')):
        img.paste(ico_rings, (rsc_x + int(x_off * 3.5), rsc_y), mask=ico_rings)

    img = img.resize((w // antialias_value, h //
                      antialias_value), Image.ANTIALIAS)

    r = io.BytesIO()
    img.save(r, format="PNG")
    return r


def generate_ship_card(bot, ship_instance):
    """Return a BytesIO object of a card image of the given ship.

    Parameters
    ----------
    bot : discord.ext.commands.Bot
        The bot being run.
    ship_instance : ShipInstance
        The ship to display.
    """
    base = ship_instance.base()

    img = ship_stats.get_rarity_backdrop(base.rarity)

    layout = CONFIG_DATA['ship_card']
    obj_small_identifier = layout['small_identifier']
    obj_name = layout['name']
    obj_class_name = layout['class_name']
    obj_level_indicator = layout['level_indicator']
    obj_level_progress = layout['level_progress']
    obj_next_remodel = layout['next_remodel']
    obj_owned_by = layout['owned_by']
    obj_main_image = layout['main_image']

    use_damaged = False  # TODO make this check if ship is damaged

    img_full = base.get_cg(dmg=use_damaged)

    if (obj_main_image['enabled']):
        img_w, img_h = img_full.size
        targ_width = int(obj_main_image['targ_height'] * (img_w / img_h))
        x_offset = int(obj_main_image['x_offset'] - (targ_width / 2))
        img_full = img_full.resize((targ_width, obj_main_image['targ_height']),
                                   Image.BICUBIC)
        img.paste(
            img_full, (x_offset, obj_main_image['y_offset']), mask=img_full)

    if (ship_instance.level > setting('levels.level_cap')):
        ring = Image.open(small_ico_ring_img)
        ring = ring.resize((60, 60))
        img.paste(ring, (20, 20), mask=ring)

    if (obj_name['enabled']):
        draw_object(img, obj_name, base.name)
    if (obj_class_name['enabled']):
        draw_object(img, obj_class_name, "%s %s" % (base.class_name,
                                                    ship_stats.get_ship_type(base.stype).full_name))
    if (setting('features.levels_enabled')):
        if (obj_level_indicator['enabled']):
            draw_object(img, obj_level_indicator, "Level %s" %
                        (ship_instance.level))
        if (obj_level_progress['enabled'] and (ship_instance.level > 1 or ship_instance.exp > 0)
                and ship_instance.level != setting('levels.level_cap') and ship_instance.level < setting('levels.level_cap_married')):
            exp = ship_instance.exp
            req = ship_instance.exp_req()
            draw_object(img, obj_level_progress, "%s / %s EXP (%.02f%%)" %
                        (exp, req, 100.0 * exp / req))
        if (base.remodels_into and obj_next_remodel['enabled']):
            r_base = ship_stats.ShipBase.instance(base.remodels_into)
            draw_object(img, obj_next_remodel, "Next Remodel: %s (Level %s)" % (
                r_base.name, base.remodel_level))

    if (obj_small_identifier['enabled']):
        draw_object(img, obj_small_identifier, "%s-%04d" %
                    (base.stype, ship_instance.invid))

    if (obj_owned_by['enabled']):
        display_name = "Unknown User"
        for g in bot.guilds:
            owner = g.get_member(ship_instance.owner)
            if (owner):
                display_name = "%s#%s" % (owner.name, owner.discriminator)
                break
        draw_object(img, obj_owned_by, namesub("Part of %s's <fleet.title>" % (display_name)))

    r = io.BytesIO(b'')
    img.save(r, format="PNG")
    return r


def get_birthday_image(base):
    """Return BytesIO object of an image for a ship's birthday.

    Parameters
    ----------
    base : ShipBase
        The base object of the ship to celebrate the birthday of.
    """
    img_size = (600, 800)
    img = Image.new(size=img_size, mode="RGB", color=(0, 0, 0))

    backdrop = Image.open(DIR_PATH + '/images/bday_bg.png')
    img.paste(backdrop)

    cg = base.get_cg()

    img_w, img_h = cg.size
    targ_height = img_size[1] * 3 // 4
    targ_width = int(targ_height * (img_w / img_h))
    x_offset = int((img_size[0] / 2) - (targ_width / 2))
    cg = cg.resize((targ_width, targ_height), Image.BICUBIC)
    img.paste(cg, (x_offset, 0), mask=cg)

    font = ImageFont.truetype("fonts/impact.ttf", 60)
    draw_squish_text(img, (img_size[0] // 2, targ_height + 20),
                     "Happy Birthday", font, img_size[0] - 20, color=(0, 0, 0),
                     outline=(125, 125, 125))
    font_2 = ImageFont.truetype("fonts/impact.ttf", 80)
    draw_squish_text(img, (img_size[0] // 2, targ_height + 110), "%s!"
                     % (base.name), font_2, img_size[0] - 20, color=(0, 0, 0),
                     outline=(125, 125, 125))

    r = io.BytesIO(b'')
    img.save(r, format="PNG")
    return r


def generate_sortie_card(sortie):
    """Return a BytesIO object of a sortie map.

    Parameters
    ----------
    sortie : Sortie
        The Sortie object to display.
    """
    padding = 20
    orig_w, orig_h = sortie.map_size
    padding_s = padding * 2

    size_info = padding
    for pos, node in sortie.nodes:
        if (len(node.routing_rules.routes) < 1):
            continue
        for connected in node.routing_rules.routes:
            size_info += 22
        size_info += 10

    info_w, info_h = (0, size_info)
    img = Image.new(size=(orig_w + padding_s + info_w, orig_h + padding_s
                          + info_h), mode="RGB", color=(255, 255, 255))

    bg = Image.open(large_bg_map_img)
    bg = bg.resize((orig_w + padding_s, orig_h + padding_s), Image.LINEAR)
    img.paste(bg, (0, 0))

    font = ImageFont.truetype("fonts/framd.ttf", 20)
    draw = ImageDraw.Draw(img)
    for pos, node in sortie.nodes:
        pos = (pos[0] + padding, pos[1] + padding)
        for r in node.routing_rules.routes:
            n_to = r.node_to
            node_to = sortie.nodes[n_to][0]
            node_to = (node_to[0] + padding, node_to[1] + padding)
            tri_w_s = 5
            if (pos[0] == node_to[0]):
                tri_1 = (pos[0] - tri_w_s, pos[1])
                tri_2 = (pos[0] + tri_w_s, pos[1])
            elif (pos[1] == node_to[1]):
                tri_1 = (pos[0], pos[1] + tri_w_s)
                tri_2 = (pos[0], pos[1] - tri_w_s)
            else:
                rad = math.atan2(pos[1] - node_to[1], pos[0] - node_to[0])
                rad += math.pi / 2
                off_x = math.cos(rad)
                off_y = math.sin(rad)
                tri_1 = (pos[0] + tri_w_s * off_x, pos[1] + tri_w_s * off_y)
                tri_2 = (pos[0] - tri_w_s * off_x, pos[1] - tri_w_s * off_y)
            draw.polygon([tri_1, tri_2, node_to], fill=(142, 136, 255),
                         outline=(0, 0, 0))
    for pos, node in sortie.nodes:
        pos = (pos[0] + padding, pos[1] + padding)
        cir_s = 12
        ImageDraw.Draw(img).ellipse((pos[0] - cir_s, pos[1] - cir_s, pos[0]
                                     + cir_s, pos[1] + cir_s),
                                    fill=node.ntype.color)
        draw_squish_text(img, pos, node.symbol(), font, 35, (255, 255, 255))

    draw = ImageDraw.Draw(img)
    draw.rectangle((0, orig_h + padding_s, orig_w + padding_s + info_w,
                    orig_h + padding_s + info_h), fill=(50, 50, 50))

    txt_x = padding
    txt_y = orig_h + padding_s + 10
    for pos, node in sortie.nodes:
        if (len(node.routing_rules.routes) < 1):
            continue
        format = node.routing_rules.format()
        for connected in reversed(node.routing_rules.routes):
            draw.text((txt_x, txt_y), "%s => %s : %s"
                      % (node.symbol(),
                         sortie.nodes[connected.node_to][1].symbol(),
                         format[connected.node_to]), font=font,
                      fill=(255, 255, 255))
            txt_y += 22
        txt_y += 10

    r = io.BytesIO(b'')
    img.save(r, format="PNG")
    return r


def draw_object(img, obj, text, center_height=True, repeat=1):
    """Draw a configuration object using its JSON Parameters."""
    font = ImageFont.truetype(obj['font'], obj['font_size'])
    draw_squish_text(img, tuple(obj['position']), text, font, obj['width'], color=tuple(obj['color']),
                     outline=tuple(obj['outline']), center_height=center_height, repeat=repeat)


def draw_squish_text(img, position, text, font, max_width,
                     color=(255, 255, 255), outline=None, center_height=True,
                     repeat=1):
    """Draw centered text and squish it if it is too wide.

    Parameters
    ----------
    img : PIL.Image
        The image to draw on.
    position : tuple
        2-tuple of the position of the center of the text.
    text : str
        The text to write.
    font : Pil.ImageFont
        The font to write with.
    max_width : int
        The maximum width the text can span, will be squished to this size
        if it is too wide.
    color : tuple
        3-tuple of the color of the text
    outline : tuple
        3-tuple of the color of the outline, None for no outline
    center_height : bool
        True if the text should be centered vertically.
    repeat : int
        Amount of times to repeat drawing this text, for sharpness.
    """
    draw = ImageDraw.Draw(img)
    w, h = draw.textsize(text, font=font)
    text_img = Image.new(size=(w, h), color=(0, 0, 0, 0), mode="RGBA")
    tdraw = ImageDraw.Draw(text_img)
    draw_outline(tdraw, (0, 0), text, font, color, outline, repeat)
    if (max_width < w):
        text_img = text_img.resize((max_width, h), Image.BILINEAR)
    w, h = text_img.size
    paste_x = int(position[0] - (w / 2))
    if center_height:
        paste_y = int(position[1] - (h / 2))
    else:
        paste_y = position[1]
    img.paste(text_img, (paste_x, paste_y), mask=text_img)
    del draw


def draw_centered_text(draw, position, text, font, color=(255, 255, 255),
                       outline=(255, 255, 255),
                       center_height=True, repeat=1):
    """Draw centered text on a draw object.

    Parameters
    ----------
    draw : PIL.ImageDraw
        The draw object to draw on.
    position : tuple
        2-tuple of the position of the center of the text.
    text : str
        The text to write.
    font : Pil.ImageFont
        The font to write with.
    color : tuple
        3-tuple of the color of the text
    outline : tuple
        3-tuple of the color of the outline, None for no outline
    center_height : bool
        True if the text should be centered vertically.
    repeat : int
        Amount of times to repeat drawing this text, for sharpness.
    """
    w, h = draw.textsize(text, font=font)
    x, y = position
    if (center_height):
        start_loc = (x - w / 2, y - h / 2)
    else:
        start_loc = (x - w / 2, y)
    draw_outline(draw, start_loc, text, font, color, outline, repeat)


def draw_outline(draw, position, text, font, fill, outline, repeat):
    """Draw text with an outline.

    Parameters
    ----------
    draw : PIL.ImageDraw
        The draw object to draw on.
    position : tuple
        2-tuple of the position of the top left of the text.
    text : str
        The text to write.
    font : Pil.ImageFont
        The font to write with.
    fill : tuple
        3-tuple of the color of the text
    outline : tuple
        3-tuple of the color of the outline, None for no outline
    repeat : int
        Amount of times to repeat drawing this text, for sharpness.
    """
    x, y = position
    if (outline):
        for i in range(repeat * 3):
            draw.text((x-1, y-1), text, font=font, fill=outline)
            draw.text((x+1, y-1), text, font=font, fill=outline)
            draw.text((x-1, y-1), text, font=font, fill=outline)
            draw.text((x+1, y+1), text, font=font, fill=outline)
    for i in range(repeat):
        draw.text((x, y), text, font=font, fill=fill)
